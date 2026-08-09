"""LLMProvider — the only interface the rest of the app is allowed to reason
against. No module outside ai/llm/ may import a provider SDK directly
(CLAUDE.md §9/§43): swapping Groq for xAI Grok, or anything else, later means
adding one class here.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, messages: list[ChatMessage], *, temperature: float = 0.2, max_tokens: int = 1024) -> str:
        raise NotImplementedError
