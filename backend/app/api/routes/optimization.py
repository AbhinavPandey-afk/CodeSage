"""GET /api/repositories/{id}/optimization — proposed architecture improvements
(CLAUDE.md §19/§20/§26/§44). A recommendation only; never modifies the repository."""
from fastapi import APIRouter, HTTPException

from analysis.optimization.engine import generate_optimization_report
from app.models.repository import RepositoryStatus
from app.repositories.repository_store import repository_store
from app.schemas.optimization import (
    OptimizationProposalResponse,
    OptimizationReportResponse,
    RepresentativeImpactResponse,
)

router = APIRouter(prefix="/api/repositories", tags=["optimization"])


def _proposal_response(p) -> OptimizationProposalResponse:
    return OptimizationProposalResponse(
        id=p.id, goal=p.goal, problem=p.problem, evidence=p.evidence,
        proposed_change=p.proposed_change, expected_benefit=p.expected_benefit,
        potential_risk=p.potential_risk, risk_level=p.risk_level,
        confidence=p.confidence, confidence_label=p.confidence_label,
        affected_components=p.affected_components, affected_files=p.affected_files,
        representative_impact=(
            RepresentativeImpactResponse(**p.representative_impact.__dict__)
            if p.representative_impact is not None else None
        ),
        finding_id=p.finding_id,
    )


@router.get("/{repo_id}/optimization", response_model=OptimizationReportResponse)
def get_optimization(repo_id: str) -> OptimizationReportResponse:
    record = repository_store.get(repo_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Repository not found.")
    if record.status != RepositoryStatus.READY:
        raise HTTPException(status_code=409, detail=f"Repository is not ready yet (status: {record.status.value}).")

    report = generate_optimization_report(repo_id)
    return OptimizationReportResponse(
        repo_id=report.repo_id,
        current_architecture_summary=report.current_architecture_summary,
        proposals=[_proposal_response(p) for p in report.proposals],
        detection_notes=report.detection_notes,
    )
