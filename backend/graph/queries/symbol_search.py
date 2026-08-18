"""Symbol search, used to power the impact-analysis target picker — the
knowledge-graph view only renders a capped subset of symbols, so users need
a way to find a specific function/class/file that isn't currently on screen.
"""
from dataclasses import dataclass

from graph.neo4j.client import get_driver

_SEARCHABLE_TYPES = ["file", "class", "function", "method"]


@dataclass(frozen=True)
class SymbolSearchResult:
    uid: str
    symbol_type: str
    name: str
    qualified_name: str
    file_path: str
    start_line: int


def search_symbols(repo_id: str, query: str, limit: int = 20) -> list[SymbolSearchResult]:
    query = query.strip()
    if not query:
        return []

    with get_driver().session() as session:
        rows = session.run(
            "MATCH (s:Symbol {repo_id: $repo_id}) "
            "WHERE s.symbol_type IN $types AND toLower(s.qualified_name) CONTAINS toLower($q) "
            "RETURN s.uid AS uid, s.symbol_type AS symbol_type, s.name AS name, "
            "s.qualified_name AS qualified_name, s.file_path AS file_path, s.start_line AS start_line "
            "ORDER BY size(s.qualified_name) ASC "
            "LIMIT $limit",
            repo_id=repo_id, types=_SEARCHABLE_TYPES, q=query, limit=limit,
        ).data()

    return [
        SymbolSearchResult(
            uid=r["uid"], symbol_type=r["symbol_type"], name=r["name"],
            qualified_name=r["qualified_name"], file_path=r["file_path"], start_line=r["start_line"],
        )
        for r in rows
    ]


def suggest_symbols(repo_id: str, limit: int = 6) -> list[SymbolSearchResult]:
    """Good starting points for impact analysis: the most-connected non-test
    classes/functions/methods, so a first-time user gets a non-trivial report
    (real dependents) instead of guessing a name and finding nothing."""
    with get_driver().session() as session:
        rows = session.run(
            "MATCH (s:Symbol {repo_id: $repo_id}) "
            "WHERE s.symbol_type IN ['class', 'function', 'method'] "
            "AND NOT toLower(s.file_path) CONTAINS 'test' "
            "OPTIONAL MATCH (s)-[r:CALLS|INHERITS]-() "
            "WITH s, count(r) AS degree "
            "WHERE degree > 0 "
            "RETURN s.uid AS uid, s.symbol_type AS symbol_type, s.name AS name, "
            "s.qualified_name AS qualified_name, s.file_path AS file_path, s.start_line AS start_line "
            "ORDER BY degree DESC "
            "LIMIT $limit",
            repo_id=repo_id, limit=limit,
        ).data()

    return [
        SymbolSearchResult(
            uid=r["uid"], symbol_type=r["symbol_type"], name=r["name"],
            qualified_name=r["qualified_name"], file_path=r["file_path"], start_line=r["start_line"],
        )
        for r in rows
    ]
