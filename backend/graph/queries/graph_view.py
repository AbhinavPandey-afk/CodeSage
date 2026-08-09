"""Architecture-level graph view for the frontend explorer (CLAUDE.md §15/§22).

Rendering all ~2-3k raw symbols of a real repo is unreadable, so this returns
File and Class nodes only — the "Component View" granularity — with:
  - CONTAINS   File -> Class
  - INHERITS   Class -> Class
  - USES       Class -> Class, aggregated (with a call count) from every
               Method-level CALLS edge between the two classes' methods

Nodes are ranked by degree (how connected they are) and capped at `limit`,
so the graph shown is the most structurally significant part of the repo,
not an arbitrary slice.
"""
from dataclasses import dataclass

from graph.neo4j.client import get_driver

_DEFAULT_LIMIT = 150


@dataclass(frozen=True)
class GraphNode:
    uid: str
    symbol_type: str
    name: str
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int
    degree: int


@dataclass(frozen=True)
class GraphEdge:
    source_uid: str
    target_uid: str
    relationship_type: str
    weight: float


@dataclass(frozen=True)
class GraphView:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    truncated: bool


def get_architecture_graph(repo_id: str, limit: int = _DEFAULT_LIMIT) -> GraphView:
    # Test code is real structure but not "architecture" — including it lets
    # high-fan-out test files dominate the degree ranking and crowd out the
    # production classes a developer actually wants to see by default.
    not_test_clause = "NOT toLower(s.file_path) CONTAINS 'test'"

    with get_driver().session() as session:
        total = session.run(
            f"MATCH (s:Symbol {{repo_id: $repo_id}}) WHERE (s:File OR s:Class) AND {not_test_clause} "
            "RETURN count(s) AS n",
            repo_id=repo_id,
        ).single()["n"]

        node_rows = session.run(
            f"MATCH (s:Symbol {{repo_id: $repo_id}}) WHERE (s:File OR s:Class) AND {not_test_clause} "
            "OPTIONAL MATCH (s)-[r]-() "
            "WITH s, count(r) AS degree "
            "RETURN s.uid AS uid, s.symbol_type AS symbol_type, s.name AS name, "
            "s.qualified_name AS qualified_name, s.file_path AS file_path, "
            "s.start_line AS start_line, s.end_line AS end_line, degree "
            "ORDER BY degree DESC LIMIT $limit",
            repo_id=repo_id, limit=limit,
        ).data()

        nodes = [
            GraphNode(
                uid=r["uid"], symbol_type=r["symbol_type"], name=r["name"],
                qualified_name=r["qualified_name"], file_path=r["file_path"],
                start_line=r["start_line"], end_line=r["end_line"], degree=r["degree"],
            )
            for r in node_rows
        ]
        uids = [n.uid for n in nodes]
        if not uids:
            return GraphView(nodes=[], edges=[], truncated=False)

        contains_rows = session.run(
            "MATCH (f:File {repo_id: $repo_id})-[:CONTAINS]->(c:Class) "
            "WHERE f.uid IN $uids AND c.uid IN $uids "
            "RETURN f.uid AS src, c.uid AS dst",
            repo_id=repo_id, uids=uids,
        ).data()

        inherits_rows = session.run(
            "MATCH (c1:Class {repo_id: $repo_id})-[:INHERITS]->(c2:Class) "
            "WHERE c1.uid IN $uids AND c2.uid IN $uids "
            "RETURN c1.uid AS src, c2.uid AS dst",
            repo_id=repo_id, uids=uids,
        ).data()

        uses_rows = session.run(
            "MATCH (c1:Class {repo_id: $repo_id})-[:CONTAINS]->(:Method)-[:CALLS]->(:Method)<-[:CONTAINS]-(c2:Class {repo_id: $repo_id}) "
            "WHERE c1.uid IN $uids AND c2.uid IN $uids AND c1 <> c2 "
            "WITH c1, c2, count(*) AS weight "
            "RETURN c1.uid AS src, c2.uid AS dst, weight",
            repo_id=repo_id, uids=uids,
        ).data()

    edges = (
        [GraphEdge(r["src"], r["dst"], "CONTAINS", 1.0) for r in contains_rows]
        + [GraphEdge(r["src"], r["dst"], "INHERITS", 1.0) for r in inherits_rows]
        + [GraphEdge(r["src"], r["dst"], "USES", float(r["weight"])) for r in uses_rows]
    )

    return GraphView(nodes=nodes, edges=edges, truncated=total > len(nodes))
