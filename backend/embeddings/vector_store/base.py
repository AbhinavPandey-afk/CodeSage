"""Vector store abstraction. CLAUDE.md §7/§25: FAISS is the initial choice,
kept behind this interface so it can be swapped without touching retrieval.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingItem:
    """One embeddable unit, always traceable back to a graph symbol (CLAUDE.md §7)."""

    symbol_uid: str
    text: str
    symbol_type: str
    name: str
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class SearchHit:
    item: EmbeddingItem
    score: float


class VectorStore(ABC):
    @abstractmethod
    def build(self, items: list[EmbeddingItem]) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, top_k: int = 8) -> list[SearchHit]:
        raise NotImplementedError
