"""GET /api/repositories/{id}/architecture — reconstructed architecture (CLAUDE.md §15/§44)."""
from fastapi import APIRouter, HTTPException

from analysis.reconstruction.engine import reconstruct_architecture
from app.models.repository import RepositoryStatus
from app.repositories.repository_store import repository_store
from app.schemas.architecture import (
    ArchitectureComponentResponse,
    ArchitectureModelResponse,
    ComponentRelationshipResponse,
)

router = APIRouter(prefix="/api/repositories", tags=["architecture"])


@router.get("/{repo_id}/architecture", response_model=ArchitectureModelResponse)
def get_architecture(repo_id: str) -> ArchitectureModelResponse:
    record = repository_store.get(repo_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Repository not found.")
    if record.status != RepositoryStatus.READY:
        raise HTTPException(status_code=409, detail=f"Repository is not ready yet (status: {record.status.value}).")

    model = reconstruct_architecture(repo_id)
    return ArchitectureModelResponse(
        repo_id=model.repo_id,
        components=[ArchitectureComponentResponse(**c.__dict__) for c in model.components],
        relationships=[ComponentRelationshipResponse(**r.__dict__) for r in model.relationships],
        truncated=model.truncated,
        detection_notes=model.detection_notes,
    )
