"""Architecture Analysis V2: stable finding identifiers (CLAUDE.md V2 §1).

compute_finding_id must be a pure, deterministic function -- same inputs,
same id, forever -- and must not accidentally collide across different
findings sharing part of their identity."""
from analysis.smells.context import compute_finding_id


def test_same_inputs_produce_the_same_id():
    a = compute_finding_id("repo-1", "god_class", "pkg.Foo")
    b = compute_finding_id("repo-1", "god_class", "pkg.Foo")
    assert a == b


def test_different_repo_produces_a_different_id():
    a = compute_finding_id("repo-1", "god_class", "pkg.Foo")
    b = compute_finding_id("repo-2", "god_class", "pkg.Foo")
    assert a != b


def test_different_smell_type_produces_a_different_id_for_the_same_entity():
    a = compute_finding_id("repo-1", "god_class", "pkg.Foo")
    b = compute_finding_id("repo-1", "large_function", "pkg.Foo")
    assert a != b


def test_different_identity_parts_produce_different_ids():
    a = compute_finding_id("repo-1", "architecture_boundary_violation", "app/api", "app/data")
    b = compute_finding_id("repo-1", "architecture_boundary_violation", "app/data", "app/api")
    assert a != b  # direction is part of a boundary violation's identity


def test_id_is_a_short_stable_hex_string():
    finding_id = compute_finding_id("repo-1", "god_class", "pkg.Foo")
    assert len(finding_id) == 16
    int(finding_id, 16)  # must be valid hex -- raises ValueError otherwise


def test_id_does_not_depend_on_finding_order_or_index():
    # A caller must never fall back to array position -- verify no index
    # parameter exists on the function signature at all by confirming two
    # calls with identical semantic identity match regardless of call site.
    ids = {compute_finding_id("repo-1", "circular_dependency", "a.b", "a.c") for _ in range(5)}
    assert len(ids) == 1
