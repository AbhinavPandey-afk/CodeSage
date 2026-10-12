"""Contracts for POST /api/repositories/{id}/graph/relationship."""
from typing import Literal

from pydantic import BaseModel


class RelationshipRequest(BaseModel):
    source_uid: str
    target_uid: str


class SymbolRefResponse(BaseModel):
    uid: str
    symbol_type: str
    qualified_name: str
    file_path: str


class RelationshipStepResponse(BaseModel):
    from_qualified_name: str
    to_qualified_name: str
    relationship_type: str
    source_file: str | None
    source_line: int | None
    confidence: float | None


class RelationshipResponse(BaseModel):
    source: SymbolRefResponse
    target: SymbolRefResponse
    connected: bool
    steps: list[RelationshipStepResponse]
    explanation: str
    # Additive (CLAUDE.md §44/§37: OBSERVED structural fact, never inferred
    # from steps.length alone — a DIRECT pair can have >1 parallel edge).
    # None when `connected` is False.
    relationship_kind: Literal["DIRECT", "INDIRECT"] | None = None
    hop_count: int | None = None
