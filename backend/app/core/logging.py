"""Structured logging setup — JSON in production, readable console in dev."""
import logging
import sys

import structlog

from app.core.config import settings


def configure_logging() -> None:
    """Wire structlog + stdlib logging to a single structured output stream."""
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=settings.log_level)

    renderer = (
        structlog.dev.ConsoleRenderer()
        if settings.app_env == "development"
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(settings.log_level)),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Fetch a structured logger bound to a component name."""
    return structlog.get_logger(name)
