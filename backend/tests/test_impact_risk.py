from analysis.impact.risk import score_risk


def _score(**overrides):
    defaults = dict(
        direct_count=0, indirect_count=0, affected_apis_count=0,
        affected_services_count=0, affected_tests_count=0,
        external_dependency_count=0, target_degree=0,
    )
    defaults.update(overrides)
    return score_risk(**defaults)


def test_no_dependents_is_low_risk():
    level, score, signals = _score()
    assert level == "LOW"
    assert score == 0


def test_many_dependents_no_tests_no_api_is_still_bounded():
    level, score, signals = _score(direct_count=20, indirect_count=10)
    # 30 total dependents -> 4 points, no test coverage -> +2 = 6 -> HIGH, not CRITICAL
    assert level == "HIGH"
    assert score == 6


def test_api_and_missing_tests_pushes_risk_up():
    low_level, low_score, _ = _score(direct_count=2, indirect_count=0)
    high_level, high_score, _ = _score(direct_count=2, indirect_count=0, affected_apis_count=1)
    assert high_score > low_score


def test_test_coverage_reduces_score_relative_to_no_coverage():
    uncovered_level, uncovered_score, _ = _score(direct_count=5, indirect_count=0)
    covered_level, covered_score, _ = _score(direct_count=5, indirect_count=0, affected_tests_count=3)
    assert covered_score < uncovered_score


def test_everything_maxed_out_is_critical():
    level, score, signals = _score(
        direct_count=15, indirect_count=20, affected_apis_count=3,
        affected_services_count=2, affected_tests_count=0,
        external_dependency_count=2, target_degree=20,
    )
    assert level == "CRITICAL"
    assert score >= 8


def test_signals_are_transparent_and_sum_to_score():
    level, score, signals = _score(direct_count=5, indirect_count=1, affected_apis_count=1)
    assert sum(s.points for s in signals) == score
    assert any("dependents" in s.name.lower() for s in signals)
