"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import ask, health, repositories, smells
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
    allow_origins=["http://localhost:5173", "http://localhost:3000"] if settings.app_env == "development" else [],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(repositories.router)
app.include_router(ask.router)
app.include_router(smells.router)
