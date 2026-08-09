"""The single place that knows which concrete LLMProvider is active."""
from functools import lru_cache

from ai.llm.base import LLMProvider
from ai.llm.groq_provider import GroqProvider
from app.core.config import settings


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    return GroqProvider(api_key=settings.groq_api_key, model=settings.groq_model)
