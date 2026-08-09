"""Request/response contracts for the /api/repositories endpoints."""
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.repository import RepositoryStatus


class RepositoryCreateRequest(BaseModel):
    url: str = Field(..., examples=["https://github.com/psf/requests"])


class RepositoryResponse(BaseModel):
    id: str
    url: str
    owner: str
    name: str
    status: RepositoryStatus
    default_branch: str | None
    commit_sha: str | None
    languages: dict[str, int]
    file_count: int
    symbol_count: int
    relationship_count: int
    error: str | None
    created_at: datetime
    updated_at: datetime
