"""GET /api/repositories/{id}/flows — candidate entry points.
POST /api/repositories/{id}/flows/reconstruct — static execution-flow
reconstruction from a chosen entry point (CLAUDE.md §21/§22/§44)."""
from fastapi import APIRouter, HTTPException

from analysis.execution_flow.engine import EntryPointNotFoundError, detect_entry_points, reconstruct_execution_flow
from analysis.execution_flow.models import FlowHop
from app.models.repository import RepositoryStatus
from app.repositories.repository_store import repository_store
from app.schemas.execution_flow import (
    EntryPointResponse,
    ExecutionFlowReconstructRequest,
    ExecutionFlowReportResponse,
    FlowHopResponse,
)

router = APIRouter(prefix="/api/repositories", tags=["execution_flow"])


def _require_ready(repo_id: str):
    record = repository_store.get(repo_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Repository not found.")
    if record.status != RepositoryStatus.READY:
        raise HTTPException(status_code=409, detail=f"Repository is not ready yet (status: {record.status.value}).")


def _hop_response(hop: FlowHop) -> FlowHopResponse:
    return FlowHopResponse(
        label=hop.label, caller_qualified_name=hop.caller_qualified_name,
        callee_qualified_name=hop.callee_qualified_name, callee_uid=hop.callee_uid,
        relationship_type=hop.relationship_type, source_file=hop.source_file,
        source_line=hop.source_line, confidence=hop.confidence, terminal_kind=hop.terminal_kind,
        callee_file_path=hop.callee_file_path, component_id=hop.component_id,
        component_role=hop.component_role, component_name=hop.component_name,
        terminal_reason=hop.terminal_reason, children_omitted=hop.children_omitted,
        note=hop.note, children=[_hop_response(c) for c in hop.children],
    )


@router.get("/{repo_id}/flows", response_model=list[EntryPointResponse])
def list_entry_points(repo_id: str) -> list[EntryPointResponse]:
    _require_ready(repo_id)
    return [EntryPointResponse(**e.__dict__) for e in detect_entry_points(repo_id)]


@router.post("/{repo_id}/flows/reconstruct", response_model=ExecutionFlowReportResponse)
def reconstruct_flow(repo_id: str, req: ExecutionFlowReconstructRequest) -> ExecutionFlowReportResponse:
    _require_ready(repo_id)
    try:
        report = reconstruct_execution_flow(repo_id, req.entry_uid)
    except EntryPointNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ExecutionFlowReportResponse(
        repo_id=report.repo_id,
        entry=EntryPointResponse(**report.entry.__dict__),
        observed=_hop_response(report.observed),
        proposed=_hop_response(report.proposed) if report.proposed is not None else None,
        truncated=report.truncated,
        detection_notes=report.detection_notes,
    )
