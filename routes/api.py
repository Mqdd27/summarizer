import os
import socket
import ipaddress
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates

import config
from services.summarizer import process_url

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
