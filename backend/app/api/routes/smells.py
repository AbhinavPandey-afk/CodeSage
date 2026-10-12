"""GET /api/repositories/{id}/smells — deterministic architectural smell report."""
from fastapi import APIRouter, HTTPException

from analysis.smells.detector import run_smell_detection
from app.models.repository import RepositoryStatus
from app.repositories.repository_store import repository_store
from app.schemas.smells import AffectedSymbolResponse, EvidenceRelationshipResponse, SmellResponse

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
            id=s.id, smell_type=s.smell_type, severity=s.severity, confidence=s.confidence,
            title=s.title, explanation=s.explanation, evidence=s.evidence,
            affected=[
                AffectedSymbolResponse(
                    qualified_name=a.qualified_name, file_path=a.file_path,
                    start_line=a.start_line, end_line=a.end_line,
                )
                for a in s.affected
            ],
            context_flags=s.context_flags,
            evidence_details=[
                EvidenceRelationshipResponse(
                    source=d.source, target=d.target, relationship_type=d.relationship_type,
                    source_file=d.source_file, source_line=d.source_line,
                    resolver_confidence=d.resolver_confidence,
                    source_role=d.source_role, target_role=d.target_role,
                )
                for d in s.evidence_details
            ],
            optimization_supported=s.optimization_supported,
            related_finding_ids=s.related_finding_ids,
        )
        for s in smells
    ]
