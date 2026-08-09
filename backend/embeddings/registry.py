"""In-memory per-repository vector store registry.

Rebuilt on server restart — acceptable for the current milestone since
BackgroundTasks already runs in-process (no separate worker yet). Swapping
to a persisted index is a registry-internal change; callers are unaffected.
"""
import threading

from embeddings.vector_store.base import VectorStore
from embeddings.vector_store.tfidf_store import TfidfFaissStore

_lock = threading.Lock()
_stores: dict[str, VectorStore] = {}


def set_store(repo_id: str, store: VectorStore) -> None:
    with _lock:
        _stores[repo_id] = store


def get_store(repo_id: str) -> VectorStore | None:
    with _lock:
        return _stores.get(repo_id)


def new_store() -> VectorStore:
    return TfidfFaissStore()
