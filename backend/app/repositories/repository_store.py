"""Persistence for repository records.

A JSON-backed store, not a full relational DB — CLAUDE.md calls for a relational
DB to own application metadata (users/jobs/repositories/settings) long-term, but
that is out of scope for the current MVP milestone. The store is written behind
a small interface so swapping in Postgres later does not touch call sites.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from app.core.config import settings
from app.models.repository import RepositoryRecord


class RepositoryStore:
    """Thread-safe CRUD for RepositoryRecord, persisted to a single JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (settings.workspace_dir / "registry.json")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._records: dict[str, RepositoryRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        raw = json.loads(self._path.read_text(encoding="utf-8") or "{}")
        self._records = {rid: RepositoryRecord.model_validate(r) for rid, r in raw.items()}

    def _save(self) -> None:
        payload = {rid: json.loads(r.model_dump_json()) for rid, r in self._records.items()}
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def create(self, record: RepositoryRecord) -> RepositoryRecord:
        with self._lock:
            self._records[record.id] = record
            self._save()
        return record

    def get(self, repo_id: str) -> RepositoryRecord | None:
        with self._lock:
            return self._records.get(repo_id)

    def list(self) -> list[RepositoryRecord]:
        with self._lock:
            return sorted(self._records.values(), key=lambda r: r.created_at, reverse=True)

    def update(self, record: RepositoryRecord) -> RepositoryRecord:
        record.touch()
        with self._lock:
            self._records[record.id] = record
            self._save()
        return record


repository_store = RepositoryStore()
