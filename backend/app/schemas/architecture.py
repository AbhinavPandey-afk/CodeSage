"""Response contract for GET /api/repositories/{id}/architecture (CLAUDE.md §15/§44)."""
from pydantic import BaseModel


class ThirdPartyDependencyResponse(BaseModel):
    name: str
    category: str


class ArchitectureComponentResponse(BaseModel):
    id: str
    name: str
    role: str
    file_count: int
    symbol_count: int
    files: list[str]
    confidence: float
    confidence_label: str
    evidence: list[str]
    third_party_dependencies: list[ThirdPartyDependencyResponse] = []


class ComponentRelationshipResponse(BaseModel):
    source_id: str
    target_id: str
    call_count: int
    confidence: float
    confidence_label: str
    evidence: list[str]


class ArchitectureModelResponse(BaseModel):
    repo_id: str
    components: list[ArchitectureComponentResponse]
    relationships: list[ComponentRelationshipResponse]
    truncated: bool
    detection_notes: list[str]
