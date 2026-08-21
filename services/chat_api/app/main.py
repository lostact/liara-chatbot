from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from shared.settings import get_settings
from app.obs.logger import setup_logging
from app.api.chat import router as chat_router
from app.api.conversations import router as conv_router
from app.api.feedback import router as feedback_router
from app.api.suggestions import router as suggestions_router
from app.api.config import router as config_router
from app.api.health import router as health_router

settings = get_settings()
setup_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Liara Docs Chatbot API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Mount API routers
app.include_router(chat_router)
app.include_router(conv_router)
app.include_router(feedback_router)
app.include_router(suggestions_router)
app.include_router(config_router)
app.include_router(health_router)


# Serve Widget JS
WIDGET_CANDIDATE_PATHS = [
    Path("/app/widget/dist/widget.js"),
    Path(__file__).resolve().parent.parent.parent.parent / "widget" / "dist" / "widget.js",
    Path("widget/dist/widget.js"),
]


def resolve_widget_file() -> Optional[Path]:
    for candidate in WIDGET_CANDIDATE_PATHS:
        if candidate.exists():
            return candidate
    return None


@app.get("/widget/v1/widget.js")
async def serve_widget_js():
    file_path = resolve_widget_file()
    if file_path:
        return FileResponse(
            str(file_path),
            media_type="application/javascript",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    return Response(
        content="// Widget bundle not found.",
        media_type="application/javascript",
        status_code=404,
    )
