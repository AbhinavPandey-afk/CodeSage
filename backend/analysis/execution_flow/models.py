"""Output model for Execution Flow Reconstruction (CLAUDE.md §21/§22/§39).

Purely static: every OBSERVED hop is a resolved CALLS edge from the graph,
carrying the same file/line/confidence provenance used everywhere else. A
PROPOSED hop is a design projection derived from Architecture Optimization's
layer-skip findings -- it is a synthetic node with no source location, and
is never presented as observed runtime behavior (CLAUDE.md §39's "never
claim this definitely happens at runtime" rule). Every hop's `label` field
makes the distinction explicit rather than leaving it to prose.

`terminal_kind` and `terminal_reason` answer two different questions and
must not be conflated (a regression this module used to have): `terminal_kind`
is the reconstructed Architecture *role* of the callee ("database" /
"external_service" / None) -- purely descriptive, for badges/coloring.
`terminal_reason` is why traversal actually stopped at this hop -- it is None
whenever the hop has children, and otherwise one of NO_RESOLVED_CALLEES,
STANDARD_LIBRARY, EXTERNAL_DEPENDENCY, UNRESOLVED, DEPTH_LIMIT, BRANCH_LIMIT,
or CONFIGURED_BOUNDARY. A component classified `external_integration` can
still have further resolved calls *within this same repository* (e.g. Flask's
own `templating.render_template` calling deeper into Flask's own source) --
traversal now follows those regardless of architectural role, and only
reports a component's role as informational context.
"""
from dataclasses import dataclass, field

FlowLabel = str  # "OBSERVED" | "PROPOSED"
TerminalReason = str  # see module docstring for the full enumeration


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
    # Why traversal stopped here -- None whenever `children` is non-empty.
    terminal_reason: TerminalReason | None = None
    # How many additional resolved calls this symbol has beyond the ones
    # included below, cut by the per-hop branch cap (_MAX_BRANCHES_PER_HOP) --
    # disclosed rather than silently dropped (CLAUDE.md-adjacent "never hide
    # evidence" rule).
    children_omitted: int = 0
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
