import os
import time
import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse

import config
from services.cache import init_db
from routes.home import router as home_router
from routes.upload import router as upload_router
from routes.api import router as api_router

os.makedirs(config.UPLOAD_DIR, exist_ok=True)

rate_limit_store: dict[str, list[float]] = defaultdict(list)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = config.RATE_LIMIT_WINDOW
        rate_limit_store[client_ip] = [
            t for t in rate_limit_store[client_ip] if now - t < window
        ]
        if len(rate_limit_store[client_ip]) >= config.RATE_LIMIT_REQUESTS:
            return JSONResponse({"error": "Rate limit exceeded. Try again later."}, status_code=429)
        rate_limit_store[client_ip].append(now)
    return await call_next(request)


app.include_router(home_router)
app.include_router(upload_router)
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host=config.APP_HOST, port=config.APP_PORT, reload=False)
