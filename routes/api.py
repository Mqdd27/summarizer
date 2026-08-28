import os
import socket
import ipaddress
import base64
import html
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response

import config
from services.cache import get_document_context
from services.models import validate_model
from services.summarizer import ask_document, process_url, reset_model, set_model

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


def is_ssrf_target(url: str) -> bool:
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return True
        if hostname in ("localhost", "0.0.0.0"):
            return True
        try:
            addr = ipaddress.ip_address(hostname)
            return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved
        except ValueError:
            pass
        try:
            resolved = socket.getaddrinfo(hostname, None)
            for family, _, _, _, sockaddr in resolved:
                ip_str = sockaddr[0]
                addr = ipaddress.ip_address(ip_str)
                if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                    return True
        except socket.gaierror:
            return True
    except Exception:
        return True
    return False


def validate_url(url: str) -> str | None:
    if not url or not url.strip():
        return "URL is required."
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.hostname:
        return "Invalid URL."
    if is_ssrf_target(url):
        return "Access to internal/private addresses is not allowed."
    return None


@router.post("/api/summarize-url")
async def summarize_url(request: Request, url: str = Form(...), model: str = Form(...)):
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    error = validate_url(url)
    if error:
        return templates.TemplateResponse(
            request=request, name="result.html", context={"error": error}
        )

    selected_model = await validate_model(model)
    token = set_model(selected_model)
    try:
        result = await process_url(url)
    finally:
        reset_model(token)
    return templates.TemplateResponse(
        request=request, name="result.html", context=result
    )


@router.get("/api/document-source/{context_id}")
async def document_source(context_id: str):
    context = await get_document_context(context_id)
    headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
    if not context:
        return HTMLResponse(
            '<div class="p-6 text-sm text-red-400">Source expired. Please summarize it again.</div>',
            status_code=410,
            headers=headers,
        )
    if context["source_type"] == "image":
        try:
            return Response(base64.b64decode(context["content"]), media_type="image/jpeg", headers=headers)
        except ValueError:
            return Response(status_code=422, headers=headers)
    escaped = html.escape(context["content"])
    return HTMLResponse(
        f'<article class="whitespace-pre-wrap break-words text-sm leading-7 text-dark-300">{escaped}</article>',
        headers=headers,
    )


@router.post("/api/chat-document")
async def chat_document(request: Request, question: str = Form(...), context_id: str = Form(...), model: str = Form(...), research: str = Form("false")):
    if not question.strip():
        return HTMLResponse("")

    try:
        context = await get_document_context(context_id)
        if not context:
            raise ValueError("Source context expired. Please summarize the source again.")
        selected_model = await validate_model(model)
        token = set_model(selected_model)
        try:
            answer_html, web_sources = await ask_document(
                context, question.strip(), research=research == "true"
            )
        finally:
            reset_model(token)
        return templates.TemplateResponse(
            request=request,
            name="chat_message.html",
            context={"question": question, "answer_html": answer_html, "web_sources": web_sources},
        )
    except Exception as e:
        error_html = f"<p class='text-red-400'>Error: {e}</p>"
        return templates.TemplateResponse(
            request=request,
            name="chat_message.html",
            context={"question": question, "answer_html": error_html},
        )
