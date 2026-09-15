"""Output model for Execution Flow Reconstruction (CLAUDE.md §21/§22/§39).

Purely static: every OBSERVED hop is a resolved CALLS edge from the graph,
carrying the same file/line/confidence provenance used everywhere else. A
PROPOSED hop is a design projection derived from Architecture Optimization's
layer-skip findings -- it is a synthetic node with no source location, and
is never presented as observed runtime behavior (CLAUDE.md §39's "never
claim this definitely happens at runtime" rule). Every hop's `label` field
makes the distinction explicit rather than leaving it to prose.
"""
from dataclasses import dataclass, field

FlowLabel = str  # "OBSERVED" | "PROPOSED"


@dataclass(frozen=True)
class EntryPoint:
    uid: str
    qualified_name: str
    file_path: str
    start_line: int
    route_hint: str | None


@dataclass(frozen=True)
class FlowHop:
    label: FlowLabel
    caller_qualified_name: str
    callee_qualified_name: str
    callee_uid: str | None
    relationship_type: str  # "ENTRY" | "CALLS" | "PROPOSED_CALL"
    source_file: str | None
    source_line: int | None
    confidence: float
    terminal_kind: str | None  # "database" | "external_service" | None
    # The callee's own file (distinct from source_file/source_line, which is
    # the call-site evidence inside the *caller*) and the reconstructed
    # Architecture component it belongs to -- reused from ArchitectureModel
    # rather than re-derived, so the frontend can group hops into the same
    # API/Service/Data-Access/External layers Architecture Reconstruction
    # already established, without inventing a second classification.
    callee_file_path: str | None = None
    component_id: str | None = None
    component_role: str | None = None
    component_name: str | None = None
    note: str | None = None
    caller_uid: str | None = None  # internal only -- not part of the API response
    children: list["FlowHop"] = field(default_factory=list)


@dataclass(frozen=True)
class ExecutionFlowReport:
    repo_id: str
    entry: EntryPoint
    observed: FlowHop
    proposed: FlowHop | None
    truncated: bool
    detection_notes: list[str] = field(default_factory=list)
