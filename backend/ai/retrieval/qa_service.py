"""Orchestrates the full hybrid retrieval -> evidence fusion -> LLM pipeline
described in CLAUDE.md §8: Question -> vector search + graph search -> evidence
fusion -> LLM -> structured, evidence-backed answer.
"""
from dataclasses import dataclass

from ai.llm.base import ChatMessage
from ai.llm.factory import get_llm_provider
from ai.prompts.qa_prompt import build_messages
from ai.retrieval.evidence import EvidenceItem, compute_confidence, gather_evidence, render_evidence_block
from embeddings.registry import get_store

_TOP_K = 8


class RepositoryNotReadyError(RuntimeError):
    pass


@dataclass(frozen=True)
class AskResult:
    answer: str
    confidence_score: float
    confidence_label: str
    evidence: list[EvidenceItem]


def ask(repo_id: str, question: str) -> AskResult:
    store = get_store(repo_id)
    if store is None:
        raise RepositoryNotReadyError(
            "This repository has no vector index yet — analysis may still be running."
        )

    hits = store.search(question, top_k=_TOP_K)
    evidence = gather_evidence(hits)
    evidence_block = render_evidence_block(evidence)
    confidence_score, confidence_label = compute_confidence(hits, evidence)

    messages: list[ChatMessage] = build_messages(question, evidence_block)
    answer = get_llm_provider().generate(messages)

    return AskResult(
        answer=answer,
        confidence_score=confidence_score,
        confidence_label=confidence_label,
        evidence=evidence,
    )
