"""Architecture Analysis V2 §17: overlapping findings sharing a root entity
(a god_class and one of its own large_function methods) must be
cross-referenced, never suppressed or merged."""
from analysis.smells.detector import _link_related_findings
from analysis.smells.models import AffectedSymbol, Smell


def _smell(id_, smell_type, qualified_name):
    return Smell(
        id=id_, smell_type=smell_type, severity="MEDIUM", confidence=0.6,
        title="t", explanation="e", evidence="ev",
        affected=[AffectedSymbol(qualified_name, f"{qualified_name}.py", 1, 10)],
    )


def test_god_class_and_its_own_method_get_cross_referenced():
    god = _smell("g1", "god_class", "pkg.Flask")
    method = _smell("l1", "large_function", "pkg.Flask.make_response")
    unrelated = _smell("l2", "large_function", "pkg.Other.run")

    linked = _link_related_findings([god, method, unrelated])
    by_id = {s.id: s for s in linked}

    assert by_id["l1"].id in ["l1"]  # sanity
    assert "l1" in by_id["g1"].related_finding_ids
    assert "g1" in by_id["l1"].related_finding_ids
    assert by_id["l2"].related_finding_ids == []  # unrelated class, not linked


def test_neither_finding_is_suppressed_or_merged():
    god = _smell("g1", "god_class", "pkg.Flask")
    method = _smell("l1", "large_function", "pkg.Flask.make_response")
    linked = _link_related_findings([god, method])
    assert len(linked) == 2  # both findings still present, independently


def test_no_false_link_for_unrelated_prefix_that_is_not_a_method():
    # "pkg.FlaskTask" is not a method of "pkg.Flask" -- a shared string
    # prefix without a "." boundary must not be treated as containment.
    god = _smell("g1", "god_class", "pkg.Flask")
    lookalike = _smell("l1", "large_function", "pkg.FlaskTask.run")
    linked = _link_related_findings([god, lookalike])
    by_id = {s.id: s for s in linked}
    assert by_id["g1"].related_finding_ids == []
    assert by_id["l1"].related_finding_ids == []


def test_no_god_classes_or_large_functions_is_a_no_op():
    only_dead_code = _smell("d1", "dead_code_candidate", "pkg.unused")
    linked = _link_related_findings([only_dead_code])
    assert linked[0].related_finding_ids == []
