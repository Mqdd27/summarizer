import os
import socket
import ipaddress
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

import config
from services.summarizer import process_url, ask_document, ask_with_sources

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
async def summarize_url(request: Request, url: str = Form(...)):
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    error = validate_url(url)
    if error:
        return templates.TemplateResponse(
            request=request, name="result.html", context={"error": error}
        )

    result = await process_url(url)
    return templates.TemplateResponse(
        request=request, name="result.html", context=result
    )


@router.post("/api/chat-document")
async def chat_document(request: Request, question: str = Form(...), context: str = Form(...)):
    if not question.strip():
        return HTMLResponse("")

    try:
        answer_html = await ask_document(context, question.strip())
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


@router.post("/api/chat-research")
async def chat_research(request: Request, question: str = Form(...), existing_context: str = Form(...), new_url: str = Form(None), new_file: UploadFile = File(None)):
    new_context = ""
    if new_url:
        result = await process_url(new_url)
        if "error" not in result:
            new_context = result.get("summary_md", "")
    elif new_file and new_file.filename:
        import shutil, os
        filename = f"research_{uuid4().hex[:8]}_{new_file.filename}"
        filepath = os.path.join(config.UPLOAD_DIR, filename)
        content = await new_file.read()
        with open(filepath, "wb") as f:
            f.write(content)
        try:
            from services.summarizer import extract_from_pdf, extract_from_image
            import mimetypes
            mime = new_file.content_type or mimetypes.guess_type(new_file.filename)[0] or ""
            if mime in config.ALLOWED_PDF_TYPES:
                extracted = extract_from_pdf(filepath)
                new_context = extracted.get("summary_md", "") if hasattr(extracted, "get") else ""
            elif mime in config.ALLOWED_IMAGE_TYPES:
                extracted = extract_from_image(filepath)
                new_context = extracted.get("summary_md", "") if hasattr(extracted, "get") else ""
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)
    elif new_file and not new_file.filename:
        return HTMLResponse("")

    if not new_context:
        return HTMLResponse("")

    answer_html = await ask_with_sources(existing_context, new_context, question)
    return templates.TemplateResponse(
        request=request, name="chat_message.html", context={"question": question, "answer_html": answer_html}
    )
