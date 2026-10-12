"""Architecture Analysis V2: finding confidence is distinct from severity and
from resolver confidence (CLAUDE.md V2 §2/§3), and context flags are
evidence-derived, never subjective (§4/§5/§6)."""
from analysis.reconstruction.models import ArchitectureComponent, ArchitectureModel, ComponentRelationship
from analysis.smells.architecture_violations import (
    circular_component_dependency_records,
    excessive_coupling_records,
    layer_violation_records,
)
from analysis.smells.detector import (
    circular_dependency_confidence,
    dead_code_confidence,
    god_class_confidence,
    large_function_confidence,
)


def _component(id_, role, **overrides):
    defaults = dict(
        id=id_, name=id_, role=role, file_count=1, symbol_count=1, files=[f"{id_}/mod.py"],
        confidence=0.8, confidence_label="Confirmed", evidence=[],
    )
    defaults.update(overrides)
    return ArchitectureComponent(**defaults)


def _relationship(source_id, target_id, call_count=1, confidence=0.9, **overrides):
    defaults = dict(
        source_id=source_id, target_id=target_id, call_count=call_count, confidence=confidence,
        confidence_label="Confirmed", evidence=[f"e.g. {source_id}/mod.py:10"],
    )
    defaults.update(overrides)
    return ComponentRelationship(**defaults)


def _model(components, relationships=()):
    return ArchitectureModel(repo_id="r1", components=components, relationships=list(relationships), truncated=False)


# --- god_class / large_function / dead_code: symbol-level confidence -------


def test_god_class_confidence_is_lower_in_a_supporting_component():
    model = _model([_component("tests/fixtures", "test")])
    confidence, flags = god_class_confidence(model, "tests/fixtures/mod.py")
    assert "SUPPORTING_STRUCTURE" in flags
    baseline, _ = god_class_confidence(_model([_component("app/core", "service")]), "app/core/mod.py")
    assert confidence < baseline


def test_god_class_confidence_is_lower_for_a_widely_depended_on_hub():
    hub = _component("app/core", "service")
    peers = [_component(f"app/p{i}", "service") for i in range(4)]
    rels = [_relationship(f"app/p{i}", "app/core") for i in range(4)]
    model = _model([hub, *peers], rels)
    confidence, flags = god_class_confidence(model, "app/core/mod.py")
    assert "FRAMEWORK_HUB" in flags
    assert confidence < 0.6  # below the unadjusted base


def test_god_class_confidence_always_carries_the_method_count_heuristic_flag():
    model = _model([_component("app/core", "service")])
    _, flags = god_class_confidence(model, "app/core/mod.py")
    assert "METHOD_COUNT_HEURISTIC" in flags


def test_large_function_confidence_always_carries_the_length_based_heuristic_flag():
    model = _model([_component("app/core", "service")])
    _, flags = large_function_confidence(model, "app/core/mod.py")
    assert "LENGTH_BASED_HEURISTIC" in flags


def test_large_function_confidence_is_lower_in_supporting_structure():
    supporting = _model([_component("docs/x", "other")])
    runtime = _model([_component("app/core", "service")])
    supporting_conf, _ = large_function_confidence(supporting, "docs/x/mod.py")
    runtime_conf, _ = large_function_confidence(runtime, "app/core/mod.py")
    assert supporting_conf < runtime_conf


def test_dead_code_confidence_is_low_and_always_flags_dynamic_dispatch_risk():
    model = _model([_component("app/core", "service")])
    confidence, flags = dead_code_confidence(model, "app/core/mod.py")
    assert confidence < 0.5  # absence-of-evidence is always weak evidence
    assert "DYNAMIC_DISPATCH_RISK" in flags


def test_dead_code_confidence_drops_further_in_supporting_structure():
    supporting = _model([_component("docs/x", "other")])
    runtime = _model([_component("app/core", "service")])
    supporting_conf, flags = dead_code_confidence(supporting, "docs/x/mod.py")
    runtime_conf, _ = dead_code_confidence(runtime, "app/core/mod.py")
    assert supporting_conf < runtime_conf
    assert "SUPPORTING_STRUCTURE" in flags


def test_circular_dependency_confidence_drops_for_intra_class_delegation():
    intra_class = ["pkg.Foo.a", "pkg.Foo.b", "pkg.Foo.c"]
    cross_module = ["pkg.a.Foo.run", "pkg.b.Bar.run", "pkg.c.Baz.run"]
    intra_conf, intra_flags = circular_dependency_confidence(intra_class, {"pkg/foo.py"})
    cross_conf, cross_flags = circular_dependency_confidence(cross_module, {"pkg/a.py", "pkg/b.py", "pkg/c.py"})
    assert "INTRA_CLASS_DELEGATION" in intra_flags
    assert "INTRA_CLASS_DELEGATION" not in cross_flags
    assert intra_conf < cross_conf


# --- architecture-violation-level confidence --------------------------------


def test_boundary_violation_confidence_is_not_the_raw_resolver_confidence():
    """Resolver confidence must be blended with the layering base, never
    copied straight through -- CLAUDE.md V2 §2's core requirement."""
    model = _model(
        [_component("app/api", "api"), _component("app/data", "data_access")],
        [_relationship("app/data", "app/api", confidence=0.9)],
    )
    findings = layer_violation_records(model)
    assert len(findings) == 1
    assert findings[0].smell.confidence != 0.9
    assert "HEURISTIC_LAYERING" in findings[0].smell.context_flags


def test_boundary_violation_evidence_details_disclose_roles_and_resolver_confidence():
    model = _model(
        [_component("app/api", "api"), _component("app/data", "data_access")],
        [_relationship("app/data", "app/api", confidence=0.9)],
    )
    findings = layer_violation_records(model)
    details = findings[0].smell.evidence_details
    assert len(details) == 1
    assert details[0].source_role == "data_access"
    assert details[0].target_role == "api"
    assert details[0].resolver_confidence == 0.9


def test_circular_component_dependency_flags_test_participant_and_lowers_confidence():
    model = _model(
        [_component("tests", "test"), _component("app/core", "service")],
        [_relationship("tests", "app/core"), _relationship("app/core", "tests")],
    )
    findings = circular_component_dependency_records(model)
    assert len(findings) == 1
    smell = findings[0].smell
    assert "EXPECTED_TEST_DEPENDENCY" in smell.context_flags
    assert smell.confidence < 0.5  # heavily discounted, but the finding still exists
    assert smell.severity == "MEDIUM"  # severity (the structural fact) is unaffected


def test_circular_component_dependency_between_two_runtime_components_keeps_higher_confidence():
    model = _model(
        [_component("app/a", "service"), _component("app/b", "service")],
        [_relationship("app/a", "app/b"), _relationship("app/b", "app/a")],
    )
    findings = circular_component_dependency_records(model)
    assert findings[0].smell.confidence > 0.5
    assert "EXPECTED_TEST_DEPENDENCY" not in findings[0].smell.context_flags


def test_excessive_coupling_flags_framework_hub_for_incoming_heavy_component():
    hub = _component("app/core", "external_integration")
    peers = [_component(f"app/p{i}", "service") for i in range(6)]
    rels = [_relationship(f"app/p{i}", "app/core") for i in range(6)]
    model = _model([hub, *peers], rels)
    findings = excessive_coupling_records(model)
    hub_finding = next(f for f in findings if f.component_ids == ("app/core",))
    assert "FRAMEWORK_HUB" in hub_finding.smell.context_flags
    assert hub_finding.smell.severity in ("MEDIUM", "HIGH")  # observed degree/severity unchanged


def test_every_violation_finding_is_optimization_supported():
    model = _model(
        [_component("app/api", "api"), _component("app/data", "data_access")],
        [_relationship("app/data", "app/api")],
    )
    for f in layer_violation_records(model):
        assert f.smell.optimization_supported is True
