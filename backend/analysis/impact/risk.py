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
    target_degree: int,
    risk_level: str,
) -> str:
    """Narrate *why* the score came out this way — what each signal implies
    for a developer about to make the change — rather than repeating the
    raw counts the signal table already shows."""
    total = direct_count + indirect_count
    sentences: list[str] = []

    if total == 0:
        sentences.append(
            f"Nothing in this repository calls or inherits from {target_qualified_name}, "
            "so a change here carries no measurable ripple-effect risk on its own."
        )
    elif total > 25:
        sentences.append(
            f"{target_qualified_name} is one of the most heavily relied-upon symbols in this "
            f"codebase — {total} other symbols ({direct_count} directly, {indirect_count} "
            "transitively) depend on it, so a behavior change here is likely to ripple far "
            "beyond the immediate call sites."
        )
    elif total > 10:
        sentences.append(
            f"{target_qualified_name} has a moderate footprint — {total} dependent(s) "
            f"({direct_count} direct, {indirect_count} indirect) — enough that a change is "
            "unlikely to stay contained to one area of the codebase."
        )
    else:
        sentences.append(
            f"{target_qualified_name} has a small, contained footprint: only {total} "
            f"dependent(s) ({direct_count} direct, {indirect_count} indirect) would be touched "
            "by a change here."
        )

    if affected_apis_count:
        sentences.append(
            f"{affected_apis_count} dependent(s) are live API endpoints, so a regression "
            "wouldn't stay internal — it could surface directly to external callers."
        )
    elif affected_services_count:
        sentences.append(
            f"{affected_services_count} dependent(s) sit in service-layer components, so the "
            "blast radius reaches business logic even though no API endpoint is directly exposed."
        )
    elif total > 0:
        sentences.append(
            "None of its dependents are exposed API endpoints or named service-layer "
            "components, which keeps the practical (externally-visible) blast radius smaller "
            "than the raw dependent count suggests."
        )

    if total > 0 and affected_tests_count == 0:
        sentences.append(
            "No test exercises any dependent, so a regression here would most likely go "
            "unnoticed until it reaches production rather than being caught automatically."
        )
    elif affected_tests_count >= total > 0:
        sentences.append(
            f"{affected_tests_count} test(s) exercise its dependents, giving a reasonable "
            "automated safety net for this change."
        )
    elif affected_tests_count:
        sentences.append(
            f"Only {affected_tests_count} of its {total} dependent(s) are exercised by a test, "
            "so coverage is partial — some regression paths could still slip through untested."
        )

    if external_names:
        sentences.append(
            f"Its own file also touches external dependencies ({', '.join(external_names[:5])}), "
            "adding an integration-boundary risk on top of the internal fan-out — a subtle "
            "behavior change could affect how this code interacts with them."
        )

    if target_degree >= 15 and total <= 10:
        sentences.append(
            f"It also sits at a structurally central point in the call graph (degree "
            f"{target_degree}), which raises risk beyond what the dependent count alone implies."
        )

    sentences.append(f"Taken together, these factors put the overall risk at {risk_level}.")
    return " ".join(sentences)
