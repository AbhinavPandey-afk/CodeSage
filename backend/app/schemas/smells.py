"""Response contract for GET /api/repositories/{id}/smells."""
from pydantic import BaseModel


class AffectedSymbolResponse(BaseModel):
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int


class SmellResponse(BaseModel):
    smell_type: str
    severity: str
    title: str
    explanation: str
    evidence: str
    affected: list[AffectedSymbolResponse]
