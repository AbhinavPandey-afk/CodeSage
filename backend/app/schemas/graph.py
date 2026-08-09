"""Response contract for GET /api/repositories/{id}/graph."""
from pydantic import BaseModel


class GraphNodeResponse(BaseModel):
    uid: str
    symbol_type: str
    name: str
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int
    degree: int


class GraphEdgeResponse(BaseModel):
    source_uid: str
    target_uid: str
    relationship_type: str
    weight: float


class GraphViewResponse(BaseModel):
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]
    truncated: bool
