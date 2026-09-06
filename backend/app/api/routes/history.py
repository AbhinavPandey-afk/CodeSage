"""GET /api/repositories/{id}/history — Historical Reconstruction from the
repository's own Git commit history (CLAUDE.md §27/§28/§44)."""
from fastapi import APIRouter, HTTPException

from analysis.history.engine import (
    RepositoryNotFoundError,
    WorkspaceUnavailableError,
    analyze_history,
)
from app.models.repository import RepositoryStatus
from app.repositories.repository_store import repository_store
from app.schemas.history import CommitInfoResponse, ComponentHistoryResponse, HistoryReportResponse

router = APIRouter(prefix="/api/repositories", tags=["history"])


def _component_response(c) -> ComponentHistoryResponse:
    return ComponentHistoryResponse(
        component_id=c.component_id, component_name=c.component_name, role=c.role,
        commit_count=c.commit_count, first_seen=c.first_seen, last_changed=c.last_changed,
        top_authors=c.top_authors, introduction_commit=CommitInfoResponse(**c.introduction_commit.__dict__),
    )


@router.get("/{repo_id}/history", response_model=HistoryReportResponse)
def get_history(repo_id: str) -> HistoryReportResponse:
    record = repository_store.get(repo_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Repository not found.")
    if record.status != RepositoryStatus.READY:
        raise HTTPException(status_code=409, detail=f"Repository is not ready yet (status: {record.status.value}).")

    try:
        report = analyze_history(repo_id)
    except (RepositoryNotFoundError, WorkspaceUnavailableError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return HistoryReportResponse(
        repo_id=report.repo_id, commits_analyzed=report.commits_analyzed,
        history_truncated=report.history_truncated,
        components=[_component_response(c) for c in report.components],
        recent_commits=[CommitInfoResponse(**c.__dict__) for c in report.recent_commits],
        detection_notes=report.detection_notes,
    )
