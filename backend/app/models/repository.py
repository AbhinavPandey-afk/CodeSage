"""Internal domain model for a repository CodeSage has ingested."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class RepositoryStatus(str, Enum):
    PENDING = "pending"
    CLONING = "cloning"
    CLONED = "cloned"
    PARSING = "parsing"
    BUILDING_GRAPH = "building_graph"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"


class RepositoryRecord(BaseModel):
    """Persisted record for one ingested repository (metadata only — no source code)."""

    id: str
    url: str
    owner: str
    name: str
    status: RepositoryStatus = RepositoryStatus.PENDING
    workspace_path: str | None = None
    default_branch: str | None = None
    commit_sha: str | None = None
    languages: dict[str, int] = Field(default_factory=dict)  # language -> file count
    file_count: int = 0
    symbol_count: int = 0
    relationship_count: int = 0
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
