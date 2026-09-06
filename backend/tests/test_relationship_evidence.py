from ai.retrieval.relationship_service import _render_evidence, not_connected_explanation
from graph.queries.relationship import RelationshipResult, RelationshipStep, SymbolRef


def _symbol(uid, name) -> SymbolRef:
    return SymbolRef(uid=uid, symbol_type="function", qualified_name=name, file_path=f"{name}.py")


def test_not_connected_explanation_names_both_symbols_and_no_llm_needed():
    text = not_connected_explanation("pkg.a", "pkg.b")
    assert "pkg.a" in text
    assert "pkg.b" in text
    assert "No structural relationship" in text


def test_render_evidence_includes_every_step_with_citation():
    source = _symbol("u1", "pkg.a")
    target = _symbol("u2", "pkg.b")
    result = RelationshipResult(
        source=source,
        target=target,
        connected=True,
        steps=[
            RelationshipStep(
                from_qualified_name="pkg.a", to_qualified_name="pkg.b",
                relationship_type="CALLS", source_file="pkg/a.py", source_line=12, confidence=0.9,
            )
        ],
    )
    block = _render_evidence(result)
    assert "pkg.a" in block and "pkg.b" in block
    assert "CALLS" in block
    assert "pkg/a.py:12" in block
    assert "0.90" in block


def test_render_evidence_handles_multi_hop_path():
    source = _symbol("u1", "pkg.a")
    target = _symbol("u3", "pkg.c")
    result = RelationshipResult(
        source=source,
        target=target,
        connected=True,
        steps=[
            RelationshipStep("pkg.a", "pkg.b", "CALLS", "pkg/a.py", 5, 0.8),
            RelationshipStep("pkg.b", "pkg.c", "IMPORTS", "pkg/b.py", 1, None),
        ],
    )
    block = _render_evidence(result)
    assert block.count("->") == 2
    assert "n/a" in block  # missing confidence rendered explicitly, never invented
