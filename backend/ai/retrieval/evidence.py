"""Evidence fusion + deterministic confidence scoring (CLAUDE.md §11).

The confidence score is never asked of the LLM — it is computed here from two
measurable signals only:
  1. vector_component — how well the question matched retrieved symbols (TF-IDF cosine, 0-1)
  2. graph_component  — whether those symbols have at least one structurally
                         resolved (high-confidence) relationship corroborating them
"""
from dataclasses import dataclass

from ai.retrieval.graph_context import RelatedSymbol, get_symbol_context
from embeddings.vector_store.base import SearchHit

_TOP_N_FOR_PROMPT = 6
_HIGH_CONFIDENCE_EDGE = 0.7
_CONFIRMED_THRESHOLD = 0.55
_INFERRED_THRESHOLD = 0.30


@dataclass(frozen=True)
class EvidenceItem:
    symbol_type: str
    name: str
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int
    relevance: float
    related: list[RelatedSymbol]


def gather_evidence(hits: list[SearchHit]) -> list[EvidenceItem]:
    items = []
    for hit in hits[:_TOP_N_FOR_PROMPT]:
        context = get_symbol_context(hit.item.symbol_uid)
        items.append(
            EvidenceItem(
                symbol_type=hit.item.symbol_type, name=hit.item.name,
                qualified_name=hit.item.qualified_name, file_path=hit.item.file_path,
                start_line=hit.item.start_line, end_line=hit.item.end_line,
                relevance=hit.score, related=context,
            )
        )
    return items


def render_evidence_block(items: list[EvidenceItem]) -> str:
    blocks = []
    for i, item in enumerate(items, start=1):
        related_lines = [
            f"  - {r.relationship_type} ({r.direction}) {r.qualified_name} "
            f"[{r.file_path}:{r.start_line}] (confidence {r.confidence:.2f})"
            for r in item.related
        ]
        related_text = "\n".join(related_lines) if related_lines else "  (no recorded relationships)"
        blocks.append(
            f"[{i}] {item.symbol_type} {item.qualified_name}\n"
            f"    location: {item.file_path}:{item.start_line}-{item.end_line}\n"
            f"    relationships:\n{related_text}"
        )
    return "\n\n".join(blocks) if blocks else "(no matching evidence found in the repository)"


def compute_confidence(hits: list[SearchHit], evidence: list[EvidenceItem]) -> tuple[float, str]:
    if not hits:
        return 0.0, "Uncertain"

    top = hits[: min(3, len(hits))]
    vector_component = sum(h.score for h in top) / len(top)

    graph_component = 0.0
    for item in evidence:
        if any(r.confidence >= _HIGH_CONFIDENCE_EDGE for r in item.related):
            graph_component = 0.2
            break
        if item.related:
            graph_component = max(graph_component, 0.05)

    score = min(1.0, vector_component + graph_component)
    if score >= _CONFIRMED_THRESHOLD:
        label = "Confirmed"
    elif score >= _INFERRED_THRESHOLD:
        label = "Inferred"
    else:
        label = "Uncertain"
    return score, label
