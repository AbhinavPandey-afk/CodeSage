"""relationship_kind/hop_count (CLAUDE.md §37 OBSERVED vs INFERRED): the
resolver must classify DIRECT vs INDIRECT deterministically from graph shape
alone — never from steps.length, since a DIRECT pair can carry more than one
parallel edge (e.g. both CALLS and IMPORTS at once)."""
from graph.queries.relationship import (
    SymbolRef,
    _direct_result,
    _not_connected_result,
    _path_result,
)


def _symbol(uid, name) -> SymbolRef:
    return SymbolRef(uid=uid, symbol_type="function", qualified_name=name, file_path=f"{name}.py")


def test_direct_result_is_one_hop():
    source, target = _symbol("u1", "pkg.a"), _symbol("u2", "pkg.b")
    row = {"rel_type": "CALLS", "start_uid": "u1", "source_file": "pkg/a.py", "source_line": 5, "confidence": 0.9}

    result = _direct_result(source, target, [row])

    assert result.connected is True
    assert result.relationship_kind == "DIRECT"
    assert result.hop_count == 1
    assert len(result.steps) == 1


def test_direct_result_with_multiple_parallel_edges_is_still_one_hop():
    """A -[CALLS]-> B and A -[IMPORTS]-> B at once: two direct edges, not a
    two-hop chain. hop_count must stay 1 and both steps must be preserved."""
    source, target = _symbol("u1", "pkg.a"), _symbol("u2", "pkg.b")
    rows = [
        {"rel_type": "CALLS", "start_uid": "u1", "source_file": "pkg/a.py", "source_line": 5, "confidence": 0.9},
        {"rel_type": "IMPORTS", "start_uid": "u1", "source_file": "pkg/a.py", "source_line": 1, "confidence": 1.0},
    ]

    result = _direct_result(source, target, rows)

    assert result.relationship_kind == "DIRECT"
    assert result.hop_count == 1
    assert len(result.steps) == 2
    assert {s.relationship_type for s in result.steps} == {"CALLS", "IMPORTS"}


def test_path_result_hop_count_matches_edge_count():
    source, target = _symbol("u1", "pkg.a"), _symbol("u3", "pkg.c")
    path_nodes = [
        {"uid": "u1", "qualified_name": "pkg.a"},
        {"uid": "u2", "qualified_name": "pkg.b"},
        {"uid": "u3", "qualified_name": "pkg.c"},
    ]
    path_rels = [
        {"rel_type": "CONTAINS", "start_uid": "u1", "source_file": "pkg/a.py", "source_line": 3, "confidence": 1.0},
        {"rel_type": "CALLS", "start_uid": "u2", "source_file": "pkg/b.py", "source_line": 7, "confidence": 0.75},
    ]

    result = _path_result(source, target, path_nodes, path_rels)

    assert result.connected is True
    assert result.relationship_kind == "INDIRECT"
    assert result.hop_count == 2
    assert [s.relationship_type for s in result.steps] == ["CONTAINS", "CALLS"]


def test_not_connected_result_has_no_kind_or_hop_count():
    source, target = _symbol("u1", "pkg.a"), _symbol("u2", "pkg.z")

    result = _not_connected_result(source, target)

    assert result.connected is False
    assert result.steps == []
    assert result.relationship_kind is None
    assert result.hop_count is None
