"""GET /api/repositories/{id}/smells — deterministic architectural smell report."""
from fastapi import APIRouter, HTTPException

from analysis.smells.detector import run_smell_detection
from app.models.repository import RepositoryStatus
from app.repositories.repository_store import repository_store
from app.schemas.smells import AffectedSymbolResponse, SmellResponse

router = APIRouter(prefix="/api/repositories", tags=["smells"])


@router.get("/{repo_id}/smells", response_model=list[SmellResponse])
def get_smells(repo_id: str) -> list[SmellResponse]:
    record = repository_store.get(repo_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Repository not found.")
    if record.status != RepositoryStatus.READY:
        raise HTTPException(status_code=409, detail=f"Repository is not ready yet (status: {record.status.value}).")

    smells = run_smell_detection(repo_id)
    return [
        SmellResponse(
            smell_type=s.smell_type, severity=s.severity, title=s.title,
            explanation=s.explanation, evidence=s.evidence,
            affected=[
                AffectedSymbolResponse(
                    qualified_name=a.qualified_name, file_path=a.file_path,
                    start_line=a.start_line, end_line=a.end_line,
                )
                for a in s.affected
            ],
        )
        for s in smells
    ]
