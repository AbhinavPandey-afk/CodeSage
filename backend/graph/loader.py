"""IR -> Neo4j: the one place normalized Symbols/Relationships become graph writes.

Every node gets a `uid` = "{repo_id}:{symbol.id}" — the parser's ids are only
unique within a single repository, so uid is the actual Neo4j primary key.
Analysis engines and retrieval should read the graph, never re-derive it.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from graph.neo4j.client import get_driver
from graph.schema.constraints import ensure_schema
from parsing.ir.models import ParsedFile, RelationshipType, Symbol, SymbolType
from parsing.ir.resolver import resolve_relationships

logger = get_logger(__name__)

_BATCH_SIZE = 500

_LABEL_BY_SYMBOL_TYPE = {
    SymbolType.FILE: "File",
    SymbolType.CLASS: "Class",
    SymbolType.FUNCTION: "Function",
    SymbolType.METHOD: "Method",
    SymbolType.IMPORT: "Import",
    SymbolType.VARIABLE: "Variable",
}

_REL_TYPE_CYPHER = {
    RelationshipType.CONTAINS: "CONTAINS",
    RelationshipType.IMPORTS: "IMPORTS",
    RelationshipType.CALLS: "CALLS",
    RelationshipType.INHERITS: "INHERITS",
}


@dataclass
class GraphLoadResult:
    symbol_count: int
    relationship_count: int


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _uid(repo_id: str, symbol_id: str) -> str:
    return f"{repo_id}:{symbol_id}"


def load_repository_graph(
    repo_id: str,
    owner: str,
    name: str,
    url: str,
    default_branch: str | None,
    commit_sha: str | None,
    parsed_files: list[ParsedFile],
) -> GraphLoadResult:
    ensure_schema()

    all_symbols: list[Symbol] = [s for pf in parsed_files for s in pf.symbols]
    all_relationships = resolve_relationships(
        all_symbols, [r for pf in parsed_files for r in pf.relationships]
    )

    driver = get_driver()
    with driver.session() as session:
        session.run(
            "MERGE (r:Repository {id: $id}) "
            "SET r.owner=$owner, r.name=$name, r.url=$url, "
            "r.default_branch=$default_branch, r.commit_sha=$commit_sha",
            id=repo_id, owner=owner, name=name, url=url,
            default_branch=default_branch, commit_sha=commit_sha,
        )

        symbols_by_type: dict[SymbolType, list[dict]] = {}
        for s in all_symbols:
            symbols_by_type.setdefault(s.symbol_type, []).append(
                {
                    "uid": _uid(repo_id, s.id),
                    "id": s.id,
                    "repo_id": repo_id,
                    "symbol_type": s.symbol_type.value,
                    "name": s.name,
                    "qualified_name": s.qualified_name,
                    "file_path": s.file_path,
                    "start_line": s.start_line,
                    "end_line": s.end_line,
                    "language": s.language.value,
                    "decorators": s.decorators,
                    "docstring": s.docstring,
                }
            )

        for symbol_type, rows in symbols_by_type.items():
            label = _LABEL_BY_SYMBOL_TYPE[symbol_type]
            query = (
                f"UNWIND $rows AS row "
                f"MERGE (s:Symbol:{label} {{uid: row.uid}}) "
                f"SET s += row"
            )
            for batch in _chunks(rows, _BATCH_SIZE):
                session.run(query, rows=batch)

        file_uids = [_uid(repo_id, s.id) for s in all_symbols if s.symbol_type == SymbolType.FILE]
        for batch in _chunks(file_uids, _BATCH_SIZE):
            session.run(
                "UNWIND $uids AS uid "
                "MATCH (r:Repository {id: $repo_id}), (f:Symbol {uid: uid}) "
                "MERGE (r)-[:CONTAINS]->(f)",
                uids=batch, repo_id=repo_id,
            )

        relationship_rows_by_type: dict[RelationshipType, list[dict]] = {}
        for rel in all_relationships:
            if rel.target_id is None:
                continue  # unresolved — not a graph edge; the target simply isn't in this repo's IR
            relationship_rows_by_type.setdefault(rel.relationship_type, []).append(
                {
                    "source_uid": _uid(repo_id, rel.source_id),
                    "target_uid": _uid(repo_id, rel.target_id),
                    "source_file": rel.source_file,
                    "source_line": rel.source_line,
                    "confidence": rel.confidence,
                }
            )

        written_relationships = 0
        for rel_type, rows in relationship_rows_by_type.items():
            cypher_type = _REL_TYPE_CYPHER[rel_type]
            query = (
                "UNWIND $rows AS row "
                "MATCH (a:Symbol {uid: row.source_uid}) "
                "MATCH (b:Symbol {uid: row.target_uid}) "
                f"MERGE (a)-[rel:{cypher_type} {{source_line: row.source_line}}]->(b) "
                "SET rel.confidence = row.confidence, rel.source_file = row.source_file"
            )
            for batch in _chunks(rows, _BATCH_SIZE):
                session.run(query, rows=batch)
            written_relationships += len(rows)

    logger.info(
        "graph.loaded",
        repo_id=repo_id,
        symbols=len(all_symbols),
        relationships_written=written_relationships,
        relationships_total=len(all_relationships),
    )
    return GraphLoadResult(symbol_count=len(all_symbols), relationship_count=written_relationships)
