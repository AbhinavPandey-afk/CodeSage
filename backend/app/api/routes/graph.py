"""GET /api/repositories/{id}/graph — architecture-level graph for visualization."""
from fastapi import APIRouter, HTTPException, Query

from app.models.repository import RepositoryStatus
from app.repositories.repository_store import repository_store
from app.schemas.graph import GraphEdgeResponse, GraphNodeResponse, GraphViewResponse
from graph.queries.graph_view import get_architecture_graph

router = APIRouter(prefix="/api/repositories", tags=["graph"])


@router.get("/{repo_id}/graph", response_model=GraphViewResponse)
def get_graph(repo_id: str, limit: int = Query(default=150, ge=1, le=500)) -> GraphViewResponse:
    record = repository_store.get(repo_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Repository not found.")
    if record.status != RepositoryStatus.READY:
        raise HTTPException(status_code=409, detail=f"Repository is not ready yet (status: {record.status.value}).")

    view = get_architecture_graph(repo_id, limit=limit)
    return GraphViewResponse(
        nodes=[GraphNodeResponse(**n.__dict__) for n in view.nodes],
        edges=[GraphEdgeResponse(**e.__dict__) for e in view.edges],
        truncated=view.truncated,
    )
