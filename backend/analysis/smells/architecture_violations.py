"""Architecture-level violation detection (CLAUDE.md §18/§6).

Reasons over the reconstructed ArchitectureModel's components and
relationships -- a different granularity from detector.py's per-symbol
checks (circular dependency, god class, ...). Findings share the same Smell
output shape so they surface in the same Architecture Analysis list per
CLAUDE.md's "Smell Detection + Architecture Violations merge into
Architecture Analysis" rule -- never a separate endpoint or tab.

V2 confidence model: every rule below blends the underlying relationship's
own resolver confidence (how sure the cross-file CALL resolver was that this
specific edge is real) with structural context signals (is either endpoint
test/supporting infrastructure? is the component highly relied-upon?) --
never resolver confidence copied through unchanged. See each function's
comment for its exact formula.
"""
import dataclasses

from analysis.reconstruction.models import ArchitectureModel, ComponentRelationship
from analysis.smells.context import compute_finding_id, is_supporting_component
from analysis.smells.models import AffectedSymbol, EvidenceRelationship, Smell

# Expected layer order in a typical API -> Service -> Data-access/External
# architecture (CLAUDE.md §15/§19). "model" and "other" are deliberately
# unordered -- they can reasonably be depended on by anything.
_LAYER_ORDER = {"api": 0, "service": 1, "data_access": 2, "external_integration": 2}

_COUPLING_HIGH = 10
_COUPLING_MEDIUM = 6

_ROLE_HEURISTIC_CAVEAT = (
    "Component roles are inferred heuristically from directory structure and naming "
    "conventions, so verify this against the source before treating it as confirmed."
)

# HEURISTIC_LAYERING always applies to layer-order-based findings: the roles
# a boundary/layer_skip finding depends on are themselves inferred, so a
# ceiling below "very high confidence" is always appropriate even with no
# other discount.
_LAYERING_CONFIDENCE_CEILING = 0.85
_SUPPORTING_DISCOUNT = 0.25
_TEST_PARTICIPANT_DISCOUNT = 0.35

_BOUNDARY_BASE_CONFIDENCE = 0.7
_LAYER_SKIP_BASE_CONFIDENCE = 0.65
# Equal weight: the heuristic-layering base and the resolver's own
# confidence in the underlying CALLS edges each count for half. This is a
# blend, never a passthrough of resolver confidence -- see module docstring.
_RESOLVER_BLEND_WEIGHT = 0.5


def _layering_confidence(base: float, rel_confidence: float, discount: float) -> float:
    blended = (1 - _RESOLVER_BLEND_WEIGHT) * base + _RESOLVER_BLEND_WEIGHT * rel_confidence
    return max(0.15, min(_LAYERING_CONFIDENCE_CEILING, blended) - discount)


@dataclasses.dataclass(frozen=True)
class ViolationRecord:
    """A violation Smell plus the raw component ids behind it, for consumers
    (Architecture Optimization) that need to act on the actual components
    rather than re-parse the human-readable Smell text."""

    smell: Smell
    kind: str  # "boundary" | "layer_skip" | "cycle" | "coupling"
    component_ids: tuple[str, ...]  # (source,) for coupling; (source, target) otherwise


def _relationship_evidence(
    *relationships: ComponentRelationship, model: ArchitectureModel
) -> tuple[list[AffectedSymbol], list[EvidenceRelationship]]:
    """Real per-call-site evidence already embedded in each
    ComponentRelationship.evidence ("e.g. {file}:{line}" lines, produced by
    the reconstruction engine) -- never fabricated. Returns both the
    human-readable AffectedSymbol list (existing shape) and the structured
    EvidenceRelationship list (V2 addition), from the same parse pass."""
    names = {c.id: c for c in model.components}
    affected: list[AffectedSymbol] = []
    details: list[EvidenceRelationship] = []
    for rel in relationships:
        src = names.get(rel.source_id)
        dst = names.get(rel.target_id)
        src_name = src.name if src else rel.source_id
        dst_name = dst.name if dst else rel.target_id
        label = f"{src_name} -> {dst_name}"
        for line in rel.evidence:
            if not line.startswith("e.g. "):
                continue
            location = line[len("e.g. ") :]
            file_path, _, line_no = location.rpartition(":")
            if not file_path:
                continue
            start = int(line_no) if line_no.isdigit() else 0
            affected.append(AffectedSymbol(qualified_name=label, file_path=file_path, start_line=start, end_line=start))
            details.append(
                EvidenceRelationship(
                    source=src_name, target=dst_name, relationship_type="CALLS",
                    source_file=file_path, source_line=start, resolver_confidence=rel.confidence,
                    source_role=src.role if src else None, target_role=dst.role if dst else None,
                )
            )
    return affected, details


def _context_discount(*components) -> tuple[float, list[str]]:
    """Shared supporting-structure discount: if any participant is
    supporting infrastructure (tests, docs, tooling -- see
    analysis.smells.context.is_supporting_component), a boundary/layer_skip
    finding involving it is discounted and flagged. Test participation gets
    its own, larger, EXPECTED_TEST_DEPENDENCY flag in the two detectors
    where that specific case matters (circular/coupling)."""
    for c in components:
        if c is not None and is_supporting_component(c):
            return _SUPPORTING_DISCOUNT, ["SUPPORTING_STRUCTURE"]
    return 0.0, []


def layer_violation_records(model: ArchitectureModel) -> list[ViolationRecord]:
    components_by_id = {c.id: c for c in model.components}
    has_service = any(c.role == "service" for c in model.components)

    records: list[ViolationRecord] = []
    for rel in model.relationships:
        src, dst = components_by_id.get(rel.source_id), components_by_id.get(rel.target_id)
        if src is None or dst is None:
            continue
        src_order, dst_order = _LAYER_ORDER.get(src.role), _LAYER_ORDER.get(dst.role)
        if src_order is None or dst_order is None:
            continue
        diff = dst_order - src_order

        if diff < 0:
            severity = "HIGH" if diff <= -2 else "MEDIUM"
            affected, details = _relationship_evidence(rel, model=model)
            # Confidence: blend the relationship's own resolver confidence
            # (are we even sure these CALLS edges are correctly resolved?)
            # with the layering-heuristic ceiling, then apply the
            # supporting-structure discount if either side is test/tooling.
            discount, flags = _context_discount(src, dst)
            confidence = _layering_confidence(_BOUNDARY_BASE_CONFIDENCE, rel.confidence, discount)
            smell = Smell(
                id=compute_finding_id(model.repo_id, "architecture_boundary_violation", src.id, dst.id),
                smell_type="architecture_boundary_violation", severity=severity, confidence=confidence,
                title=f"{src.name} ({src.role}) depends on {dst.name} ({dst.role})",
                explanation=(
                    f"OBSERVED: {rel.call_count} resolved call(s) from '{src.name}' to '{dst.name}'. "
                    f"INTERPRETATION: in a layered architecture, a {src.role} component is not "
                    f"expected to call back into a {dst.role} component -- dependencies should flow "
                    f"the other way. {_ROLE_HEURISTIC_CAVEAT}"
                ),
                evidence=(
                    f"{rel.call_count} resolved call(s) from '{src.name}' to '{dst.name}' "
                    f"(avg resolver confidence {rel.confidence:.2f})."
                ),
                affected=affected,
                context_flags=["HEURISTIC_LAYERING", *flags],
                evidence_details=details,
                optimization_supported=True,
            )
            records.append(ViolationRecord(smell=smell, kind="boundary", component_ids=(src.id, dst.id)))
        elif diff > 1 and has_service:
            affected, details = _relationship_evidence(rel, model=model)
            discount, flags = _context_discount(src, dst)
            confidence = _layering_confidence(_LAYER_SKIP_BASE_CONFIDENCE, rel.confidence, discount)
            smell = Smell(
                id=compute_finding_id(model.repo_id, "layer_skip", src.id, dst.id),
                smell_type="layer_skip", severity="MEDIUM", confidence=confidence,
                title=f"{src.name} (api) calls {dst.name} ({dst.role}) directly",
                explanation=(
                    f"OBSERVED: {rel.call_count} resolved call(s) from '{src.name}' to '{dst.name}', "
                    "bypassing a service-role component that exists elsewhere in this repository. "
                    f"INTERPRETATION: this API-layer component may be skipping the service layer "
                    f"instead of routing through it. {_ROLE_HEURISTIC_CAVEAT}"
                ),
                evidence=(
                    f"{rel.call_count} resolved call(s) from '{src.name}' to '{dst.name}' "
                    f"(avg resolver confidence {rel.confidence:.2f}); a service-role component exists "
                    "elsewhere in the reconstructed architecture."
                ),
                affected=affected,
                context_flags=["HEURISTIC_LAYERING", *flags],
                evidence_details=details,
                optimization_supported=True,
            )
            records.append(ViolationRecord(smell=smell, kind="layer_skip", component_ids=(src.id, dst.id)))
    return records


def circular_component_dependency_records(model: ArchitectureModel) -> list[ViolationRecord]:
    components_by_id = {c.id: c for c in model.components}
    rel_index = {(r.source_id, r.target_id): r for r in model.relationships}

    records: list[ViolationRecord] = []
    seen_pairs: set[tuple[str, str]] = set()
    for (src_id, dst_id), rel in rel_index.items():
        pair = tuple(sorted((src_id, dst_id)))
        if pair in seen_pairs:
            continue
        reverse = rel_index.get((dst_id, src_id))
        if reverse is None:
            continue
        seen_pairs.add(pair)

        src, dst = components_by_id.get(src_id), components_by_id.get(dst_id)
        if src is None or dst is None:
            continue

        # Confidence (PART 11): a bidirectional call relationship between
        # two components is real structural coupling -- but when one side
        # is test infrastructure, tests calling the code they exercise
        # (and that code being reachable from test utilities/fixtures) is
        # the expected, desired shape of a test suite, not an architecture
        # problem. This is never silently excluded -- it stays a finding,
        # with a large confidence discount and an explicit context flag, so
        # the evidence (the relationship itself) is preserved either way.
        base_confidence = 0.7
        context_flags: list[str] = []
        if is_supporting_component(src) or is_supporting_component(dst):
            base_confidence -= _TEST_PARTICIPANT_DISCOUNT
            context_flags.append("EXPECTED_TEST_DEPENDENCY" if src.role == "test" or dst.role == "test" else "SUPPORTING_STRUCTURE")
        confidence = max(0.1, base_confidence)

        affected, details = _relationship_evidence(rel, reverse, model=model)
        smell = Smell(
            id=compute_finding_id(model.repo_id, "circular_component_dependency", *pair),
            smell_type="circular_component_dependency", severity="MEDIUM", confidence=confidence,
            title=f"{src.name} and {dst.name} depend on each other",
            explanation=(
                f"OBSERVED: {rel.call_count} call(s) '{src.name}' -> '{dst.name}' and "
                f"{reverse.call_count} call(s) '{dst.name}' -> '{src.name}'. INTERPRETATION: these "
                "two architectural components call each other -- neither can be understood, "
                "tested, or reused independently of the other. This is the component-level "
                "counterpart of a circular call dependency."
                + (
                    " One participant is test infrastructure; bidirectional test/source "
                    "interaction is common and expected, so this is not read as a confirmed "
                    "architecture problem."
                    if "EXPECTED_TEST_DEPENDENCY" in context_flags
                    else ""
                )
            ),
            evidence=(
                f"{rel.call_count} call(s) '{src.name}' -> '{dst.name}' and "
                f"{reverse.call_count} call(s) '{dst.name}' -> '{src.name}'."
            ),
            affected=affected,
            context_flags=context_flags,
            evidence_details=details,
            optimization_supported=True,
        )
        records.append(ViolationRecord(smell=smell, kind="cycle", component_ids=(src.id, dst.id)))
    return records


def excessive_coupling_records(model: ArchitectureModel) -> list[ViolationRecord]:
    connections: dict[str, set[str]] = {}
    incoming: dict[str, set[str]] = {}
    for rel in model.relationships:
        connections.setdefault(rel.source_id, set()).add(rel.target_id)
        connections.setdefault(rel.target_id, set()).add(rel.source_id)
        incoming.setdefault(rel.target_id, set()).add(rel.source_id)

    components_by_id = {c.id: c for c in model.components}
    records: list[ViolationRecord] = []
    for comp_id, peers in connections.items():
        degree = len(peers)
        if degree < _COUPLING_MEDIUM:
            continue
        comp = components_by_id.get(comp_id)
        if comp is None:
            continue
        severity = "HIGH" if degree >= _COUPLING_HIGH else "MEDIUM"

        # Confidence (PART 12): raw degree doesn't distinguish "this
        # component does too much" from "this component is a widely-relied
        # -upon hub" (a framework core, an entry point, shared
        # infrastructure) -- both produce a high degree. A component whose
        # connections are mostly OTHERS depending on IT (high incoming
        # share) reads as a hub; one that mostly reaches out to others
        # reads as more likely doing too much itself. The observed degree
        # (and severity) is unchanged either way -- only confidence moves.
        base_confidence = 0.6
        context_flags: list[str] = []
        incoming_degree = len(incoming.get(comp_id, set()))
        incoming_ratio = incoming_degree / degree if degree else 0.0
        if comp.role in ("api", "external_integration") or incoming_ratio >= 0.6:
            base_confidence -= 0.2
            context_flags.append("FRAMEWORK_HUB")
        if is_supporting_component(comp):
            base_confidence -= _SUPPORTING_DISCOUNT
            context_flags.append("SUPPORTING_STRUCTURE")
        confidence = max(0.15, base_confidence)

        smell = Smell(
            id=compute_finding_id(model.repo_id, "excessive_component_coupling", comp.id),
            smell_type="excessive_component_coupling", severity=severity, confidence=confidence,
            title=f"{comp.name} is connected to {degree} other components",
            explanation=(
                f"OBSERVED: {comp.name} has resolved relationships with {degree} other components "
                f"({incoming_degree} of which depend on it). INTERPRETATION: a component connected "
                "to this many others is commonly read as a structural bottleneck -- changes to it "
                "are likely to ripple widely -- but high in-degree can equally mean this is a "
                "widely-relied-upon hub (a framework core, entry point, or shared infrastructure) "
                "rather than a component that itself does too much."
            ),
            evidence=(
                f"{degree} distinct connected component(s) "
                f"(thresholds: MEDIUM>={_COUPLING_MEDIUM}, HIGH>={_COUPLING_HIGH})."
            ),
            affected=[
                AffectedSymbol(
                    qualified_name=comp.name,
                    file_path=comp.files[0] if comp.files else comp.id,
                    start_line=1, end_line=1,
                )
            ],
            context_flags=context_flags,
            optimization_supported=True,
        )
        records.append(ViolationRecord(smell=smell, kind="coupling", component_ids=(comp.id,)))
    return records


def all_violation_records(model: ArchitectureModel) -> list[ViolationRecord]:
    return [
        *layer_violation_records(model),
        *circular_component_dependency_records(model),
        *excessive_coupling_records(model),
    ]


def detect_layer_violations(model: ArchitectureModel) -> list[Smell]:
    return [r.smell for r in layer_violation_records(model)]


def detect_circular_component_dependencies(model: ArchitectureModel) -> list[Smell]:
    return [r.smell for r in circular_component_dependency_records(model)]


def detect_excessive_coupling(model: ArchitectureModel) -> list[Smell]:
    return [r.smell for r in excessive_coupling_records(model)]


def detect_architecture_violations(model: ArchitectureModel) -> list[Smell]:
    return [r.smell for r in all_violation_records(model)]
