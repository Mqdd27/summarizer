import os
import uuid
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.templating import Jinja2Templates

import config

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    name = name.replace("..", "").replace("/", "").replace("\\", "")
    if not name:
        name = "upload"
    return f"{uuid.uuid4().hex[:8]}_{name}"


@router.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...), model: str = Form(...)):
    if not file.filename:
        return templates.TemplateResponse(
            request=request, name="result.html", context={"error": "No file provided."}
        )

    content = await file.read()
    if len(content) > config.UPLOAD_MAX_SIZE:
        return templates.TemplateResponse(
            request=request, name="result.html",
            context={"error": f"File too large. Max size: {config.UPLOAD_MAX_SIZE // (1024*1024)}MB."}
        )

    mime = file.content_type or mimetypes.guess_type(file.filename)[0] or ""
    safe_name = sanitize_filename(file.filename)
    file_path = os.path.join(config.UPLOAD_DIR, safe_name)

    suffix = Path(file.filename).suffix.lower()
    if mime in config.ALLOWED_PDF_TYPES or suffix == ".pdf":
        input_type = "pdf"
    elif mime in config.ALLOWED_IMAGE_TYPES:
        input_type = "image"
    elif suffix in config.ALLOWED_DOCUMENT_EXTENSIONS and (
        mime in config.ALLOWED_DOCUMENT_TYPES or mime.startswith("text/") or mime == "application/octet-stream"
    ):
        input_type = "document"
    else:
        return templates.TemplateResponse(
            request=request, name="result.html",
            context={"error": "Unsupported file type. Allowed: PDF, DOCX, ODT, and text-based documents such as TXT, Markdown, CSV, JSON, XML, HTML, RTF, YAML, and code files."}
        )

    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(content)

    from services.models import validate_model
    from services.summarizer import process_file, reset_model, set_model
    selected_model = await validate_model(model)
    token = set_model(selected_model)
    try:
        result = await process_file(file_path, input_type, file.filename or safe_name)
    finally:
        reset_model(token)
        if os.path.exists(file_path):
            os.remove(file_path)

    return templates.TemplateResponse(
        request=request, name="result.html", context=result
    )
