"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import ask, graph, health, repositories, smells
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(
    title="CodeSage API",
    description="AI-powered software architecture intelligence platform.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    # Vite auto-increments its port (5173, 5174, ...) whenever the default is
    # already taken, so a fixed origin list breaks the moment a second dev
    # server is running. A localhost-only regex tolerates any port instead.
    allow_origin_regex=r"http://localhost:\d+" if settings.app_env == "development" else None,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(repositories.router)
app.include_router(ask.router)
app.include_router(smells.router)
app.include_router(graph.router)
