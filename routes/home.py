import os

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

import config
from services.models import get_models

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"))


@router.get("/")
async def home(request: Request):
    try:
        models = await get_models()
    except Exception:
        models = [config.OLLAMA_MODEL]
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"models": models, "selected_model": config.OLLAMA_MODEL},
    )
