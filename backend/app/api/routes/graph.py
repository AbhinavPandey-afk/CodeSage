"""GET /api/repositories/{id}/graph — architecture-level graph for visualization."""
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.models.repository import RepositoryStatus
from app.repositories.repository_store import repository_store
from app.schemas.graph import GraphEdgeResponse, GraphNodeResponse, GraphViewResponse
from graph.queries.graph_view import get_class_level_graph, get_file_level_graph

router = APIRouter(prefix="/api/repositories", tags=["graph"])


@router.get("/{repo_id}/graph", response_model=GraphViewResponse)
def get_graph(
    repo_id: str,
    granularity: Literal["files", "classes"] = "files",
    limit: int | None = Query(default=None, ge=1, le=500),
) -> GraphViewResponse:
    record = repository_store.get(repo_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Repository not found.")
    if record.status != RepositoryStatus.READY:
        raise HTTPException(status_code=409, detail=f"Repository is not ready yet (status: {record.status.value}).")

    if granularity == "files":
        view = get_file_level_graph(repo_id, limit=limit) if limit else get_file_level_graph(repo_id)
    else:
        view = get_class_level_graph(repo_id, limit=limit) if limit else get_class_level_graph(repo_id)

    return GraphViewResponse(
        nodes=[GraphNodeResponse(**n.__dict__) for n in view.nodes],
        edges=[GraphEdgeResponse(**e.__dict__) for e in view.edges],
        truncated=view.truncated,
    )
