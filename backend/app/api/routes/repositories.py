"""POST/GET /api/repositories — repository ingestion and status polling."""
from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.repositories.repository_store import repository_store
from app.schemas.repository import RepositoryCreateRequest, RepositoryResponse
from app.services.pipeline import run_analysis_pipeline
from ingestion.github.repository_service import github_repository_service
from ingestion.github.validation import InvalidRepositoryUrlError

router = APIRouter(prefix="/api/repositories", tags=["repositories"])


@router.post("", response_model=RepositoryResponse, status_code=202)
def create_repository(req: RepositoryCreateRequest, background_tasks: BackgroundTasks) -> RepositoryResponse:
    """Register a repository and kick off analysis in the background; returns immediately."""
    try:
        record = github_repository_service.register(req.url)
    except InvalidRepositoryUrlError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    background_tasks.add_task(run_analysis_pipeline, record.id)
    return RepositoryResponse(**record.model_dump())


@router.get("", response_model=list[RepositoryResponse])
def list_repositories() -> list[RepositoryResponse]:
    return [RepositoryResponse(**r.model_dump()) for r in repository_store.list()]


@router.get("/{repo_id}", response_model=RepositoryResponse)
def get_repository(repo_id: str) -> RepositoryResponse:
    record = repository_store.get(repo_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Repository not found.")
    return RepositoryResponse(**record.model_dump())


@router.get("/{repo_id}/status", response_model=RepositoryResponse)
def get_repository_status(repo_id: str) -> RepositoryResponse:
    return get_repository(repo_id)
