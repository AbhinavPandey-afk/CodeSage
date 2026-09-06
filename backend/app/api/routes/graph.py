"""GET /api/repositories/{id}/graph — architecture-level graph for visualization.
POST .../graph/relationship — explain how two selected nodes are connected."""
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from ai.retrieval.relationship_service import explain_relationship
from app.models.repository import RepositoryStatus
from app.repositories.repository_store import repository_store
from app.schemas.graph import GraphEdgeResponse, GraphNodeResponse, GraphViewResponse
from app.schemas.relationship import (
    RelationshipRequest,
    RelationshipResponse,
    RelationshipStepResponse,
    SymbolRefResponse,
)
from graph.queries.graph_view import get_class_level_graph, get_file_level_graph
from graph.queries.relationship import SymbolNotFoundError

router = APIRouter(prefix="/api/repositories", tags=["graph"])


def _require_ready(repo_id: str):
    record = repository_store.get(repo_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Repository not found.")
    if record.status != RepositoryStatus.READY:
        raise HTTPException(status_code=409, detail=f"Repository is not ready yet (status: {record.status.value}).")


@router.get("/{repo_id}/graph", response_model=GraphViewResponse)
def get_graph(
    repo_id: str,
    granularity: Literal["files", "classes"] = "files",
    limit: int | None = Query(default=None, ge=1, le=500),
) -> GraphViewResponse:
    _require_ready(repo_id)

    if granularity == "files":
        view = get_file_level_graph(repo_id, limit=limit) if limit else get_file_level_graph(repo_id)
    else:
        view = get_class_level_graph(repo_id, limit=limit) if limit else get_class_level_graph(repo_id)

    return GraphViewResponse(
        nodes=[GraphNodeResponse(**n.__dict__) for n in view.nodes],
        edges=[GraphEdgeResponse(**e.__dict__) for e in view.edges],
        truncated=view.truncated,
    )


@router.post("/{repo_id}/graph/relationship", response_model=RelationshipResponse)
def get_relationship(repo_id: str, req: RelationshipRequest) -> RelationshipResponse:
    _require_ready(repo_id)

    try:
        explanation = explain_relationship(repo_id, req.source_uid, req.target_uid)
    except SymbolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    result = explanation.result
    return RelationshipResponse(
        source=SymbolRefResponse(**result.source.__dict__),
        target=SymbolRefResponse(**result.target.__dict__),
        connected=result.connected,
        steps=[RelationshipStepResponse(**s.__dict__) for s in result.steps],
        explanation=explanation.explanation,
    )
