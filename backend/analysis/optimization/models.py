"""Output model for Architecture Optimization (CLAUDE.md §19/§20/§26/§38).

Every proposal maps back to a specific finding from Architecture Analysis --
optimization never runs as a free-standing "redesign this repository" step.
Each one states problem, evidence, proposed change, expected benefit,
potential risk, and confidence, per CLAUDE.md §38. This is a design
recommendation only (CLAUDE.md §19): nothing here modifies the repository.
"""
from dataclasses import dataclass, field

OptimizationGoal = str  # "enforce_layering" | "reduce_circularity" | "reduce_coupling"


@dataclass(frozen=True)
class RepresentativeImpact:
    """A deterministic proxy for "what would changing this actually touch":
    analysis/impact/engine.py run against the most-connected real symbol in
    the affected component(s), per CLAUDE.md §26's "optimization should use
    existing impact analysis" rule. Absent when no such symbol was found."""

    symbol_qualified_name: str
    direct_dependents: int
    indirect_dependents: int
    risk_level: str


@dataclass(frozen=True)
class OptimizationProposal:
    id: str
    goal: OptimizationGoal
    problem: str  # OBSERVED/INFERRED -- restates the Architecture Analysis finding
    evidence: str
    proposed_change: str  # explicitly PROPOSED -- a recommendation, never a fact
    expected_benefit: str
    potential_risk: str
    risk_level: str  # LOW | MEDIUM | HIGH | CRITICAL -- deterministic, never LLM-invented
    confidence: float
    confidence_label: str
    affected_components: list[str]
    affected_files: list[str]
    representative_impact: RepresentativeImpact | None = None


@dataclass(frozen=True)
class OptimizationReport:
    repo_id: str
    current_architecture_summary: str
    proposals: list[OptimizationProposal] = field(default_factory=list)
    detection_notes: list[str] = field(default_factory=list)
