"""Graph views for the frontend explorer (CLAUDE.md §15/§22).

Two granularities, both deliberately restrained rather than dumping the raw
symbol graph (a real repo has thousands of Method/Function nodes, which is
unreadable as a picture):

  - "files"   (default): one node per file, one edge per pair of files with
    at least one cross-file call between symbols they contain. This is the
    "Component View" / module dependency graph — the level a new developer
    actually wants first.
  - "classes": File + Class nodes with CONTAINS/INHERITS/USES edges, for
    drilling into a specific area.

Both exclude test paths (real structure, not architecture), rank by degree
in the *rendered* graph, cap at `limit`, and drop zero-degree nodes — an
isolated box with no lines is noise, not information.
"""
from dataclasses import dataclass

from graph.neo4j.client import get_driver

_DEFAULT_FILE_LIMIT = 60
_DEFAULT_CLASS_LIMIT = 100
_NOT_TEST = "NOT toLower({alias}.file_path) CONTAINS 'test'"


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


def get_file_level_graph(repo_id: str, limit: int = _DEFAULT_FILE_LIMIT) -> GraphView:
    with get_driver().session() as session:
        file_rows = session.run(
            "MATCH (f:File {repo_id: $repo_id}) WHERE " + _NOT_TEST.format(alias="f") + " "
            "RETURN f.uid AS uid, f.name AS name, f.qualified_name AS qualified_name, "
            "f.file_path AS file_path, f.start_line AS start_line, f.end_line AS end_line",
            repo_id=repo_id,
        ).data()
        file_by_path = {r["file_path"]: r for r in file_rows}

        edge_rows = session.run(
            "MATCH (caller:Symbol {repo_id: $repo_id})-[:CALLS]->(callee:Symbol {repo_id: $repo_id}) "
            "WHERE caller.symbol_type IN ['method', 'function'] "
            "AND callee.symbol_type IN ['method', 'function'] "
            "AND caller.file_path <> callee.file_path "
            "AND " + _NOT_TEST.format(alias="caller") + " AND " + _NOT_TEST.format(alias="callee") + " "
            "WITH caller.file_path AS src_file, callee.file_path AS dst_file, count(*) AS weight "
            "RETURN src_file, dst_file, weight",
            repo_id=repo_id,
        ).data()

    degree: dict[str, int] = {}
    edges_by_path: list[tuple[str, str, float]] = []
    for r in edge_rows:
        src, dst = r["src_file"], r["dst_file"]
        if src not in file_by_path or dst not in file_by_path:
            continue
        edges_by_path.append((src, dst, float(r["weight"])))
        degree[src] = degree.get(src, 0) + 1
        degree[dst] = degree.get(dst, 0) + 1

    ranked_paths = sorted(degree, key=lambda p: degree[p], reverse=True)[:limit]
    selected = set(ranked_paths)

    nodes = [
        GraphNode(
            uid=file_by_path[p]["uid"], symbol_type="file", name=file_by_path[p]["name"],
            qualified_name=file_by_path[p]["qualified_name"], file_path=p,
            start_line=file_by_path[p]["start_line"], end_line=file_by_path[p]["end_line"],
            degree=degree[p],
        )
        for p in ranked_paths
    ]
    edges = [
        GraphEdge(file_by_path[src]["uid"], file_by_path[dst]["uid"], "USES", weight)
        for src, dst, weight in edges_by_path
        if src in selected and dst in selected
    ]

    return GraphView(nodes=nodes, edges=edges, truncated=len(degree) > len(nodes))


def get_class_level_graph(repo_id: str, limit: int = _DEFAULT_CLASS_LIMIT) -> GraphView:
    not_test = _NOT_TEST.format(alias="s")

    with get_driver().session() as session:
        node_rows = session.run(
            f"MATCH (s:Symbol {{repo_id: $repo_id}}) WHERE (s:File OR s:Class) AND {not_test} "
            "OPTIONAL MATCH (s)-[r]-() "
            "WITH s, count(r) AS degree "
            "WHERE degree > 0 "
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

    return GraphView(nodes=nodes, edges=edges, truncated=len(nodes) >= limit)
