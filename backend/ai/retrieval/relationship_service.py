"""Explains the connection between two symbols a user selects in the graph
explorer. graph.queries.relationship finds the real connecting edges (or
proves there are none); this module only asks the LLM to narrate that
evidence in plain English — never to guess a relationship on its own
(CLAUDE.md §44).
"""
from dataclasses import dataclass

from ai.llm.factory import get_llm_provider
from ai.prompts.relationship_prompt import build_messages
from graph.queries.relationship import RelationshipResult, find_relationship


@dataclass(frozen=True)
class RelationshipExplanation:
    result: RelationshipResult
    explanation: str


def _render_evidence(result: RelationshipResult) -> str:
    lines = [
        f"{result.source.symbol_type} {result.source.qualified_name} ({result.source.file_path})",
        f"{result.target.symbol_type} {result.target.qualified_name} ({result.target.file_path})",
        "",
        "Connection path:",
    ]
    for step in result.steps:
        location = f"{step.source_file}:{step.source_line}" if step.source_file else "location unknown"
        confidence = f"{step.confidence:.2f}" if step.confidence is not None else "n/a"
        lines.append(
            f"  {step.from_qualified_name} -[{step.relationship_type}]-> {step.to_qualified_name} "
            f"(evidence: {location}, confidence {confidence})"
        )
    return "\n".join(lines)


def not_connected_explanation(source_qualified_name: str, target_qualified_name: str) -> str:
    return (
        f"No structural relationship (call, import, inheritance, or containment) connects "
        f"`{source_qualified_name}` and `{target_qualified_name}` in the knowledge graph."
    )


def explain_relationship(repo_id: str, source_uid: str, target_uid: str) -> RelationshipExplanation:
    result = find_relationship(repo_id, source_uid, target_uid)

    if not result.connected:
        return RelationshipExplanation(
            result=result,
            explanation=not_connected_explanation(result.source.qualified_name, result.target.qualified_name),
        )

    evidence_block = _render_evidence(result)
    messages = build_messages(result.source.qualified_name, result.target.qualified_name, evidence_block)
    explanation = get_llm_provider().generate(messages)

    return RelationshipExplanation(result=result, explanation=explanation)
