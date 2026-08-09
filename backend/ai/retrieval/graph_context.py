"""Pulls a symbol's immediate graph neighborhood — the structural corroboration
that turns a vector-search hit into evidence, per CLAUDE.md §8 (graph search
used when relationships matter).
"""
from dataclasses import dataclass

from graph.neo4j.client import get_driver

_OUTGOING_LIMIT = 8
_INCOMING_LIMIT = 5


@dataclass(frozen=True)
class RelatedSymbol:
    relationship_type: str
    direction: str  # "outgoing" | "incoming"
    qualified_name: str
    file_path: str
    start_line: int
    confidence: float


def get_symbol_context(uid: str) -> list[RelatedSymbol]:
    with get_driver().session() as session:
        outgoing = session.run(
            "MATCH (s:Symbol {uid: $uid})-[r]->(t:Symbol) "
            "RETURN type(r) AS rel_type, t.qualified_name AS qname, "
            "t.file_path AS file_path, t.start_line AS start_line, r.confidence AS confidence "
            "LIMIT $limit",
            uid=uid, limit=_OUTGOING_LIMIT,
        ).data()
        incoming = session.run(
            "MATCH (caller:Symbol)-[r:CALLS]->(s:Symbol {uid: $uid}) "
            "RETURN caller.qualified_name AS qname, caller.file_path AS file_path, "
            "caller.start_line AS start_line, r.confidence AS confidence "
            "LIMIT $limit",
            uid=uid, limit=_INCOMING_LIMIT,
        ).data()

    related = [
        RelatedSymbol(
            relationship_type=row["rel_type"], direction="outgoing",
            qualified_name=row["qname"], file_path=row["file_path"],
            start_line=row["start_line"], confidence=row["confidence"] or 1.0,
        )
        for row in outgoing
    ]
    related += [
        RelatedSymbol(
            relationship_type="CALLS", direction="incoming",
            qualified_name=row["qname"], file_path=row["file_path"],
            start_line=row["start_line"], confidence=row["confidence"] or 1.0,
        )
        for row in incoming
    ]
    return related
