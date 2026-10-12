"""GET /api/repositories/{id}/architecture — reconstructed architecture (CLAUDE.md §15/§44)."""
from fastapi import APIRouter, HTTPException

from analysis.reconstruction.engine import reconstruct_architecture
from analysis.reconstruction.models import ArchitectureComponent
from app.models.repository import RepositoryStatus
from app.repositories.repository_store import repository_store
from app.schemas.architecture import (
    ArchitectureComponentResponse,
    ArchitectureModelResponse,
    ComponentRelationshipResponse,
    ThirdPartyDependencyResponse,
)

router = APIRouter(prefix="/api/repositories", tags=["architecture"])


def _component_response(c: ArchitectureComponent) -> ArchitectureComponentResponse:
    # **c.__dict__ can't cross frozen-dataclass -> Pydantic automatically for
    # the nested third_party_dependencies list, so build it explicitly (same
    # pattern app/api/routes/flows.py uses for FlowHop's nested children).
    return ArchitectureComponentResponse(
        id=c.id, name=c.name, role=c.role, file_count=c.file_count, symbol_count=c.symbol_count,
        files=c.files, confidence=c.confidence, confidence_label=c.confidence_label, evidence=c.evidence,
        third_party_dependencies=[
            ThirdPartyDependencyResponse(name=d.name, category=d.category) for d in c.third_party_dependencies
        ],
    )


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
        components=[_component_response(c) for c in model.components],
        relationships=[ComponentRelationshipResponse(**r.__dict__) for r in model.relationships],
        truncated=model.truncated,
        detection_notes=model.detection_notes,
    )
