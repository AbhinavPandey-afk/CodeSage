"""GroqProvider — LLMProvider backed by Groq's OpenAI-compatible chat API.

NOTE: CLAUDE.md names "Grok" (xAI, api.x.ai) as the reference LLM. This build
uses Groq (api.groq.com) instead, per an explicit product decision made when
only a Groq key was available. Because everything above this class talks to
LLMProvider, adding a real GrokProvider later is additive, not a rewrite.
"""
from groq import Groq

from ai.llm.base import ChatMessage, LLMProvider


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set — add it to backend/.env")
        self._client = Groq(api_key=api_key)
        self._model = model

    def generate(self, messages: list[ChatMessage], *, temperature: float = 0.2, max_tokens: int = 1024) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
