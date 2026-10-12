/** Pure, unit-testable derivations for Evidence Explorer's node inspector and
 * relationship investigation panel — every function here reads only fields
 * the backend already returns (ArchitectureComponent, Smell, GraphEdge,
 * RelationshipResponse); nothing is invented or LLM-derived. Mirrors the
 * "derive, don't duplicate the source of truth" approach architectureModel.ts
 * already established for Architecture. */
import type { ArchitectureComponent, GraphEdge, RelationshipResponse, RelationshipStep, Smell } from "@/api/types";

/** The architecture component that contains this file, if any — same
 * file->component membership the backend's own grouping produced, just
 * looked up client-side (identical technique SmellsPanel/Overview use). */
export function componentForFile(components: ArchitectureComponent[], filePath: string): ArchitectureComponent | null {
  return components.find((c) => c.files.includes(filePath)) ?? null;
}

/** Findings whose evidence touches this file — a finding is "related" to an
 * entity when the entity's own file appears in the finding's affected list. */
export function findingsForFile(smells: Smell[], filePath: string): Smell[] {
  return smells.filter((s) => s.affected.some((a) => a.file_path === filePath));
}

export interface StructuralSummary {
  total: number;
  incoming: number;
  outgoing: number;
}

/** Incoming/outgoing/total edge counts for a node from the currently loaded
 * graph view — this is view-scoped (files or files+classes, whichever is on
 * screen), not a repository-wide degree; `degree` on GraphNode already gives
 * the repo-wide total, so this only recomputes the in/out split the API
 * doesn't break out itself. */
export function structuralSummary(edges: GraphEdge[], uid: string): StructuralSummary {
  let incoming = 0;
  let outgoing = 0;
  for (const e of edges) {
    if (e.source_uid === uid) outgoing++;
    if (e.target_uid === uid) incoming++;
  }
  return { total: incoming + outgoing, incoming, outgoing };
}

/** The ordered chain of distinct entities an INDIRECT path passes through —
 * source, then each hop's destination in turn. Only meaningful when the
 * steps form a genuine sequential chain (relationship_kind === "INDIRECT");
 * DIRECT's parallel edges must never be fed through this. */
export function pathChain(relationship: RelationshipResponse): string[] {
  return [relationship.source.qualified_name, ...relationship.steps.map((s) => s.to_qualified_name)];
}

/** CLAUDE.md §12/PART 12: never a plain average — the documented rule is
 * "bounded by the least-confident hop." Returns null when no step carries a
 * confidence value, rather than fabricating one. Only meaningful for a
 * multi-step chain; callers should skip labeling this for a single-step
 * relationship, where the one step's own confidence already is the answer. */
export function weakestLinkConfidence(steps: RelationshipStep[]): number | null {
  const known = steps.map((s) => s.confidence).filter((c): c is number => c !== null);
  if (known.length === 0) return null;
  return Math.min(...known);
}

export interface EvidenceLedger {
  relationshipCount: number;
  hopCount: number | null;
  sourceLocationCount: number;
  confidenceAssessmentCount: number;
  /** Share of steps that carry a concrete file:line citation — a real,
   * computed percentage, never an invented "confidence" number. */
  observedEvidencePct: number | null;
}

export function evidenceLedger(relationship: RelationshipResponse): EvidenceLedger {
  const { steps } = relationship;
  const sourceLocationCount = steps.filter((s) => s.source_file !== null).length;
  const confidenceAssessmentCount = steps.filter((s) => s.confidence !== null).length;
  return {
    relationshipCount: steps.length,
    hopCount: relationship.hop_count,
    sourceLocationCount,
    confidenceAssessmentCount,
    observedEvidencePct: steps.length > 0 ? Math.round((sourceLocationCount / steps.length) * 100) : null,
  };
}
