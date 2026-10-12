"""Response contract for the execution-flow endpoints (CLAUDE.md §21/§22/§44)."""
from pydantic import BaseModel


class EntryPointResponse(BaseModel):
    uid: str
    qualified_name: str
    file_path: str
    start_line: int
    route_hint: str | None


class FlowHopResponse(BaseModel):
    label: str
    caller_qualified_name: str
    callee_qualified_name: str
    callee_uid: str | None
    relationship_type: str
    source_file: str | None
    source_line: int | None
    confidence: float
    terminal_kind: str | None
    callee_file_path: str | None = None
    component_id: str | None = None
    component_role: str | None = None
    component_name: str | None = None
    # Why traversal stopped here -- None whenever `children` is non-empty.
    # One of NO_RESOLVED_CALLEES, STANDARD_LIBRARY, EXTERNAL_DEPENDENCY,
    # UNRESOLVED, DEPTH_LIMIT, BRANCH_LIMIT (see execution_flow/models.py).
    terminal_reason: str | None = None
    # Additional resolved calls from this symbol beyond the branch cap,
    # disclosed rather than silently dropped.
    children_omitted: int = 0
    note: str | None
    children: list["FlowHopResponse"] = []


FlowHopResponse.model_rebuild()


class ExecutionFlowReconstructRequest(BaseModel):
    entry_uid: str


class ExecutionFlowReportResponse(BaseModel):
    repo_id: str
    entry: EntryPointResponse
    observed: FlowHopResponse
    proposed: FlowHopResponse | None
    truncated: bool
    detection_notes: list[str]
