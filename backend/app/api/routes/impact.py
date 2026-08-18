"""GET .../symbols (search) and POST .../impact — CLAUDE.md §19/§37."""
from fastapi import APIRouter, HTTPException, Query

from analysis.impact.engine import SymbolNotFoundError, analyze_impact
from app.models.repository import RepositoryStatus
from app.repositories.repository_store import repository_store
from app.schemas.impact import (
    DependentResponse,
    ExternalDependencyResponse,
    ImpactRequest,
    ImpactResponse,
    RiskSignalResponse,
    SymbolSearchResponse,
)
from graph.queries.symbol_search import search_symbols, suggest_symbols

router = APIRouter(prefix="/api/repositories", tags=["impact"])


def _require_ready(repo_id: str):
    record = repository_store.get(repo_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Repository not found.")
    if record.status != RepositoryStatus.READY:
        raise HTTPException(status_code=409, detail=f"Repository is not ready yet (status: {record.status.value}).")


@router.get("/{repo_id}/symbols", response_model=list[SymbolSearchResponse])
def get_symbols(repo_id: str, q: str = Query(..., min_length=1), limit: int = Query(default=20, ge=1, le=50)):
    _require_ready(repo_id)
    results = search_symbols(repo_id, q, limit=limit)
    return [SymbolSearchResponse(**r.__dict__) for r in results]


@router.get("/{repo_id}/symbols/suggestions", response_model=list[SymbolSearchResponse])
def get_symbol_suggestions(repo_id: str, limit: int = Query(default=6, ge=1, le=20)):
    """Repo-specific starting points for impact analysis — the most-connected
    real symbols in this repository, so the picker never shows a generic
    placeholder example that doesn't exist in whatever repo is loaded."""
    _require_ready(repo_id)
    results = suggest_symbols(repo_id, limit=limit)
    return [SymbolSearchResponse(**r.__dict__) for r in results]


def _dep(d) -> DependentResponse:
    return DependentResponse(**d.__dict__)


@router.post("/{repo_id}/impact", response_model=ImpactResponse)
def post_impact(repo_id: str, req: ImpactRequest) -> ImpactResponse:
    _require_ready(repo_id)
    try:
        report = analyze_impact(repo_id, req.symbol_uid)
    except SymbolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ImpactResponse(
        target_uid=report.target_uid,
        target_qualified_name=report.target_qualified_name,
        target_symbol_type=report.target_symbol_type,
        target_file_path=report.target_file_path,
        direct_dependents=[_dep(d) for d in report.direct_dependents],
        indirect_dependents=[_dep(d) for d in report.indirect_dependents],
        affected_apis=[_dep(d) for d in report.affected_apis],
        affected_services=[_dep(d) for d in report.affected_services],
        affected_tests=[_dep(d) for d in report.affected_tests],
        external_dependencies=[ExternalDependencyResponse(**e.__dict__) for e in report.external_dependencies],
        risk_level=report.risk_level,
        risk_score=report.risk_score,
        risk_signals=[RiskSignalResponse(**s.__dict__) for s in report.risk_signals],
        explanation=report.explanation,
        detection_notes=report.detection_notes,
    )
