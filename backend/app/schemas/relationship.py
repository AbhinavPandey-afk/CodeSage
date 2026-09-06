"""Contracts for POST /api/repositories/{id}/graph/relationship."""
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
