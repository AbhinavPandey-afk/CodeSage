"""FAISS-backed vector store using TF-IDF vectors.

A neural embedding model (e.g. via sentence-transformers) would rank semantic
similarity better, but pulls in a heavy, network-fetched model download. For
the current milestone TF-IDF + FAISS exact search gives fast, dependency-light,
fully-offline retrieval at the symbol counts real repos produce; swapping in a
neural encoder later only means writing another VectorStore, per CLAUDE.md §7.
"""
import faiss
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from embeddings.vector_store.base import EmbeddingItem, SearchHit, VectorStore


class TfidfFaissStore(VectorStore):
    def __init__(self) -> None:
        self._vectorizer = TfidfVectorizer(max_features=4096, stop_words="english")
        self._index: faiss.IndexFlatIP | None = None
        self._items: list[EmbeddingItem] = []

    def build(self, items: list[EmbeddingItem]) -> None:
        self._items = items
        if not items:
            self._index = None
            return
        matrix = self._vectorizer.fit_transform([it.text for it in items]).astype("float32").toarray()
        faiss.normalize_L2(matrix)
        self._index = faiss.IndexFlatIP(matrix.shape[1])
        self._index.add(matrix)

    def search(self, query: str, top_k: int = 8) -> list[SearchHit]:
        if self._index is None or not self._items:
            return []
        query_vec = self._vectorizer.transform([query]).astype("float32").toarray()
        faiss.normalize_L2(query_vec)
        scores, indices = self._index.search(query_vec, min(top_k, len(self._items)))
        hits = []
        for idx, score in zip(indices[0], scores[0]):
            if idx == -1:
                continue
            hits.append(SearchHit(item=self._items[idx], score=float(score)))
        return hits
