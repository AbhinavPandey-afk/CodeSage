from analysis.reconstruction.models import ArchitectureComponent, ArchitectureModel, ComponentRelationship
from analysis.smells.architecture_violations import (
    detect_architecture_violations,
    detect_circular_component_dependencies,
    detect_excessive_coupling,
    detect_layer_violations,
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


def _model(components, relationships):
    return ArchitectureModel(repo_id="r1", components=components, relationships=relationships, truncated=False)


def test_data_access_calling_api_is_a_high_severity_boundary_violation():
    model = _model(
        [_component("app/api", "api"), _component("app/data", "data_access")],
        [_relationship("app/data", "app/api")],
    )
    findings = detect_layer_violations(model)
    assert len(findings) == 1
    assert findings[0].smell_type == "architecture_boundary_violation"
    assert findings[0].severity == "HIGH"


def test_service_calling_api_is_a_medium_severity_boundary_violation():
    model = _model(
        [_component("app/api", "api"), _component("app/services", "service")],
        [_relationship("app/services", "app/api")],
    )
    findings = detect_layer_violations(model)
    assert len(findings) == 1
    assert findings[0].severity == "MEDIUM"


def test_forward_layered_calls_are_not_flagged():
    model = _model(
        [_component("app/api", "api"), _component("app/services", "service"), _component("app/data", "data_access")],
        [_relationship("app/api", "app/services"), _relationship("app/services", "app/data")],
    )
    assert detect_layer_violations(model) == []


def test_api_calling_data_access_directly_is_flagged_only_when_service_layer_exists():
    with_service = _model(
        [_component("app/api", "api"), _component("app/services", "service"), _component("app/data", "data_access")],
        [_relationship("app/api", "app/data")],
    )
    findings = detect_layer_violations(with_service)
    assert len(findings) == 1
    assert findings[0].smell_type == "layer_skip"

    without_service = _model(
        [_component("app/api", "api"), _component("app/data", "data_access")],
        [_relationship("app/api", "app/data")],
    )
    assert detect_layer_violations(without_service) == []


def test_detects_mutual_component_dependency():
    model = _model(
        [_component("app/a", "service"), _component("app/b", "service")],
        [_relationship("app/a", "app/b"), _relationship("app/b", "app/a")],
    )
    findings = detect_circular_component_dependencies(model)
    assert len(findings) == 1
    assert findings[0].smell_type == "circular_component_dependency"
    assert len(findings[0].affected) == 2


def test_no_cycle_without_reverse_edge():
    model = _model(
        [_component("app/a", "service"), _component("app/b", "service")],
        [_relationship("app/a", "app/b")],
    )
    assert detect_circular_component_dependencies(model) == []


def test_excessive_coupling_flags_high_degree_component():
    hub = _component("app/hub", "service")
    peers = [_component(f"app/p{i}", "service") for i in range(10)]
    relationships = [_relationship("app/hub", p.id) for p in peers]
    model = _model([hub, *peers], relationships)

    findings = detect_excessive_coupling(model)
    hub_findings = [f for f in findings if "app/hub" in f.title]
    assert len(hub_findings) == 1
    assert hub_findings[0].severity == "HIGH"


def test_low_degree_components_are_not_flagged_as_coupled():
    a, b = _component("app/a", "service"), _component("app/b", "service")
    model = _model([a, b], [_relationship("app/a", "app/b")])
    assert detect_excessive_coupling(model) == []


def test_combined_detection_runs_all_checks():
    model = _model(
        [_component("app/api", "api"), _component("app/data", "data_access")],
        [_relationship("app/data", "app/api")],
    )
    findings = detect_architecture_violations(model)
    assert any(f.smell_type == "architecture_boundary_violation" for f in findings)
