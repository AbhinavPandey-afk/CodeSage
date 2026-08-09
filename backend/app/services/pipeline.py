"""Orchestrates the full repository analysis pipeline as a single background job.

CLAUDE.md §26/§27: analysis must not run inside the request/response cycle.
FastAPI's BackgroundTasks is the v1 "local worker" — the interface (a single
function taking a repo_id) is intentionally what a Celery/RQ task would look
like, so swapping the execution backend later doesn't change this module.
"""
from app.core.logging import get_logger
from app.models.repository import RepositoryStatus
from app.repositories.repository_store import repository_store
from app.services.graph_pipeline import build_graph_for_repository
from ingestion.github.repository_service import github_repository_service

logger = get_logger(__name__)


def run_analysis_pipeline(repo_id: str) -> None:
    """Clone -> parse -> graph -> embed. Each stage persists status as it goes,
    so the frontend can poll GET /api/repositories/{id} for live progress."""
    record = github_repository_service.ingest(repo_id)
    if record.status != RepositoryStatus.CLONED:
        return  # ingest() already recorded the failure reason

    try:
        build_graph_for_repository(repo_id)
    except Exception as exc:
        logger.error("pipeline.graph_stage_failed", repo_id=repo_id, error=str(exc))
        record = repository_store.get(repo_id)
        if record is not None:
            record.status = RepositoryStatus.FAILED
            record.error = f"Graph build failed: {exc}"
            repository_store.update(record)
