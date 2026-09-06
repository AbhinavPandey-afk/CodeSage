"""Output model for the Architecture Reconstruction engine (CLAUDE.md §15/§16).

The reconstructed architecture is a structured model, not a diagram — every
component and relationship carries the evidence and confidence that produced
it, so visualization, analysis, optimization, and impact analysis can all
consume the same object instead of re-deriving it from the graph.
"""
from dataclasses import dataclass, field

ComponentRole = str  # "api" | "service" | "data_access" | "external_integration" | "model" | "test" | "other"
ConfidenceLabel = str  # "Confirmed" | "Inferred" | "Uncertain"


@dataclass(frozen=True)
class ArchitectureComponent:
    id: str  # stable slug derived from the directory group, e.g. "app/services"
    name: str  # display name, e.g. "app / services"
    role: ComponentRole
    file_count: int
    symbol_count: int
    files: list[str]
    confidence: float
    confidence_label: ConfidenceLabel
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ComponentRelationship:
    source_id: str
    target_id: str
    call_count: int
    confidence: float
    confidence_label: ConfidenceLabel
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ArchitectureModel:
    repo_id: str
    components: list[ArchitectureComponent]
    relationships: list[ComponentRelationship]
    truncated: bool
    detection_notes: list[str] = field(default_factory=list)
