"""Output model for the architectural smell detector (CLAUDE.md §16).

Every smell is produced by a deterministic, measurable rule -- never an LLM
judgment call -- and carries the evidence that triggered it so a developer can
verify the finding directly in the source.

V2 (Architecture Analysis analytical hardening) adds the distinction this
model previously lacked: an OBSERVED STRUCTURAL CONDITION (the graph fact --
severity, evidence, affected) is not the same thing as an ARCHITECTURAL
INTERPRETATION (how strongly that condition should be read as a real
problem -- confidence, context_flags). Both are still 100% rule-derived; nothing
here is LLM-generated.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AffectedSymbol:
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class EvidenceRelationship:
    """One structured relationship behind a finding -- the machine-readable
    counterpart to the free-text `evidence` string, so a consumer can render
    real evidence without parsing prose. `resolver_confidence` is the
    cross-file CALL/IMPORT resolver's confidence in *this specific edge*
    (analysis/reconstruction's ComponentRelationship.confidence, or the raw
    CALLS relationship's own `confidence` property) -- deliberately distinct
    from the finding's own `confidence` (see Smell.confidence)."""

    source: str
    target: str
    relationship_type: str
    source_file: str | None = None
    source_line: int | None = None
    resolver_confidence: float | None = None
    # Populated only for component-level findings (architecture_violations.py),
    # where the reconstructed role of each endpoint is itself part of the
    # evidence for why this was classified as a layering issue.
    source_role: str | None = None
    target_role: str | None = None


@dataclass(frozen=True)
class Smell:
    # Stable, content-addressed identifier -- see analysis/smells/context.py's
    # compute_finding_id() for the canonicalization rule. Required (no
    # default) so every construction site states it explicitly.
    id: str
    smell_type: str  # circular_dependency | god_class | large_function | dead_code_candidate | architecture_boundary_violation | layer_skip | circular_component_dependency | excessive_component_coupling
    severity: str  # LOW | MEDIUM | HIGH -- magnitude/importance of the structural condition, if real
    # How strongly the evidence supports reading this condition AS a finding
    # (0.0-1.0) -- see each detector's confidence rule for its formula. This
    # is NEVER resolver confidence copied directly; it is a distinct,
    # documented combination of signals (see architecture_violations.py and
    # detector.py module docstrings).
    confidence: float
    title: str
    explanation: str
    evidence: str
    affected: list[AffectedSymbol] = field(default_factory=list)
    # Deterministic, evidence-derived tags that qualify how the finding
    # should be interpreted -- e.g. "one participant is test infrastructure".
    # Never a subjective/LLM judgment; each flag has a fixed, documented
    # trigger condition. See analysis/smells/context.py for the vocabulary.
    context_flags: list[str] = field(default_factory=list)
    # Structured counterpart of `evidence` -- see EvidenceRelationship.
    evidence_details: list[EvidenceRelationship] = field(default_factory=list)
    # Whether analysis.optimization.engine currently has a deterministic
    # restoration strategy for this finding type. False is an honest
    # "detectable, not (yet) actionable" status, never a fabricated proposal.
    optimization_supported: bool = False
    # IDs of other findings that share the same root entity (e.g. a
    # god_class on `Flask` and a large_function on one of Flask's own
    # methods) -- populated by a post-pass over the full finding list, never
    # used to suppress either finding.
    related_finding_ids: list[str] = field(default_factory=list)
