from analysis.optimization.engine import _build_proposal, _risk_and_confidence
from analysis.optimization.models import RepresentativeImpact
from analysis.reconstruction.models import ArchitectureComponent, ArchitectureModel
from analysis.smells.architecture_violations import ViolationRecord
from analysis.smells.models import Smell


def _component(id_, role, files=None):
    return ArchitectureComponent(
        id=id_, name=id_, role=role, file_count=1, symbol_count=1, files=files or [f"{id_}/mod.py"],
        confidence=0.8, confidence_label="Confirmed", evidence=[],
    )


def _model(components):
    return ArchitectureModel(repo_id="r1", components=components, relationships=[], truncated=False)


def _record(kind, component_ids, severity="HIGH"):
    smell = Smell(
        id=f"test-{kind}-{'-'.join(component_ids)}", smell_type="x", severity=severity, confidence=0.7,
        title=f"problem involving {component_ids}",
        explanation="...", evidence="3 call(s)",
    )
    return ViolationRecord(smell=smell, kind=kind, component_ids=component_ids)


def test_boundary_proposal_names_the_real_components():
    model = _model([_component("app/api", "api"), _component("app/data", "data_access")])
    record = _record("boundary", ("app/data", "app/api"))
    proposal = _build_proposal("opt-0", record, model, impact=None)

    assert proposal.goal == "enforce_layering"
    assert "app/data" in proposal.proposed_change
    assert "app/api" in proposal.proposed_change
    assert proposal.affected_components == ["app/data", "app/api"]
    assert set(proposal.affected_files) == {"app/data/mod.py", "app/api/mod.py"}


def test_layer_skip_proposal_mentions_the_service_layer():
    model = _model([_component("app/api", "api"), _component("app/data", "data_access")])
    record = _record("layer_skip", ("app/api", "app/data"), severity="MEDIUM")
    proposal = _build_proposal("opt-0", record, model, impact=None)

    assert proposal.goal == "enforce_layering"
    assert "service layer" in proposal.proposed_change


def test_cycle_proposal_suggests_extraction():
    model = _model([_component("app/a", "service"), _component("app/b", "service")])
    record = _record("cycle", ("app/a", "app/b"), severity="MEDIUM")
    proposal = _build_proposal("opt-0", record, model, impact=None)

    assert proposal.goal == "reduce_circularity"
    assert "cycle" in proposal.proposed_change.lower()


def test_coupling_proposal_suggests_splitting():
    model = _model([_component("app/hub", "service")])
    record = _record("coupling", ("app/hub",), severity="HIGH")
    proposal = _build_proposal("opt-0", record, model, impact=None)

    assert proposal.goal == "reduce_coupling"
    assert "split" in proposal.proposed_change.lower()
    assert proposal.affected_components == ["app/hub"]


def test_risk_falls_back_to_severity_without_impact_data():
    record = _record("coupling", ("app/hub",), severity="HIGH")
    risk_level, confidence = _risk_and_confidence(record, impact=None)
    assert risk_level == "HIGH"
    assert 0 < confidence <= 1


def test_risk_prefers_real_impact_analysis_when_available():
    record = _record("coupling", ("app/hub",), severity="MEDIUM")
    impact = RepresentativeImpact(
        symbol_qualified_name="app.hub.Thing", direct_dependents=20, indirect_dependents=5, risk_level="CRITICAL",
    )
    risk_level, confidence = _risk_and_confidence(record, impact)
    assert risk_level == "CRITICAL"
    assert confidence > 0.6


def test_proposal_never_claims_confirmed_without_strong_evidence():
    record = _record("coupling", ("app/hub",), severity="LOW")
    _, confidence = _risk_and_confidence(record, impact=None)
    assert confidence < 0.75  # must not read as "Confirmed" on weak evidence alone


def test_proposal_finding_id_matches_the_underlying_violation_records_smell_id():
    """V2 §15: the explicit link replacing the old implicit title-string
    correlation between /smells and /optimization."""
    model = _model([_component("app/api", "api"), _component("app/data", "data_access")])
    record = _record("boundary", ("app/data", "app/api"))
    proposal = _build_proposal("opt-0", record, model, impact=None)
    assert proposal.finding_id == record.smell.id
    assert proposal.finding_id == "test-boundary-app/data-app/api"
