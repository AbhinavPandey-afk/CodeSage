"""Architecture Reconstruction engine (CLAUDE.md §15/§35): groups the existing
knowledge graph's files into architectural components by directory structure,
infers each component's role from deterministic signals, and derives
inter-component relationships from existing resolved CALLS edges.

This is the first Architecture Reconstruction milestone (CLAUDE.md §50):
Existing Neo4j Graph -> Architecture Reconstruction -> Structured Current
Architecture -> Evidence + Confidence. No LLM involvement anywhere in this
module — the graph and grouping.py are the only sources of truth, per
CLAUDE.md §15's ban on LLM-invented architecture diagrams.
"""
from analysis.reconstruction.grouping import SymbolSignal, confidence_label, group_key, infer_role
from analysis.reconstruction.models import ArchitectureComponent, ArchitectureModel, ComponentRelationship
from graph.neo4j.client import get_driver

_MAX_COMPONENTS = 40
_MAX_RELATIONSHIP_EVIDENCE = 3


def reconstruct_architecture(repo_id: str) -> ArchitectureModel:
    with get_driver().session() as session:
        file_rows = session.run(
            "MATCH (f:File {repo_id: $repo_id}) RETURN f.file_path AS file_path",
            repo_id=repo_id,
        ).data()
        symbol_rows = session.run(
            "MATCH (s:Symbol {repo_id: $repo_id}) "
            "WHERE s.symbol_type IN ['class', 'function', 'method'] "
            "RETURN s.file_path AS file_path, s.qualified_name AS qualified_name, "
            "s.symbol_type AS symbol_type, s.decorators AS decorators",
            repo_id=repo_id,
        ).data()
        import_rows = session.run(
            "MATCH (s:Symbol {repo_id: $repo_id, symbol_type: 'import'}) "
            "RETURN s.file_path AS file_path, s.name AS dotted",
            repo_id=repo_id,
        ).data()
        call_rows = session.run(
            "MATCH (a:Symbol {repo_id: $repo_id})-[r:CALLS]->(b:Symbol {repo_id: $repo_id}) "
            "WHERE a.file_path <> b.file_path "
            "RETURN a.file_path AS src_file, b.file_path AS dst_file, "
            "r.confidence AS confidence, r.source_file AS source_file, r.source_line AS source_line",
            repo_id=repo_id,
        ).data()

    if not file_rows:
        return ArchitectureModel(
            repo_id=repo_id, components=[], relationships=[], truncated=False,
            detection_notes=["No files were found in the knowledge graph for this repository."],
        )

    file_to_group: dict[str, str] = {r["file_path"]: group_key(r["file_path"]) for r in file_rows}

    symbols_by_group: dict[str, list[SymbolSignal]] = {}
    for r in symbol_rows:
        key = file_to_group.get(r["file_path"])
        if key is None:
            continue
        symbols_by_group.setdefault(key, []).append(
            SymbolSignal(r["qualified_name"], r["symbol_type"], r.get("decorators") or [])
        )

    imports_by_group: dict[str, list[str]] = {}
    for r in import_rows:
        key = file_to_group.get(r["file_path"])
        if key is None:
            continue
        imports_by_group.setdefault(key, []).append(r["dotted"])

    files_by_group: dict[str, list[str]] = {}
    for path, key in file_to_group.items():
        files_by_group.setdefault(key, []).append(path)

    symbol_count_by_group = {k: len(v) for k, v in symbols_by_group.items()}

    ranked_keys = sorted(
        files_by_group,
        key=lambda k: (symbol_count_by_group.get(k, 0), len(files_by_group[k])),
        reverse=True,
    )
    truncated = len(ranked_keys) > _MAX_COMPONENTS
    selected_keys = set(ranked_keys[:_MAX_COMPONENTS])

    components: list[ArchitectureComponent] = []
    for key in selected_keys:
        symbols = symbols_by_group.get(key, [])
        imports = imports_by_group.get(key, [])
        role, confidence, evidence = infer_role(key, symbols, imports)
        files = sorted(files_by_group[key])
        components.append(
            ArchitectureComponent(
                id=key, name=key.replace("/", " / "), role=role,
                file_count=len(files), symbol_count=len(symbols), files=files,
                confidence=confidence, confidence_label=confidence_label(confidence),
                evidence=evidence,
            )
        )
    components.sort(key=lambda c: c.symbol_count, reverse=True)

    agg: dict[tuple[str, str], dict] = {}
    for r in call_rows:
        src_key = file_to_group.get(r["src_file"])
        dst_key = file_to_group.get(r["dst_file"])
        if src_key is None or dst_key is None or src_key == dst_key:
            continue
        if src_key not in selected_keys or dst_key not in selected_keys:
            continue
        bucket = agg.setdefault((src_key, dst_key), {"count": 0, "confidences": [], "examples": []})
        bucket["count"] += 1
        bucket["confidences"].append(r["confidence"] if r["confidence"] is not None else 1.0)
        if len(bucket["examples"]) < _MAX_RELATIONSHIP_EVIDENCE:
            bucket["examples"].append(f"{r['source_file']}:{r['source_line']}")

    relationships: list[ComponentRelationship] = []
    for (src_key, dst_key), bucket in agg.items():
        avg_conf = sum(bucket["confidences"]) / len(bucket["confidences"])
        relationships.append(
            ComponentRelationship(
                source_id=src_key, target_id=dst_key, call_count=bucket["count"],
                confidence=avg_conf, confidence_label=confidence_label(avg_conf),
                evidence=[
                    f"{bucket['count']} call(s) from '{src_key}' to '{dst_key}' "
                    f"(avg resolver confidence {avg_conf:.2f})",
                    *[f"e.g. {ex}" for ex in bucket["examples"]],
                ],
            )
        )
    relationships.sort(key=lambda r: r.call_count, reverse=True)

    detection_notes = [
        "Components are directory-based groupings (up to two directory levels deep), "
        "not a guaranteed 1:1 match to the repository's intended module boundaries.",
        "Roles (api/service/data_access/external_integration/model/test/other) are inferred "
        "from route decorators, class-naming conventions, and import targets — the same "
        "deterministic signals used by change impact analysis, not an LLM judgment.",
        "Relationships are aggregated from resolved CALLS edges between symbols in different "
        "components; IMPORTS edges are intentionally excluded as too noisy to imply an "
        "architectural dependency on their own.",
    ]
    if truncated:
        detection_notes.append(
            f"{len(ranked_keys)} candidate components were found; only the {_MAX_COMPONENTS} "
            "largest (by symbol count) are shown."
        )

    return ArchitectureModel(
        repo_id=repo_id, components=components, relationships=relationships,
        truncated=truncated, detection_notes=detection_notes,
    )
