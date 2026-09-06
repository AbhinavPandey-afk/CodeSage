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
