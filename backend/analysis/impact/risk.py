"""Deterministic risk scoring (CLAUDE.md §20) — a fixed point rubric over
measurable graph signals. The LLM is never involved in assigning risk; this
module is the only place a risk level is produced, and every point awarded
is returned as a named RiskSignal so the score is auditable, not asserted.
"""
from analysis.impact.models import RiskSignal

_LEVEL_THRESHOLDS = (("CRITICAL", 8), ("HIGH", 5), ("MEDIUM", 3), ("LOW", 0))


def _dependents_points(total: int) -> tuple[int, str]:
    if total == 0:
        return 0, "0"
    if total <= 3:
        return 1, "1-3"
    if total <= 10:
        return 2, "4-10"
    if total <= 25:
        return 3, "11-25"
    return 4, ">25"


def score_risk(
    *,
    direct_count: int,
    indirect_count: int,
    affected_apis_count: int,
    affected_services_count: int,
    affected_tests_count: int,
    external_dependency_count: int,
    target_degree: int,
) -> tuple[str, int, list[RiskSignal]]:
    total_dependents = direct_count + indirect_count
    signals: list[RiskSignal] = []

    points, bucket = _dependents_points(total_dependents)
    signals.append(RiskSignal("Total dependents", f"{total_dependents} ({bucket})", points))

    if affected_apis_count > 0:
        signals.append(RiskSignal("Affects API endpoints", f"{affected_apis_count}", 2))
    if affected_services_count > 0:
        signals.append(RiskSignal("Affects service-layer components", f"{affected_services_count}", 1))

    if total_dependents > 0 and affected_tests_count == 0:
        signals.append(RiskSignal("Test coverage of dependents", "none found", 2))
    elif total_dependents > 0:
        signals.append(RiskSignal("Test coverage of dependents", f"{affected_tests_count} test(s) found", 0))

    if external_dependency_count > 0:
        signals.append(RiskSignal("Touches external dependencies", f"{external_dependency_count}", 1))

    if target_degree >= 15:
        signals.append(RiskSignal("Graph centrality of target", f"degree {target_degree} (>=15)", 1))

    total_score = sum(s.points for s in signals)
    level = next(name for name, threshold in _LEVEL_THRESHOLDS if total_score >= threshold)
    return level, total_score, signals


def explain(
    *,
    target_qualified_name: str,
    direct_count: int,
    indirect_count: int,
    affected_apis_count: int,
    affected_services_count: int,
    affected_tests_count: int,
    external_names: list[str],
    risk_level: str,
) -> str:
    total = direct_count + indirect_count
    parts = [
        f"{target_qualified_name} has {total} dependent(s) in this repository "
        f"({direct_count} direct, {indirect_count} indirect)."
    ]
    if affected_apis_count:
        parts.append(f"{affected_apis_count} of them are API endpoints, so a regression could surface externally.")
    if affected_services_count:
        parts.append(f"{affected_services_count} sit in service-layer components.")
    if total > 0 and affected_tests_count == 0:
        parts.append("No tests were found covering any dependent, so a regression here may go undetected.")
    elif affected_tests_count:
        parts.append(f"{affected_tests_count} test(s) exercise a dependent, giving some safety net.")
    if external_names:
        parts.append(f"This symbol's own file touches external dependencies: {', '.join(external_names[:5])}.")
    parts.append(f"Overall risk: {risk_level}.")
    return " ".join(parts)
