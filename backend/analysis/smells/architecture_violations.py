"""Architecture-level violation detection (CLAUDE.md §18/§6).

Reasons over the reconstructed ArchitectureModel's components and
relationships -- a different granularity from detector.py's per-symbol
checks (circular dependency, god class, ...). Findings share the same Smell
output shape so they surface in the same Architecture Analysis list per
CLAUDE.md's "Smell Detection + Architecture Violations merge into
Architecture Analysis" rule -- never a separate endpoint or tab.
"""
from dataclasses import dataclass

from analysis.reconstruction.models import ArchitectureModel, ComponentRelationship
from analysis.smells.models import AffectedSymbol, Smell

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


@dataclass(frozen=True)
class ViolationRecord:
    """A violation Smell plus the raw component ids behind it, for consumers
    (Architecture Optimization) that need to act on the actual components
    rather than re-parse the human-readable Smell text."""

    smell: Smell
    kind: str  # "boundary" | "layer_skip" | "cycle" | "coupling"
    component_ids: tuple[str, ...]  # (source,) for coupling; (source, target) otherwise


def _example_affected(*relationships: ComponentRelationship, model: ArchitectureModel) -> list[AffectedSymbol]:
    names = {c.id: c for c in model.components}
    affected: list[AffectedSymbol] = []
    for rel in relationships:
        src = names.get(rel.source_id)
        dst = names.get(rel.target_id)
        label = f"{src.name if src else rel.source_id} -> {dst.name if dst else rel.target_id}"
        for line in rel.evidence:
            if not line.startswith("e.g. "):
                continue
            location = line[len("e.g. ") :]
            file_path, _, line_no = location.rpartition(":")
            if not file_path:
                continue
            start = int(line_no) if line_no.isdigit() else 0
            affected.append(AffectedSymbol(qualified_name=label, file_path=file_path, start_line=start, end_line=start))
    return affected


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
            smell = Smell(
                smell_type="architecture_boundary_violation", severity=severity,
                title=f"{src.name} ({src.role}) depends on {dst.name} ({dst.role})",
                explanation=(
                    f"In a layered architecture, a {src.role} component is not expected to call "
                    f"back into a {dst.role} component -- dependencies should flow the other way. "
                    f"{_ROLE_HEURISTIC_CAVEAT}"
                ),
                evidence=(
                    f"{rel.call_count} resolved call(s) from '{src.name}' to '{dst.name}' "
                    f"(avg resolver confidence {rel.confidence:.2f})."
                ),
                affected=_example_affected(rel, model=model),
            )
            records.append(ViolationRecord(smell=smell, kind="boundary", component_ids=(src.id, dst.id)))
        elif diff > 1 and has_service:
            smell = Smell(
                smell_type="layer_skip", severity="MEDIUM",
                title=f"{src.name} (api) calls {dst.name} ({dst.role}) directly",
                explanation=(
                    "This API-layer component calls a data-access/external-integration component "
                    "directly, bypassing the service layer that exists elsewhere in this repository. "
                    f"{_ROLE_HEURISTIC_CAVEAT}"
                ),
                evidence=(
                    f"{rel.call_count} resolved call(s) from '{src.name}' to '{dst.name}' "
                    f"(avg resolver confidence {rel.confidence:.2f}); a service-role component exists "
                    "elsewhere in the reconstructed architecture."
                ),
                affected=_example_affected(rel, model=model),
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
        smell = Smell(
            smell_type="circular_component_dependency", severity="MEDIUM",
            title=f"{src.name} and {dst.name} depend on each other",
            explanation=(
                "These two architectural components call each other -- neither can be understood, "
                "tested, or reused independently of the other. This is the component-level "
                "counterpart of a circular call dependency."
            ),
            evidence=(
                f"{rel.call_count} call(s) '{src.name}' -> '{dst.name}' and "
                f"{reverse.call_count} call(s) '{dst.name}' -> '{src.name}'."
            ),
            affected=_example_affected(rel, reverse, model=model),
        )
        records.append(ViolationRecord(smell=smell, kind="cycle", component_ids=(src.id, dst.id)))
    return records


def excessive_coupling_records(model: ArchitectureModel) -> list[ViolationRecord]:
    connections: dict[str, set[str]] = {}
    for rel in model.relationships:
        connections.setdefault(rel.source_id, set()).add(rel.target_id)
        connections.setdefault(rel.target_id, set()).add(rel.source_id)

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
        smell = Smell(
            smell_type="excessive_component_coupling", severity=severity,
            title=f"{comp.name} is connected to {degree} other components",
            explanation=(
                "A component connected to this many other components is a structural bottleneck: "
                "changes to it are likely to ripple widely, and it is hard to reason about or "
                "replace in isolation."
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
