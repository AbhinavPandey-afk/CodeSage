/** Pure, unit-testable derivations for Architecture Analysis V2 — confidence
 * tiering, deterministic sort order, and the finding-type -> action-target
 * strategy. Nothing here calls an API or invents a fact; every function
 * reads only fields the backend's approved V2 finding model already
 * returns (see analysis/smells/models.py). */
import type { ArchitectureComponent, Severity, Smell, SmellType } from "@/api/types";

export type ConfidenceTier = "High" | "Medium" | "Low";

/** Deliberately distinct from ArchitectureConfidenceLabel's 0.75/0.4
 * Confirmed/Inferred/Uncertain (component/relationship confidence) — this
 * is a different concept (finding confidence) and uses its own thresholds
 * so the two are never visually interchangeable. */
export function confidenceTier(confidence: number): ConfidenceTier {
  if (confidence >= 0.7) return "High";
  if (confidence >= 0.4) return "Medium";
  return "Low";
}

const SEVERITY_ORDER: Record<Severity, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 };

/** Deterministic default order (PART 23): severity, then confidence
 * (higher first), then the stable finding id as a final tiebreak — never a
 * subjective "importance" score. The backend already returns findings
 * severity-sorted; this only adds the secondary/tertiary keys client-side,
 * without altering what the API considers canonical. */
export function sortFindings(smells: Smell[]): Smell[] {
  return [...smells].sort((a, b) => {
    const severityDiff = SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
    if (severityDiff !== 0) return severityDiff;
    const confidenceDiff = b.confidence - a.confidence;
    if (confidenceDiff !== 0) return confidenceDiff;
    return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
  });
}

/** The 4 symbol-level detectors produce a real, searchable symbol as
 * affected[0] (Evidence Explorer / Impact & Risk can act on it directly).
 * The 4 component-level (architecture-violation) detectors synthesize a
 * human-readable "A -> B" label as affected[0].qualified_name instead — not
 * a real graph node, so routing it into Evidence Explorer's symbol search
 * or Impact & Risk's symbol lookup would silently find nothing. This is the
 * one integration seam the V2 UI has to route around (never invented; the
 * component id / file path underneath is always real). */
const COMPONENT_LEVEL_TYPES = new Set<SmellType>([
  "architecture_boundary_violation",
  "layer_skip",
  "circular_component_dependency",
  "excessive_component_coupling",
]);

export function isComponentLevelFinding(smellType: SmellType): boolean {
  return COMPONENT_LEVEL_TYPES.has(smellType);
}

/** Same file -> component membership Architecture/Overview/Evidence
 * Explorer already use (component.files.includes(filePath)) — the one
 * reliable link from a finding's real evidence file back to a real,
 * resolvable component id. */
export function componentIdForFile(components: ArchitectureComponent[], filePath: string): string | null {
  return components.find((c) => c.files.includes(filePath))?.id ?? null;
}

export interface FindingActionTargets {
  /** Evidence Explorer focus — a real qualified_name for symbol-level
   * findings, or a real componentId for component-level findings (never
   * the synthesized "A -> B" label). Null if neither could be resolved. */
  evidenceQualifiedName: string | null;
  evidenceComponentId: string | null;
  /** Show on Architecture — real for both kinds, whenever the affected
   * file maps to a reconstructed component. */
  architectureComponentId: string | null;
  /** Impact & Risk — only offered for symbol-level findings, where
   * affected[0] is a real, impact-analyzable symbol; omitted (null) for
   * component-level findings rather than pointing at a synthetic label. */
  impactQualifiedName: string | null;
}

export interface ObservedInterpretation {
  observed: string;
  /** Null when the backend explanation didn't contain a parseable
   * INTERPRETATION section -- the caller must fall back to showing
   * `observed` as the whole explanation, never fabricate an
   * interpretation. */
  interpretation: string | null;
}

/** Every V2 detector's `explanation` is written as
 * "OBSERVED: ... INTERPRETATION: ..." (see analysis/smells/detector.py and
 * architecture_violations.py) specifically so this split is reliable --
 * this only parses that existing convention, it does not add any new fact. */
export function splitObservedInterpretation(explanation: string): ObservedInterpretation {
  const observedMarker = "OBSERVED:";
  const interpretationMarker = "INTERPRETATION:";
  const observedIdx = explanation.indexOf(observedMarker);
  const interpretationIdx = explanation.indexOf(interpretationMarker);
  if (observedIdx === -1 || interpretationIdx === -1 || interpretationIdx <= observedIdx) {
    return { observed: explanation.trim(), interpretation: null };
  }
  return {
    observed: explanation.slice(observedIdx + observedMarker.length, interpretationIdx).trim(),
    interpretation: explanation.slice(interpretationIdx + interpretationMarker.length).trim(),
  };
}

export function findingActionTargets(smell: Smell, components: ArchitectureComponent[]): FindingActionTargets {
  const primary = smell.affected[0];
  const filePath = primary?.file_path;
  const componentId = filePath ? componentIdForFile(components, filePath) : null;
  const componentLevel = isComponentLevelFinding(smell.smell_type);

  return {
    evidenceQualifiedName: componentLevel ? null : (primary?.qualified_name ?? null),
    evidenceComponentId: componentLevel ? componentId : null,
    architectureComponentId: componentId,
    impactQualifiedName: componentLevel ? null : (primary?.qualified_name ?? null),
  };
}
