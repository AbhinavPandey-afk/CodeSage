"""Response contract for GET /api/repositories/{id}/optimization (CLAUDE.md §19/§44)."""
from pydantic import BaseModel


class RepresentativeImpactResponse(BaseModel):
    symbol_qualified_name: str
    direct_dependents: int
    indirect_dependents: int
    risk_level: str


class OptimizationProposalResponse(BaseModel):
    id: str
    goal: str
    problem: str
    evidence: str
    proposed_change: str
    expected_benefit: str
    potential_risk: str
    risk_level: str
    confidence: float
    confidence_label: str
    affected_components: list[str]
    affected_files: list[str]
    representative_impact: RepresentativeImpactResponse | None
    # Additive (V2 §15): stable link to the /smells finding this proposal
    # was generated from, replacing the previous implicit title-string
    # correlation. None for a proposal not derived from a single finding.
    finding_id: str | None = None


class OptimizationReportResponse(BaseModel):
    repo_id: str
    current_architecture_summary: str
    proposals: list[OptimizationProposalResponse]
    detection_notes: list[str]
