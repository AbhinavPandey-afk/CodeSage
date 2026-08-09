"""Deterministic architectural smell detection over a repository's graph
(CLAUDE.md §16). Every threshold below is a stated, fixed rule — the point is
that a panel/reviewer can audit exactly why a finding fired, not trust an LLM's
say-so.
"""
from analysis.smells.graph_algorithms import strongly_connected_components
from analysis.smells.models import AffectedSymbol, Smell
from graph.neo4j.client import get_driver

_GOD_CLASS_THRESHOLDS = (15, 25, 40)  # LOW, MEDIUM, HIGH method-count cutoffs
_LARGE_FUNCTION_THRESHOLDS = (60, 100, 150)  # LOW, MEDIUM, HIGH line-count cutoffs
_DEAD_CODE_LIMIT = 20


def _severity_for(value: int, thresholds: tuple[int, int, int]) -> str | None:
    low, medium, high = thresholds
    if value >= high:
        return "HIGH"
    if value >= medium:
        return "MEDIUM"
    if value >= low:
        return "LOW"
    return None


def detect_circular_dependencies(repo_id: str) -> list[Smell]:
    with get_driver().session() as session:
        rows = session.run(
            "MATCH (a:Symbol {repo_id: $repo_id})-[:CALLS]->(b:Symbol {repo_id: $repo_id}) "
            "RETURN a.uid AS src, b.uid AS dst, a.qualified_name AS src_name, "
            "a.file_path AS src_file, a.start_line AS src_line, a.end_line AS src_end",
            repo_id=repo_id,
        ).data()

    adjacency: dict[str, list[str]] = {}
    meta: dict[str, dict] = {}
    for row in rows:
        adjacency.setdefault(row["src"], []).append(row["dst"])
        meta[row["src"]] = {
            "qualified_name": row["src_name"], "file_path": row["src_file"],
            "start_line": row["src_line"], "end_line": row["src_end"],
        }

    smells = []
    for component in strongly_connected_components(adjacency):
        if len(component) < 2:
            continue
        affected = [
            AffectedSymbol(
                qualified_name=meta.get(uid, {}).get("qualified_name", uid),
                file_path=meta.get(uid, {}).get("file_path", "?"),
                start_line=meta.get(uid, {}).get("start_line", 0),
                end_line=meta.get(uid, {}).get("end_line", 0),
            )
            for uid in component
        ]
        severity = "HIGH" if len(component) >= 5 else "MEDIUM" if len(component) >= 3 else "LOW"
        smells.append(
            Smell(
                smell_type="circular_dependency", severity=severity,
                title=f"Circular call dependency among {len(component)} symbols",
                explanation=(
                    "These symbols call each other in a cycle (directly or transitively), "
                    "meaning none of them can be understood, tested, or changed in isolation."
                ),
                evidence=f"Strongly connected component of size {len(component)} in the CALLS graph.",
                affected=affected,
            )
        )
    return smells


def detect_god_classes(repo_id: str) -> list[Smell]:
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
        smells.append(
            Smell(
                smell_type="god_class", severity=severity,
                title=f"{row['qname']} has {row['method_count']} methods",
                explanation=(
                    "A class with a very high method count is likely carrying more than one "
                    "responsibility, making it harder to test, extend, and reason about."
                ),
                evidence=f"{row['method_count']} methods (thresholds: LOW>=15, MEDIUM>=25, HIGH>=40).",
                affected=[AffectedSymbol(row["qname"], row["file_path"], row["start_line"], row["end_line"])],
            )
        )
    return smells


def detect_large_functions(repo_id: str) -> list[Smell]:
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
        smells.append(
            Smell(
                smell_type="large_function", severity=severity,
                title=f"{row['qname']} is {row['line_count']} lines long",
                explanation=(
                    "Long functions tend to mix multiple concerns and are disproportionately "
                    "likely to contain bugs or be hard to unit test."
                ),
                evidence=f"{row['line_count']} lines (thresholds: LOW>=60, MEDIUM>=100, HIGH>=150).",
                affected=[AffectedSymbol(row["qname"], row["file_path"], row["start_line"], row["end_line"])],
            )
        )
    return smells


def detect_dead_code_candidates(repo_id: str) -> list[Smell]:
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

    return [
        Smell(
            smell_type="dead_code_candidate", severity="LOW",
            title=f"{row['qname']} has no recorded callers",
            explanation=(
                "No CALLS edge points to this symbol from within the repository. This is a "
                "static-analysis heuristic, not proof of dead code — it misses dynamic "
                "dispatch, reflection, and external callers (e.g. a CLI entry point)."
            ),
            evidence="0 incoming CALLS edges; no decorators; not a dunder/test method.",
            affected=[AffectedSymbol(row["qname"], row["file_path"], row["start_line"], row["end_line"])],
        )
        for row in rows
    ]


_SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def run_smell_detection(repo_id: str) -> list[Smell]:
    smells = [
        *detect_circular_dependencies(repo_id),
        *detect_god_classes(repo_id),
        *detect_large_functions(repo_id),
        *detect_dead_code_candidates(repo_id),
    ]
    return sorted(smells, key=lambda s: _SEVERITY_ORDER[s.severity])
