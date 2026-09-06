"""Architecture Optimization engine (CLAUDE.md §19/§20/§26/§34 Phase 3).

Workflow: Current Architecture -> Architecture Analysis -> Problems ->
Optimization Strategy -> Proposed Architecture. Every proposal is generated
from a specific ViolationRecord produced by
analysis.smells.architecture_violations -- there is no free-standing
"propose an architecture" step, and no LLM call anywhere in this module.
Optimization is a recommendation only (CLAUDE.md §19): nothing here modifies
the repository.

The proposal-assembly logic (_build_proposal, _proposal_text,
_risk_and_confidence, _affected_files) is deliberately pure -- it takes an
already-reconstructed ArchitectureModel and an optional pre-fetched
RepresentativeImpact, so it is unit-testable without Neo4j. Only
generate_optimization_report() and _representative_impact() touch the graph.
"""
from analysis.impact.engine import SymbolNotFoundError, analyze_impact
from analysis.optimization.models import OptimizationProposal, OptimizationReport, RepresentativeImpact
from analysis.reconstruction.engine import reconstruct_architecture
from analysis.reconstruction.models import ArchitectureModel
from analysis.smells.architecture_violations import ViolationRecord, all_violation_records
from graph.neo4j.client import get_driver

_CONFIRMED_THRESHOLD = 0.75
_INFERRED_THRESHOLD = 0.4

_GOAL_BY_KIND = {
    "boundary": "enforce_layering",
    "layer_skip": "enforce_layering",
    "cycle": "reduce_circularity",
    "coupling": "reduce_coupling",
}

_RISK_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _confidence_label(score: float) -> str:
    if score >= _CONFIRMED_THRESHOLD:
        return "Confirmed"
    if score >= _INFERRED_THRESHOLD:
        return "Inferred"
    return "Uncertain"


def _top_symbol_uid(repo_id: str, files: list[str]) -> str | None:
    if not files:
        return None
    with get_driver().session() as session:
        row = session.run(
            "MATCH (s:Symbol {repo_id: $repo_id}) "
            "WHERE s.symbol_type IN ['class', 'function', 'method'] AND s.file_path IN $files "
            "OPTIONAL MATCH (s)-[r:CALLS|INHERITS]-() "
            "WITH s, count(r) AS degree "
            "RETURN s.uid AS uid ORDER BY degree DESC LIMIT 1",
            repo_id=repo_id, files=files,
        ).single()
    return row["uid"] if row else None


def _representative_impact(repo_id: str, files: list[str]) -> RepresentativeImpact | None:
    uid = _top_symbol_uid(repo_id, files)
    if uid is None:
        return None
    try:
        report = analyze_impact(repo_id, uid)
    except SymbolNotFoundError:
        return None
    return RepresentativeImpact(
        symbol_qualified_name=report.target_qualified_name,
        direct_dependents=len(report.direct_dependents),
        indirect_dependents=len(report.indirect_dependents),
        risk_level=report.risk_level,
    )


def _proposal_text(record: ViolationRecord, model: ArchitectureModel) -> tuple[str, str, str]:
    """Returns (proposed_change, expected_benefit, potential_risk), templated
    from the actual components involved -- never a generic example."""
    by_id = {c.id: c for c in model.components}
    ids = record.component_ids

    if record.kind == "boundary":
        src = by_id.get(ids[0])
        dst = by_id.get(ids[1])
        src_name, dst_name = src.name if src else ids[0], dst.name if dst else ids[1]
        return (
            f"Remove the direct call from '{src_name}' to '{dst_name}'. If '{src_name}' needs to "
            f"trigger behavior in '{dst_name}', invert the dependency (e.g. an event, callback, or "
            f"interface owned by '{src_name}') so dependencies keep flowing downward through the layers.",
            f"Restores unidirectional layering so '{dst_name}' can be understood, tested, and changed "
            f"without needing to know about '{src_name}'.",
            f"'{src_name}' and '{dst_name}' both need code changes to invert the dependency; existing "
            "callers of the removed direct call must be updated.",
        )
    if record.kind == "layer_skip":
        src = by_id.get(ids[0])
        dst = by_id.get(ids[1])
        src_name, dst_name = src.name if src else ids[0], dst.name if dst else ids[1]
        return (
            f"Route the call from '{src_name}' through the existing service layer instead of calling "
            f"'{dst_name}' directly.",
            "Keeps request-handling code decoupled from persistence/integration details, and gives the "
            "service layer a single place to enforce business rules for this operation.",
            f"Requires adding or extending a service-layer method and updating '{src_name}' to call it "
            f"instead of '{dst_name}' directly.",
        )
    if record.kind == "cycle":
        a = by_id.get(ids[0])
        b = by_id.get(ids[1])
        a_name, b_name = a.name if a else ids[0], b.name if b else ids[1]
        return (
            f"Break the cycle between '{a_name}' and '{b_name}' by extracting their shared "
            "responsibility into a new component that both depend on, or by making one direction "
            "depend on an abstraction rather than the other component directly.",
            f"'{a_name}' and '{b_name}' become independently understandable, testable, and reusable.",
            "Extracting a shared component is a structural change that touches both sides of the "
            "cycle and their existing tests.",
        )
    # "coupling"
    comp = by_id.get(ids[0])
    comp_name = comp.name if comp else ids[0]
    return (
        f"Split '{comp_name}' into smaller, more focused components along its distinct "
        "responsibilities, or introduce a facade so its dependents interact through a narrower interface.",
        f"Reduces the blast radius of future changes to '{comp_name}' and makes each resulting piece "
        "easier to reason about in isolation.",
        f"Splitting '{comp_name}' touches every one of its current dependents' import paths and is the "
        "largest-effort recommendation in this report.",
    )


def _risk_and_confidence(record: ViolationRecord, impact: RepresentativeImpact | None) -> tuple[str, float]:
    """Deterministic risk/confidence from evidence already computed for the
    underlying violation and (when available) a real impact-analysis run --
    never invented by the LLM (CLAUDE.md §20/§38)."""
    base_confidence = {"HIGH": 0.8, "MEDIUM": 0.6, "LOW": 0.4}.get(record.smell.severity, 0.5)
    if impact is not None:
        return impact.risk_level, min(base_confidence + 0.1, 0.95)
    # No representative symbol found (e.g. an empty component) -- fall back
    # to the violation's own severity as a proxy for how disruptive fixing it is.
    return record.smell.severity, base_confidence


def _affected_files(record: ViolationRecord, model: ArchitectureModel) -> list[str]:
    by_id = {c.id: c for c in model.components}
    files: list[str] = []
    for cid in record.component_ids:
        comp = by_id.get(cid)
        if comp:
            files.extend(comp.files)
    return files


def _build_proposal(
    proposal_id: str, record: ViolationRecord, model: ArchitectureModel, impact: RepresentativeImpact | None
) -> OptimizationProposal:
    files = _affected_files(record, model)
    proposed_change, expected_benefit, potential_risk = _proposal_text(record, model)
    risk_level, confidence = _risk_and_confidence(record, impact)
    return OptimizationProposal(
        id=proposal_id,
        goal=_GOAL_BY_KIND[record.kind],
        problem=record.smell.title,
        evidence=record.smell.evidence,
        proposed_change=proposed_change,
        expected_benefit=expected_benefit,
        potential_risk=potential_risk,
        risk_level=risk_level,
        confidence=confidence,
        confidence_label=_confidence_label(confidence),
        affected_components=list(record.component_ids),
        affected_files=files,
        representative_impact=impact,
    )


def _summarize(model: ArchitectureModel, violation_count: int) -> str:
    if not model.components:
        return "No architectural components could be reconstructed for this repository."
    return (
        f"{len(model.components)} architectural component(s) reconstructed, "
        f"{len(model.relationships)} inter-component relationship(s), "
        f"{violation_count} structural violation(s) found."
    )


def generate_optimization_report(repo_id: str) -> OptimizationReport:
    model = reconstruct_architecture(repo_id)
    records = all_violation_records(model)

    proposals = [
        _build_proposal(f"opt-{i}", record, model, _representative_impact(repo_id, _affected_files(record, model)))
        for i, record in enumerate(records)
    ]
    proposals.sort(key=lambda p: _RISK_ORDER.get(p.risk_level, len(_RISK_ORDER)))

    detection_notes = [
        "Every proposal here maps to a specific finding from Architecture Analysis -- "
        "there is no free-standing architecture redesign step.",
        "Risk and confidence are computed deterministically from the underlying violation's "
        "severity and, where a representative symbol could be identified, a real impact-analysis "
        "run against it -- never invented by the LLM.",
        "This is a design recommendation only. Nothing here modifies the repository.",
    ]
    if not records:
        detection_notes.insert(0, "No structural violations were found, so no optimizations are proposed.")

    return OptimizationReport(
        repo_id=repo_id,
        current_architecture_summary=_summarize(model, len(records)),
        proposals=proposals,
        detection_notes=detection_notes,
    )
