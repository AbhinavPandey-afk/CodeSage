"""Execution Flow Reconstruction engine (CLAUDE.md §21/§22/§34 Phase 4).

Static reconstruction only -- this never executes repository code. Starting
from a detected API entry point, it traverses resolved CALLS edges already in
the graph to build a bounded call tree. A PROPOSED variant is derived by
splicing in the service-layer component identified by a layer_skip finding
from Architecture Optimization wherever the OBSERVED flow crosses that exact
violating component pair -- CLAUDE.md §22's current vs proposed flow
comparison. No LLM call anywhere in this module.

Traversal boundary: a hop stops recursing only when it genuinely runs out of
resolved evidence (no more CALLS edges for that symbol in this repo's graph),
or hits the depth/branch/total-hop safety limits -- never merely because its
Architecture *role* is data_access/external_integration. A component with
that role can still contain further resolved calls within this same
repository (e.g. Flask's own `templating.render_template` calling deeper into
Flask's own source), and those remain traversable. See
`analysis/execution_flow/models.py`'s module docstring for the full
terminal_reason contract this produces.

The tree-building and splicing logic (_build_children, _build_proposed_tree)
is pure -- it takes already-fetched maps, so it is unit-testable without
Neo4j. Only reconstruct_execution_flow() and detect_entry_points() touch the
graph.
"""
import dataclasses

from analysis.execution_flow.models import EntryPoint, ExecutionFlowReport, FlowHop
from analysis.impact.classifiers import classify_call_target_module, is_api_endpoint
from analysis.reconstruction.engine import reconstruct_architecture
from analysis.reconstruction.models import ArchitectureModel
from analysis.smells.architecture_violations import all_violation_records
from graph.neo4j.client import get_driver

_MAX_DEPTH = 5
_MAX_BRANCHES_PER_HOP = 3
_MAX_TOTAL_HOPS = 150

CallAdjacency = dict[str, list[tuple[str, float, str | None, int | None]]]
SymbolMeta = dict[str, tuple[str, str]]  # uid -> (qualified_name, file_path)


class EntryPointNotFoundError(ValueError):
    pass


def detect_entry_points(repo_id: str, limit: int = 20) -> list[EntryPoint]:
    with get_driver().session() as session:
        rows = session.run(
            "MATCH (s:Symbol {repo_id: $repo_id}) "
            "WHERE s.symbol_type IN ['function', 'method'] AND size(s.decorators) > 0 "
            "RETURN s.uid AS uid, s.qualified_name AS qualified_name, "
            "s.file_path AS file_path, s.start_line AS start_line, s.decorators AS decorators",
            repo_id=repo_id,
        ).data()

    entry_points: list[EntryPoint] = []
    for r in rows:
        decorators = r.get("decorators") or []
        if not is_api_endpoint(decorators):
            continue
        route_hint = next((d for d in decorators if is_api_endpoint([d])), None)
        entry_points.append(
            EntryPoint(
                uid=r["uid"], qualified_name=r["qualified_name"], file_path=r["file_path"],
                start_line=r["start_line"], route_hint=route_hint,
            )
        )
    entry_points.sort(key=lambda e: e.qualified_name)
    return entry_points[:limit]


def _fetch_call_adjacency(repo_id: str) -> CallAdjacency:
    with get_driver().session() as session:
        rows = session.run(
            "MATCH (a:Symbol {repo_id: $repo_id})-[r:CALLS]->(b:Symbol {repo_id: $repo_id}) "
            "RETURN a.uid AS src, b.uid AS dst, r.confidence AS confidence, "
            "r.source_file AS source_file, r.source_line AS source_line",
            repo_id=repo_id,
        ).data()
    adjacency: CallAdjacency = {}
    for r in rows:
        adjacency.setdefault(r["src"], []).append(
            (r["dst"], r["confidence"] if r["confidence"] is not None else 1.0, r["source_file"], r["source_line"])
        )
    return adjacency


def _fetch_symbol_meta(repo_id: str) -> tuple[SymbolMeta, dict[str, str], dict[str, list[str]]]:
    """Returns (uid -> (qualified_name, file_path), uid -> language,
    uid -> raw unresolved-call target names). The latter two exist purely to
    let _leaf_terminal_reason tell a genuine standard-library/external
    boundary apart from a call the resolver simply couldn't attribute --
    graph/loader.py persists `unresolved_call_targets` for exactly this."""
    with get_driver().session() as session:
        rows = session.run(
            "MATCH (s:Symbol {repo_id: $repo_id}) WHERE s.symbol_type IN ['function', 'method'] "
            "RETURN s.uid AS uid, s.qualified_name AS qualified_name, s.file_path AS file_path, "
            "s.language AS language, s.unresolved_call_targets AS unresolved_call_targets",
            repo_id=repo_id,
        ).data()
    meta = {r["uid"]: (r["qualified_name"], r["file_path"]) for r in rows}
    languages = {r["uid"]: r["language"] for r in rows}
    unresolved_by_uid = {r["uid"]: (r["unresolved_call_targets"] or []) for r in rows}
    return meta, languages, unresolved_by_uid


def _fetch_file_imports(repo_id: str) -> dict[str, list[str]]:
    with get_driver().session() as session:
        rows = session.run(
            "MATCH (s:Symbol {repo_id: $repo_id, symbol_type: 'import'}) "
            "RETURN s.file_path AS file_path, s.name AS dotted",
            repo_id=repo_id,
        ).data()
    imports: dict[str, list[str]] = {}
    for r in rows:
        imports.setdefault(r["file_path"], []).append(r["dotted"])
    return imports


def _component_maps(model: ArchitectureModel) -> tuple[dict[str, str], dict[str, str]]:
    """Returns (file_path -> component_id, component_id -> role)."""
    file_to_component: dict[str, str] = {}
    role_by_component: dict[str, str] = {}
    for c in model.components:
        role_by_component[c.id] = c.role
        for f in c.files:
            file_to_component[f] = c.id
    return file_to_component, role_by_component


def _terminal_kind_for(uid: str, meta: SymbolMeta, file_to_component: dict[str, str], role_by_component: dict[str, str]) -> str | None:
    """Purely descriptive Architecture *role* of this symbol's component --
    "database"/"external_service" badges. Does NOT decide whether traversal
    continues past it; see _leaf_terminal_reason for that."""
    file_path = meta.get(uid, (None, None))[1]
    component_id = file_to_component.get(file_path) if file_path else None
    role = role_by_component.get(component_id) if component_id else None
    if role == "data_access":
        return "database"
    if role == "external_integration":
        return "external_service"
    return None


def _leaf_terminal_reason(
    uid: str, meta: SymbolMeta, languages: dict[str, str],
    unresolved_by_uid: dict[str, list[str]], file_imports: dict[str, list[str]],
) -> str:
    """Why a symbol with zero resolved outgoing CALLS is a leaf. Cross-checks
    each unresolved call's own object/module prefix (e.g. "sqlite3" in a
    "sqlite3.connect(...)" call) against that *file's* actually-recorded
    imports before trusting it as a module name -- a bare prefix like "g" in
    "g.pop(...)" is far more likely a local variable than a package, and
    isn't classified as one unless the file really does import something
    with that top-level name. This is deliberately more precise than
    scanning a file's whole import list, which can't tell which import a
    specific dead-end call was actually about."""
    targets = unresolved_by_uid.get(uid) or []
    if not targets:
        return "NO_RESOLVED_CALLEES"

    file_path = meta.get(uid, (None, None))[1]
    language = languages.get(uid)
    imported_top_levels = {t.split(".", 1)[0] for t in file_imports.get(file_path, [])} if file_path else set()

    saw_external = False
    for target in targets:
        if "." not in target:
            continue
        top_level = target.split(".", 1)[0]
        if top_level not in imported_top_levels:
            continue  # can't confirm this prefix is really an imported module
        if classify_call_target_module(top_level, language) == "stdlib":
            return "STANDARD_LIBRARY"
        saw_external = True
    return "EXTERNAL_DEPENDENCY" if saw_external else "UNRESOLVED"


def _build_children(
    caller_uid: str, caller_qname: str, depth: int, path_seen: frozenset[str],
    adjacency: CallAdjacency, meta: SymbolMeta,
    file_to_component: dict[str, str], role_by_component: dict[str, str], budget: list[int],
    component_name_by_id: dict[str, str] | None = None,
    languages: dict[str, str] | None = None,
    unresolved_by_uid: dict[str, list[str]] | None = None,
    file_imports: dict[str, list[str]] | None = None,
) -> tuple[list[FlowHop], str | None, int]:
    """Returns (children, terminal_reason, children_omitted).
    terminal_reason is None whenever `children` is non-empty -- it explains
    why *this* symbol has no more resolved hops beyond depth/branch limits.
    children_omitted is how many of this symbol's own resolved calls exist
    beyond the per-hop branch cap, disclosed rather than silently dropped."""
    component_name_by_id = component_name_by_id or {}
    languages = languages or {}
    unresolved_by_uid = unresolved_by_uid or {}
    file_imports = file_imports or {}

    if depth >= _MAX_DEPTH:
        return [], "DEPTH_LIMIT", 0
    if budget[0] <= 0:
        return [], "BRANCH_LIMIT", 0

    all_edges = sorted(adjacency.get(caller_uid, []), key=lambda e: e[1], reverse=True)
    if not all_edges:
        return [], _leaf_terminal_reason(caller_uid, meta, languages, unresolved_by_uid, file_imports), 0

    edges = all_edges[:_MAX_BRANCHES_PER_HOP]
    children_omitted = max(0, len(all_edges) - len(edges))

    hops: list[FlowHop] = []
    for callee_uid, confidence, source_file, source_line in edges:
        if budget[0] <= 0:
            break
        if callee_uid in path_seen:
            continue  # recursive/cyclic call -- stop this branch rather than loop forever
        callee_qname, callee_file = meta.get(callee_uid, (callee_uid, None))
        terminal_kind = _terminal_kind_for(callee_uid, meta, file_to_component, role_by_component)
        component_id = file_to_component.get(callee_file) if callee_file else None
        component_role = role_by_component.get(component_id) if component_id else None
        component_name = component_name_by_id.get(component_id) if component_id else None
        budget[0] -= 1

        grandchildren, terminal_reason, grandchildren_omitted = _build_children(
            callee_uid, callee_qname, depth + 1, path_seen | {callee_uid},
            adjacency, meta, file_to_component, role_by_component, budget,
            component_name_by_id, languages, unresolved_by_uid, file_imports,
        )
        hops.append(
            FlowHop(
                label="OBSERVED", caller_qualified_name=caller_qname, callee_qualified_name=callee_qname,
                callee_uid=callee_uid, relationship_type="CALLS", source_file=source_file,
                source_line=source_line, confidence=confidence, terminal_kind=terminal_kind,
                callee_file_path=callee_file, component_id=component_id, component_role=component_role,
                component_name=component_name, terminal_reason=terminal_reason,
                children_omitted=grandchildren_omitted, caller_uid=caller_uid, children=grandchildren,
            )
        )
    return hops, None, children_omitted


def _build_proposed_tree(
    root: FlowHop, meta: SymbolMeta, file_to_component: dict[str, str], skip_pairs: dict[tuple[str, str], str],
) -> tuple[FlowHop, bool]:
    """Walks the OBSERVED tree and inserts a synthetic PROPOSED hop wherever a
    caller->callee component pair matches a known layer_skip finding."""

    def walk(hop: FlowHop) -> tuple[FlowHop, bool]:
        new_children = []
        any_splice = False
        for child in hop.children:
            src_file = meta.get(child.caller_uid, (None, None))[1] if child.caller_uid else None
            dst_file = meta.get(child.callee_uid, (None, None))[1] if child.callee_uid else None
            src_comp = file_to_component.get(src_file) if src_file else None
            dst_comp = file_to_component.get(dst_file) if dst_file else None

            walked_child, child_spliced = walk(child)

            if src_comp and dst_comp and (src_comp, dst_comp) in skip_pairs:
                service_name = skip_pairs[(src_comp, dst_comp)]
                bridge_target = dataclasses.replace(
                    walked_child,
                    caller_qualified_name=f"{service_name} (proposed)",
                    label="PROPOSED",
                )
                synthetic = FlowHop(
                    label="PROPOSED", caller_qualified_name=child.caller_qualified_name,
                    callee_qualified_name=f"{service_name} (proposed service layer)", callee_uid=None,
                    relationship_type="PROPOSED_CALL", source_file=None, source_line=None,
                    confidence=0.5, terminal_kind=None,
                    component_role="service", component_name=service_name,
                    note=(
                        "Synthesized by Architecture Optimization: routes this call through an existing "
                        "service-layer component instead of calling it directly. This is a design "
                        "projection, not an observed call."
                    ),
                    children=[bridge_target],
                )
                new_children.append(synthetic)
                any_splice = True
            else:
                new_children.append(walked_child)
                any_splice = any_splice or child_spliced

        return dataclasses.replace(hop, children=new_children), any_splice

    return walk(root)


def _layer_skip_pairs(model: ArchitectureModel) -> dict[tuple[str, str], str]:
    """component_id pair (src, dst) -> a suggested service-layer component
    name to route through -- the largest (by symbol count) service-role
    component in the reconstructed architecture. Deterministic, but a
    heuristic suggestion, not a guaranteed correct mediator."""
    service_components = [c for c in model.components if c.role == "service"]
    if not service_components:
        return {}
    suggested_name = service_components[0].name

    pairs: dict[tuple[str, str], str] = {}
    for record in all_violation_records(model):
        if record.kind == "layer_skip":
            pairs[record.component_ids] = suggested_name
    return pairs


def reconstruct_execution_flow(repo_id: str, entry_uid: str) -> ExecutionFlowReport:
    meta, languages, unresolved_by_uid = _fetch_symbol_meta(repo_id)
    if entry_uid not in meta:
        raise EntryPointNotFoundError(f"Entry point {entry_uid} not found in repository {repo_id}.")
    entry_qname, entry_file = meta[entry_uid]

    with get_driver().session() as session:
        entry_row = session.run(
            "MATCH (s:Symbol {uid: $uid, repo_id: $repo_id}) RETURN s.start_line AS start_line, s.decorators AS decorators",
            uid=entry_uid, repo_id=repo_id,
        ).single()
    start_line = entry_row["start_line"] if entry_row else 0
    decorators = (entry_row["decorators"] or []) if entry_row else []
    route_hint = next((d for d in decorators if is_api_endpoint([d])), None)
    entry = EntryPoint(uid=entry_uid, qualified_name=entry_qname, file_path=entry_file, start_line=start_line, route_hint=route_hint)

    adjacency = _fetch_call_adjacency(repo_id)
    file_imports = _fetch_file_imports(repo_id)
    model = reconstruct_architecture(repo_id)
    file_to_component, role_by_component = _component_maps(model)
    component_name_by_id = {c.id: c.name for c in model.components}

    budget = [_MAX_TOTAL_HOPS]
    children, entry_terminal_reason, entry_children_omitted = _build_children(
        entry_uid, entry_qname, 0, frozenset({entry_uid}), adjacency, meta,
        file_to_component, role_by_component, budget, component_name_by_id,
        languages, unresolved_by_uid, file_imports,
    )
    entry_component_id = file_to_component.get(entry_file) if entry_file else None
    entry_component_role = role_by_component.get(entry_component_id) if entry_component_id else None
    entry_component_name = component_name_by_id.get(entry_component_id) if entry_component_id else None
    observed_root = FlowHop(
        label="OBSERVED", caller_qualified_name="", callee_qualified_name=entry_qname, callee_uid=entry_uid,
        relationship_type="ENTRY", source_file=entry_file, source_line=start_line, confidence=1.0,
        terminal_kind=None, callee_file_path=entry_file, component_id=entry_component_id,
        component_role=entry_component_role, component_name=entry_component_name,
        terminal_reason=entry_terminal_reason, children_omitted=entry_children_omitted,
        caller_uid=None, children=children,
    )

    skip_pairs = _layer_skip_pairs(model)
    proposed_root: FlowHop | None = None
    if skip_pairs:
        proposed_root, spliced = _build_proposed_tree(observed_root, meta, file_to_component, skip_pairs)
        if not spliced:
            proposed_root = None

    truncated = budget[0] <= 0
    detection_notes = [
        "This is a static reconstruction from resolved CALLS edges -- it does not execute the "
        "repository. Dynamic dispatch, reflection, and dependency injection are not detected and "
        "may cause real call paths to differ from what is shown here.",
        f"Traversal is bounded to depth {_MAX_DEPTH} and up to {_MAX_BRANCHES_PER_HOP} of the highest-"
        "confidence calls per hop; omitted branches are disclosed per hop rather than hidden.",
        "Traversal follows resolved calls across the whole repository, including components "
        "classified as external_integration/data_access -- that role describes the component's "
        "architectural position, not whether execution flow can continue through it.",
    ]
    if proposed_root is not None:
        detection_notes.append(
            "The PROPOSED flow is a design projection derived from Architecture Optimization's "
            "layer-skip findings, not an observed or guaranteed future call path."
        )
    if truncated:
        detection_notes.append(f"Traversal stopped after {_MAX_TOTAL_HOPS} hops; this flow is larger than shown.")

    return ExecutionFlowReport(
        repo_id=repo_id, entry=entry, observed=observed_root, proposed=proposed_root,
        truncated=truncated, detection_notes=detection_notes,
    )
