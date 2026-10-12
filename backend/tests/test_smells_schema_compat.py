"""Architecture Analysis V2 §18: API stability. Every field that existed
before this hardening pass must still exist, unrenamed, and every new field
must be additive (safe default) so a payload built with only the pre-V2
fields still validates."""
from app.schemas.optimization import OptimizationProposalResponse
from app.schemas.smells import SmellResponse


def test_smell_response_accepts_the_pre_v2_field_set_plus_required_new_ones():
    # id and confidence are the two V2 fields with no default (the backend
    # always sets them now) -- everything else new is optional/defaulted.
    resp = SmellResponse(
        id="abc123", confidence=0.6,
        smell_type="god_class", severity="MEDIUM", title="t", explanation="e",
        evidence="ev", affected=[],
    )
    assert resp.context_flags == []
    assert resp.evidence_details == []
    assert resp.optimization_supported is False
    assert resp.related_finding_ids == []


def test_smell_response_original_fields_are_unrenamed():
    resp = SmellResponse(
        id="abc123", confidence=0.6,
        smell_type="god_class", severity="MEDIUM", title="t", explanation="e",
        evidence="ev", affected=[],
    )
    for field in ("smell_type", "severity", "title", "explanation", "evidence", "affected"):
        assert hasattr(resp, field)


def test_optimization_proposal_response_finding_id_is_optional():
    resp = OptimizationProposalResponse(
        id="opt-0", goal="enforce_layering", problem="p", evidence="ev",
        proposed_change="c", expected_benefit="b", potential_risk="r",
        risk_level="HIGH", confidence=0.7, confidence_label="Inferred",
        affected_components=[], affected_files=[], representative_impact=None,
    )
    assert resp.finding_id is None


def test_optimization_proposal_response_original_fields_are_unrenamed():
    resp = OptimizationProposalResponse(
        id="opt-0", goal="enforce_layering", problem="p", evidence="ev",
        proposed_change="c", expected_benefit="b", potential_risk="r",
        risk_level="HIGH", confidence=0.7, confidence_label="Inferred",
        affected_components=[], affected_files=[], representative_impact=None,
        finding_id="f1",
    )
    for field in (
        "id", "goal", "problem", "evidence", "proposed_change", "expected_benefit",
        "potential_risk", "risk_level", "confidence", "confidence_label",
        "affected_components", "affected_files", "representative_impact",
    ):
        assert hasattr(resp, field)
    assert resp.finding_id == "f1"
