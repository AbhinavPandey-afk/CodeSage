"""Request/response contracts for POST /api/repositories/{id}/ask."""
from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str


class RelatedSymbolResponse(BaseModel):
    relationship_type: str
    direction: str
    qualified_name: str
    file_path: str
    start_line: int
    confidence: float


class EvidenceResponseItem(BaseModel):
    symbol_type: str
    name: str
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int
    relevance: float
    related: list[RelatedSymbolResponse]


class AskResponse(BaseModel):
    answer: str
    confidence_score: float
    confidence_label: str
    evidence: list[EvidenceResponseItem]
