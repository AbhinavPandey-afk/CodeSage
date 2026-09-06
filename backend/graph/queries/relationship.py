"""Finds the real structural connection between two symbols in the graph —
the deterministic evidence for the "explain relationship" feature. The
graph traversal here is the only source of truth for whether/how two
symbols connect (CLAUDE.md §44); ai/retrieval/relationship_service.py only
narrates what this module found.
"""
from dataclasses import dataclass

from graph.neo4j.client import get_driver

_MAX_PATH_HOPS = 6
_DIRECT_REL_TYPES = "CALLS|IMPORTS|INHERITS|CONTAINS"
# IMPORTS is excluded from multi-hop traversal: two files that happen to both
# import the same module aren't architecturally "related" the way a call or
# inheritance chain is, and including it drowns out the real connection with
# spurious shared-import paths. CONTAINS is kept only to descend from a
# selected File/Class into its members and back up to the other endpoint.
_PATH_REL_TYPES = "CALLS|INHERITS|CONTAINS"


class SymbolNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class SymbolRef:
    uid: str
    symbol_type: str
    qualified_name: str
    file_path: str


@dataclass(frozen=True)
class RelationshipStep:
    from_qualified_name: str
    to_qualified_name: str
    relationship_type: str
    source_file: str | None
    source_line: int | None
    confidence: float | None


@dataclass(frozen=True)
class RelationshipResult:
    source: SymbolRef
    target: SymbolRef
    connected: bool
    steps: list[RelationshipStep]


def _step_from_row(row: dict, source: SymbolRef, target: SymbolRef) -> RelationshipStep:
    forward = row["start_uid"] == source.uid
    return RelationshipStep(
        from_qualified_name=source.qualified_name if forward else target.qualified_name,
        to_qualified_name=target.qualified_name if forward else source.qualified_name,
        relationship_type=row["rel_type"],
        source_file=row["source_file"],
        source_line=row["source_line"],
        confidence=row["confidence"],
    )


def find_relationship(repo_id: str, source_uid: str, target_uid: str) -> RelationshipResult:
    with get_driver().session() as session:
        node_row = session.run(
            "MATCH (a:Symbol {uid: $source_uid, repo_id: $repo_id}), "
            "(b:Symbol {uid: $target_uid, repo_id: $repo_id}) "
            "RETURN a.uid AS a_uid, a.symbol_type AS a_type, a.qualified_name AS a_qname, "
            "a.file_path AS a_file, b.uid AS b_uid, b.symbol_type AS b_type, "
            "b.qualified_name AS b_qname, b.file_path AS b_file",
            source_uid=source_uid, target_uid=target_uid, repo_id=repo_id,
        ).single()
        if node_row is None:
            raise SymbolNotFoundError("One or both selected nodes were not found in this repository.")

        source = SymbolRef(node_row["a_uid"], node_row["a_type"], node_row["a_qname"], node_row["a_file"])
        target = SymbolRef(node_row["b_uid"], node_row["b_type"], node_row["b_qname"], node_row["b_file"])

        direct_rows = session.run(
            f"MATCH (a:Symbol {{uid: $source_uid, repo_id: $repo_id}})"
            f"-[r:{_DIRECT_REL_TYPES}]-"
            "(b:Symbol {uid: $target_uid, repo_id: $repo_id}) "
            "RETURN type(r) AS rel_type, startNode(r).uid AS start_uid, "
            "r.source_file AS source_file, r.source_line AS source_line, r.confidence AS confidence",
            source_uid=source_uid, target_uid=target_uid, repo_id=repo_id,
        ).data()

        if direct_rows:
            steps = [_step_from_row(r, source, target) for r in direct_rows]
            return RelationshipResult(source=source, target=target, connected=True, steps=steps)

        path_row = session.run(
            "MATCH p = shortestPath((a:Symbol {uid: $source_uid, repo_id: $repo_id})"
            f"-[:{_PATH_REL_TYPES}*1..{_MAX_PATH_HOPS}]-"
            "(b:Symbol {uid: $target_uid, repo_id: $repo_id})) "
            "WHERE all(n IN nodes(p) WHERE n:Symbol) "
            "RETURN [n IN nodes(p) | {uid: n.uid, qualified_name: n.qualified_name}] AS path_nodes, "
            "[r IN relationships(p) | {rel_type: type(r), start_uid: startNode(r).uid, "
            "source_file: r.source_file, source_line: r.source_line, confidence: r.confidence}] AS path_rels",
            source_uid=source_uid, target_uid=target_uid, repo_id=repo_id,
        ).single()

        if path_row is None or not path_row["path_rels"]:
            return RelationshipResult(source=source, target=target, connected=False, steps=[])

        path_nodes = path_row["path_nodes"]
        names_by_uid = {n["uid"]: n["qualified_name"] for n in path_nodes}
        steps = []
        for i, r in enumerate(path_row["path_rels"]):
            a_uid, b_uid = path_nodes[i]["uid"], path_nodes[i + 1]["uid"]
            forward = r["start_uid"] == a_uid
            steps.append(
                RelationshipStep(
                    from_qualified_name=names_by_uid[a_uid if forward else b_uid],
                    to_qualified_name=names_by_uid[b_uid if forward else a_uid],
                    relationship_type=r["rel_type"],
                    source_file=r["source_file"],
                    source_line=r["source_line"],
                    confidence=r["confidence"],
                )
            )
        return RelationshipResult(source=source, target=target, connected=True, steps=steps)
