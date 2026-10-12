"""Response contract for GET /api/repositories/{id}/smells.

V2 (Architecture Analysis analytical hardening): all new fields are
additive -- nothing existing was renamed or removed (id/confidence are
non-optional because the backend now always sets them; context_flags,
evidence_details, related_finding_ids default to an empty list;
optimization_supported defaults to False)."""
from pydantic import BaseModel


class AffectedSymbolResponse(BaseModel):
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int


class EvidenceRelationshipResponse(BaseModel):
    source: str
    target: str
    relationship_type: str
    source_file: str | None = None
    source_line: int | None = None
    resolver_confidence: float | None = None
    source_role: str | None = None
    target_role: str | None = None


class SmellResponse(BaseModel):
    id: str
    smell_type: str
    severity: str
    confidence: float
    title: str
    explanation: str
    evidence: str
    affected: list[AffectedSymbolResponse]
    context_flags: list[str] = []
    evidence_details: list[EvidenceRelationshipResponse] = []
    optimization_supported: bool = False
    related_finding_ids: list[str] = []
