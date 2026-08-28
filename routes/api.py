import os
import socket
import ipaddress
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

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


@router.post("/api/chat-document")
async def chat_document(request: Request, question: str = Form(...), context_id: str = Form(...), model: str = Form(...)):
    if not question.strip():
        return HTMLResponse("")

    try:
        context = await get_document_context(context_id)
        if not context:
            raise ValueError("Source context expired. Please summarize the source again.")
        selected_model = await validate_model(model)
        token = set_model(selected_model)
        try:
            answer_html = await ask_document(context, question.strip())
        finally:
            reset_model(token)
        return templates.TemplateResponse(
            request=request,
            name="chat_message.html",
            context={"question": question, "answer_html": answer_html},
        )
    except Exception as e:
        error_html = f"<p class='text-red-400'>Error: {e}</p>"
        return templates.TemplateResponse(
            request=request,
            name="chat_message.html",
            context={"question": question, "answer_html": error_html},
        )
