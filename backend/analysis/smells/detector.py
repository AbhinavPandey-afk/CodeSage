"""Deterministic architectural smell detection over a repository's graph
(CLAUDE.md §16). Every threshold below is a stated, fixed rule -- the point is
that a panel/reviewer can audit exactly why a finding fired, not trust an LLM's
say-so.

V2 adds a confidence model distinct from severity (see each detector's own
comment for its formula) and context_flags that qualify interpretation
without suppressing anything -- a finding that fires stays visible; only how
much to trust it as a real architectural problem changes. None of this
involves an LLM: every signal is a graph fact (component role, directory
structure, resolver confidence) combined via a fixed, documented rule.
"""
import dataclasses

from analysis.reconstruction.engine import reconstruct_architecture
from analysis.reconstruction.models import ArchitectureComponent, ArchitectureModel
from analysis.smells.architecture_violations import detect_architecture_violations
from analysis.smells.context import compute_finding_id, is_supporting_component
from analysis.smells.graph_algorithms import find_cycle_path, strongly_connected_components
from analysis.smells.models import AffectedSymbol, EvidenceRelationship, Smell
from graph.neo4j.client import get_driver

_GOD_CLASS_THRESHOLDS = (15, 25, 40)  # LOW, MEDIUM, HIGH method-count cutoffs
_LARGE_FUNCTION_THRESHOLDS = (60, 100, 150)  # LOW, MEDIUM, HIGH line-count cutoffs
_DEAD_CODE_LIMIT = 20

# A component that other components depend on this heavily is structurally a
# hub -- the same threshold excessive_component_coupling already uses to
# call a component "highly connected", reused here as one of the signals
# behind FRAMEWORK_HUB.
_HUB_INCOMING_DEGREE = 3


def _severity_for(value: int, thresholds: tuple[int, int, int]) -> str | None:
    low, medium, high = thresholds
    if value >= high:
        return "HIGH"
    if value >= medium:
        return "MEDIUM"
    if value >= low:
        return "LOW"
    return None


def _component_for_file(model: ArchitectureModel, file_path: str) -> ArchitectureComponent | None:
    for c in model.components:
        if file_path in c.files:
            return c
    return None


def _incoming_component_degree(model: ArchitectureModel, component_id: str) -> int:
    """Distinct other components with a resolved relationship INTO this one --
    reused from excessive_component_coupling's own notion of "hub", not a
    new concept invented for confidence scoring."""
    return len({r.source_id for r in model.relationships if r.target_id == component_id and r.source_id != component_id})


# Pure confidence rules, factored out from their Neo4j-querying callers so
# they're unit-testable with a plain constructed ArchitectureModel (no live
# database needed) -- same pattern used for the relationship resolver in
# graph/queries/relationship.py.


def god_class_confidence(model: ArchitectureModel, file_path: str) -> tuple[float, list[str]]:
    """A high method count is a weak, indirect proxy for poor cohesion -- it
    is also exactly what a component other parts of the system heavily
    depend on (a hub) is structurally expected to have (a wide public
    surface), or what supporting/test code (fixtures, base test cases)
    commonly accumulates without implying a maintainability problem in the
    running system."""
    base_confidence = 0.6
    context_flags = ["METHOD_COUNT_HEURISTIC"]
    component = _component_for_file(model, file_path)
    if component is not None:
        if is_supporting_component(component):
            base_confidence -= 0.15
            context_flags.append("SUPPORTING_STRUCTURE")
        elif (
            component.role in ("api", "external_integration")
            or _incoming_component_degree(model, component.id) >= _HUB_INCOMING_DEGREE
        ):
            base_confidence -= 0.15
            context_flags.append("FRAMEWORK_HUB")
    return max(0.2, min(0.9, base_confidence)), context_flags


def large_function_confidence(model: ArchitectureModel, file_path: str) -> tuple[float, list[str]]:
    """Line count is a real but weak complexity proxy (LENGTH_BASED_HEURISTIC
    always applies); a long function inside supporting/test structure is
    less likely to represent a runtime maintainability risk."""
    base_confidence = 0.65
    context_flags = ["LENGTH_BASED_HEURISTIC"]
    component = _component_for_file(model, file_path)
    if component is not None and is_supporting_component(component):
        base_confidence -= 0.15
        context_flags.append("SUPPORTING_STRUCTURE")
    return max(0.2, min(0.9, base_confidence)), context_flags


def dead_code_confidence(model: ArchitectureModel, file_path: str) -> tuple[float, list[str]]:
    """Absence-of-evidence is inherently the weakest kind of evidence
    (DYNAMIC_DISPATCH_RISK always applies -- this static analysis cannot see
    reflection, string-based dispatch, or framework-invoked hooks).
    Supporting/tooling code (docs generators, build scripts) is especially
    prone to being invoked this way, so it gets an additional discount."""
    base_confidence = 0.35
    context_flags = ["DYNAMIC_DISPATCH_RISK"]
    component = _component_for_file(model, file_path)
    if component is not None and is_supporting_component(component):
        base_confidence -= 0.1
        context_flags.append("SUPPORTING_STRUCTURE")
    return max(0.15, base_confidence), context_flags


def circular_dependency_confidence(member_names: list[str], member_files: set[str | None]) -> tuple[float, list[str]]:
    """A real graph cycle is strong structural evidence, but calling it a
    *problem* depends on whether it's normal intra-class delegation (private
    helper methods calling each other) rather than cross-module coupling."""
    base_confidence = 0.75
    context_flags: list[str] = []
    member_classes = {name.rsplit(".", 1)[0] for name in member_names if "." in name}
    if len(member_classes) == 1:
        base_confidence -= 0.25
        context_flags.append("INTRA_CLASS_DELEGATION")
    elif len(member_files) == 1:
        base_confidence -= 0.1
    if len(member_names) >= 5:
        base_confidence += 0.1
    return max(0.1, min(0.95, base_confidence)), context_flags


def detect_circular_dependencies(repo_id: str, model: ArchitectureModel) -> list[Smell]:
    with get_driver().session() as session:
        rows = session.run(
            "MATCH (a:Symbol {repo_id: $repo_id})-[r:CALLS]->(b:Symbol {repo_id: $repo_id}) "
            "RETURN a.uid AS src, b.uid AS dst, a.qualified_name AS src_name, "
            "a.file_path AS src_file, a.start_line AS src_line, a.end_line AS src_end, "
            "r.source_file AS rel_file, r.source_line AS rel_line, r.confidence AS rel_confidence",
            repo_id=repo_id,
        ).data()

    adjacency: dict[str, list[str]] = {}
    meta: dict[str, dict] = {}
    edge_meta: dict[tuple[str, str], dict] = {}
    for row in rows:
        adjacency.setdefault(row["src"], []).append(row["dst"])
        meta[row["src"]] = {
            "qualified_name": row["src_name"], "file_path": row["src_file"],
            "start_line": row["src_line"], "end_line": row["src_end"],
        }
        # Keep the first-seen edge evidence for a given (src, dst) pair --
        # there can be more than one CALLS edge between the same two symbols
        # in principle; one real citation is enough to ground the finding.
        edge_meta.setdefault((row["src"], row["dst"]), {
            "source_file": row["rel_file"], "source_line": row["rel_line"], "confidence": row["rel_confidence"],
        })

    smells = []
    for component in strongly_connected_components(adjacency):
        if len(component) < 2:
            continue
        member_names = sorted(meta.get(uid, {}).get("qualified_name", uid) for uid in component)
        affected = [
            AffectedSymbol(
                qualified_name=meta.get(uid, {}).get("qualified_name", uid),
                file_path=meta.get(uid, {}).get("file_path", "?"),
                start_line=meta.get(uid, {}).get("start_line", 0),
                end_line=meta.get(uid, {}).get("end_line", 0),
            )
            for uid in sorted(component, key=lambda u: meta.get(u, {}).get("qualified_name", u))
        ]
        severity = "HIGH" if len(component) >= 5 else "MEDIUM" if len(component) >= 3 else "LOW"

        # --- cycle path evidence (PART 7): one concrete, ordered example ---
        member_set = set(component)
        cycle_path = find_cycle_path(adjacency, member_set)
        evidence_details: list[EvidenceRelationship] = []
        cycle_note = ""
        if cycle_path:
            for a, b in zip(cycle_path, cycle_path[1:]):
                em = edge_meta.get((a, b), {})
                evidence_details.append(
                    EvidenceRelationship(
                        source=meta.get(a, {}).get("qualified_name", a),
                        target=meta.get(b, {}).get("qualified_name", b),
                        relationship_type="CALLS",
                        source_file=em.get("source_file"),
                        source_line=em.get("source_line"),
                        resolver_confidence=em.get("confidence"),
                    )
                )
            path_names = [meta.get(u, {}).get("qualified_name", u) for u in cycle_path]
            cycle_note = " Example cycle: " + " -> ".join(path_names) + "."
        else:
            cycle_note = (
                " No single explicit cycle path could be reconstructed within the traversal "
                "limit; the member list above is the complete, exact evidence."
            )

        member_files = {meta.get(uid, {}).get("file_path") for uid in component}
        confidence, context_flags = circular_dependency_confidence(member_names, member_files)

        identity = compute_finding_id(model.repo_id, "circular_dependency", *member_names)
        smells.append(
            Smell(
                id=identity, smell_type="circular_dependency", severity=severity, confidence=confidence,
                title=f"Circular call dependency among {len(component)} symbols",
                explanation=(
                    "OBSERVED: these symbols call each other in a cycle (directly or transitively) "
                    "in the resolved CALLS graph -- a static fact, not an observed runtime execution "
                    "order." + cycle_note + " INTERPRETATION: none of them can be understood, tested, "
                    "or changed in isolation."
                ),
                evidence=f"Strongly connected component of size {len(component)} in the CALLS graph.",
                affected=affected,
                context_flags=context_flags,
                evidence_details=evidence_details,
                optimization_supported=False,
            )
        )
    return smells


def detect_god_classes(repo_id: str, model: ArchitectureModel) -> list[Smell]:
    with get_driver().session() as session:
        rows = session.run(
            "MATCH (c:Class {repo_id: $repo_id})-[:CONTAINS]->(m:Method) "
            "WITH c, count(m) AS method_count "
            "WHERE method_count >= $min_methods "
            "RETURN c.qualified_name AS qname, c.file_path AS file_path, "
            "c.start_line AS start_line, c.end_line AS end_line, method_count "
            "ORDER BY method_count DESC",
            repo_id=repo_id, min_methods=_GOD_CLASS_THRESHOLDS[0],
        ).data()

    smells = []
    for row in rows:
        severity = _severity_for(row["method_count"], _GOD_CLASS_THRESHOLDS)
        if severity is None:
            continue

        confidence, context_flags = god_class_confidence(model, row["file_path"])

        identity = compute_finding_id(model.repo_id, "god_class", row["qname"])
        smells.append(
            Smell(
                id=identity, smell_type="god_class", severity=severity, confidence=confidence,
                title=f"{row['qname']} has {row['method_count']} methods",
                explanation=(
                    "OBSERVED: this class defines a high method count. INTERPRETATION: a class "
                    "with this many methods is commonly read as carrying more than one "
                    "responsibility, making it harder to test, extend, and reason about -- but "
                    "method count alone does not prove poor cohesion."
                ),
                evidence=f"{row['method_count']} methods (thresholds: LOW>=15, MEDIUM>=25, HIGH>=40).",
                affected=[AffectedSymbol(row["qname"], row["file_path"], row["start_line"], row["end_line"])],
                context_flags=context_flags,
                optimization_supported=False,
            )
        )
    return smells


def detect_large_functions(repo_id: str, model: ArchitectureModel) -> list[Smell]:
    with get_driver().session() as session:
        rows = session.run(
            "MATCH (s:Symbol {repo_id: $repo_id}) "
            "WHERE s.symbol_type IN ['function', 'method'] "
            "AND (s.end_line - s.start_line) >= $min_lines "
            "RETURN s.qualified_name AS qname, s.file_path AS file_path, "
            "s.start_line AS start_line, s.end_line AS end_line, "
            "(s.end_line - s.start_line) AS line_count "
            "ORDER BY line_count DESC",
            repo_id=repo_id, min_lines=_LARGE_FUNCTION_THRESHOLDS[0],
        ).data()

    smells = []
    for row in rows:
        severity = _severity_for(row["line_count"], _LARGE_FUNCTION_THRESHOLDS)
        if severity is None:
            continue

        confidence, context_flags = large_function_confidence(model, row["file_path"])

        identity = compute_finding_id(model.repo_id, "large_function", row["qname"])
        smells.append(
            Smell(
                id=identity, smell_type="large_function", severity=severity, confidence=confidence,
                title=f"{row['qname']} is {row['line_count']} lines long",
                explanation=(
                    "OBSERVED: this function/method spans this many lines. INTERPRETATION: long "
                    "functions tend to mix multiple concerns and are disproportionately likely to "
                    "contain bugs or be hard to unit test -- but line count measures length, not "
                    "cognitive complexity."
                ),
                evidence=f"{row['line_count']} lines (thresholds: LOW>=60, MEDIUM>=100, HIGH>=150).",
                affected=[AffectedSymbol(row["qname"], row["file_path"], row["start_line"], row["end_line"])],
                context_flags=context_flags,
                optimization_supported=False,
            )
        )
    return smells


def detect_dead_code_candidates(repo_id: str, model: ArchitectureModel) -> list[Smell]:
    """Functions/methods with no recorded caller and no decorator.

    This is explicitly the weakest-confidence smell: decorated functions are
    excluded because they're commonly invoked through a framework (routes,
    fixtures, event handlers) that this static analysis can't see, and
    dunder/test_ methods are excluded as known framework-invoked patterns.
    Remaining hits are still only "Inferred", never "Confirmed" dead code.
    """
    with get_driver().session() as session:
        rows = session.run(
            "MATCH (s:Symbol {repo_id: $repo_id}) "
            "WHERE s.symbol_type IN ['function', 'method'] "
            "AND NOT s.name STARTS WITH '__' AND NOT s.name STARTS WITH 'test_' "
            "AND size(s.decorators) = 0 "
            "AND NOT EXISTS { MATCH ()-[:CALLS]->(s) } "
            "RETURN s.qualified_name AS qname, s.file_path AS file_path, "
            "s.start_line AS start_line, s.end_line AS end_line "
            "LIMIT $limit",
            repo_id=repo_id, limit=_DEAD_CODE_LIMIT,
        ).data()

    if not rows:
        return []

    smells = []
    for row in rows:
        confidence, context_flags = dead_code_confidence(model, row["file_path"])

        identity = compute_finding_id(model.repo_id, "dead_code_candidate", row["qname"])
        smells.append(
            Smell(
                id=identity, smell_type="dead_code_candidate", severity="LOW", confidence=confidence,
                title=f"{row['qname']} has no recorded callers",
                explanation=(
                    "OBSERVED: no CALLS edge points to this symbol from within the repository. "
                    "INTERPRETATION: this is a DEAD CODE CANDIDATE, not proven dead code -- static "
                    "analysis cannot see dynamic dispatch, reflection, or external callers "
                    "(e.g. a CLI entry point or a framework hook invoked by name), so absence of a "
                    "recorded caller is not proof the symbol is unreachable."
                ),
                evidence="0 incoming CALLS edges; no decorators; not a dunder/test method.",
                affected=[AffectedSymbol(row["qname"], row["file_path"], row["start_line"], row["end_line"])],
                context_flags=context_flags,
                optimization_supported=False,
            )
        )
    return smells


def _link_related_findings(smells: list[Smell]) -> list[Smell]:
    """Connects god_class <-> large_function findings that share the same
    root entity (a class and one of its own methods) -- structural
    containment evidence (the qualified-name prefix relationship), not a
    guess. Findings are never suppressed or merged; this only adds
    cross-references so a consumer can present them together later."""
    god_classes = [s for s in smells if s.smell_type == "god_class"]
    large_functions = [s for s in smells if s.smell_type == "large_function"]
    if not god_classes or not large_functions:
        return smells

    related: dict[str, set[str]] = {}
    for g in god_classes:
        class_qname = g.affected[0].qualified_name if g.affected else None
        if not class_qname:
            continue
        for f in large_functions:
            func_qname = f.affected[0].qualified_name if f.affected else None
            if func_qname and func_qname.startswith(class_qname + "."):
                related.setdefault(g.id, set()).add(f.id)
                related.setdefault(f.id, set()).add(g.id)

    if not related:
        return smells
    return [
        dataclasses.replace(s, related_finding_ids=sorted(related[s.id])) if s.id in related else s
        for s in smells
    ]


_SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def run_smell_detection(repo_id: str) -> list[Smell]:
    model = reconstruct_architecture(repo_id)
    smells = [
        *detect_circular_dependencies(repo_id, model),
        *detect_god_classes(repo_id, model),
        *detect_large_functions(repo_id, model),
        *detect_dead_code_candidates(repo_id, model),
        *detect_architecture_violations(model),
    ]
    smells = _link_related_findings(smells)
    return sorted(smells, key=lambda s: _SEVERITY_ORDER[s.severity])
