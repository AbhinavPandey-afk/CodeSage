"""POST /api/repositories/{id}/ask — evidence-backed Q&A over an ingested repo."""
from fastapi import APIRouter, HTTPException

from ai.retrieval.qa_service import RepositoryNotReadyError, ask as run_ask
from app.repositories.repository_store import repository_store
from app.schemas.ask import AskRequest, AskResponse, EvidenceResponseItem, RelatedSymbolResponse

router = APIRouter(prefix="/api/repositories", tags=["ask"])


@router.post("/{repo_id}/ask", response_model=AskResponse)
def ask_repository(repo_id: str, req: AskRequest) -> AskResponse:
    record = repository_store.get(repo_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Repository not found.")

    try:
        result = run_ask(repo_id, req.question)
    except RepositoryNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return AskResponse(
        answer=result.answer,
        confidence_score=result.confidence_score,
        confidence_label=result.confidence_label,
        evidence=[
            EvidenceResponseItem(
                symbol_type=e.symbol_type, name=e.name, qualified_name=e.qualified_name,
                file_path=e.file_path, start_line=e.start_line, end_line=e.end_line,
                relevance=e.relevance,
                related=[
                    RelatedSymbolResponse(
                        relationship_type=r.relationship_type, direction=r.direction,
                        qualified_name=r.qualified_name, file_path=r.file_path,
                        start_line=r.start_line, confidence=r.confidence,
                    )
                    for r in e.related
                ],
            )
            for e in result.evidence
        ],
    )
