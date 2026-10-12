/** Understand and Components are NOT the Symbols tree rendered smaller — they
 * are genuinely different aggregations of the same evidence, built here.
 *
 * Understand: a flat, linear sequence of semantic *stages* along the
 * highest-confidence path (the backend already sorts each hop's children by
 * confidence, so children[0] at every level IS that path). Branches not
 * followed are disclosed as counts, never rendered as a second pipeline —
 * that branching detail belongs to Components/Symbols.
 *
 * Components: a deduplicated, ordered list of the distinct Architecture
 * components that participate anywhere in the trace (every branch, not just
 * the primary path) — the same component reached from two different call
 * paths is one entry, not two, with the calls it makes into other
 * components disclosed as "leads to".
 *
 * Both return DERIVED TraceNode entries (status="DERIVED"): every field is
 * computed from real FlowHop data, but the *grouping itself* is this
 * module's interpretation, never a literal backend fact — never mixed up
 * with the entry step itself, which stays OBSERVED.
 */
import type { ComponentRole, FlowHop } from "@/api/types";
import { isTerminalReason, type TerminalReason } from "@/lib/terminalReasons";
import { ROLE_LABELS } from "@/lib/labels";
import { shortName, topDir, type TraceNode } from "@/lib/flowModel";

type StageCategory = "ENTRY" | "FRAMEWORK" | "APPLICATION" | "DATA_ACCESS" | "EXTERNAL";

const STAGE_LABEL: Record<StageCategory, string> = {
  ENTRY: "Entry Point",
  FRAMEWORK: "Framework Handling",
  APPLICATION: "Application Logic",
  DATA_ACCESS: "Data Access",
  EXTERNAL: "External Integration",
};

function stageCategory(hop: FlowHop, entryTop: string | null, isEntry: boolean): StageCategory {
  if (isEntry) return "ENTRY";
  const hopTop = topDir(hop.callee_file_path);
  if (hopTop !== null && entryTop !== null && hopTop !== entryTop) return "FRAMEWORK";
  if (hop.component_role === "data_access") return "DATA_ACCESS";
  if (hop.component_role === "external_integration") return "EXTERNAL";
  return "APPLICATION";
}

interface PathStep {
  hop: FlowHop;
  id: string;
}

function countHopDescendants(hop: FlowHop): number {
  return 1 + hop.children.reduce((sum, c) => sum + countHopDescendants(c), 0);
}

/** engine.py already sorts each hop's children by confidence, so the
 * highest-confidence child is the "most likely" one to follow — but real
 * traces routinely tie (e.g. two calls both resolved at 0.75 confidence),
 * and among tied candidates always taking array position 0 is arbitrary,
 * not evidence-driven. Break ties toward whichever branch static analysis
 * could resolve *further* into — still principled (more reconstructed
 * evidence, not invented), and the untaken sibling is still disclosed via
 * branchOmitted either way. */
function pickPrimary(children: FlowHop[]): { hop: FlowHop; index: number } {
  const maxConfidence = Math.max(...children.map((c) => c.confidence));
  let bestIndex = children.findIndex((c) => c.confidence === maxConfidence);
  let bestSize = countHopDescendants(children[bestIndex]);
  for (let i = bestIndex + 1; i < children.length; i++) {
    if (children[i].confidence !== maxConfidence) continue;
    const size = countHopDescendants(children[i]);
    if (size > bestSize) {
      bestIndex = i;
      bestSize = size;
    }
  }
  return { hop: children[bestIndex], index: bestIndex };
}

function primaryPath(root: FlowHop): PathStep[] {
  const path: PathStep[] = [];
  let hop: FlowHop = root;
  let id = "root.0";
  for (;;) {
    path.push({ hop, id });
    if (hop.children.length === 0) break;
    const primary = pickPrimary(hop.children);
    id = `${id}.${primary.index}`;
    hop = primary.hop;
  }
  return path;
}

function stageNode(id: string, category: StageCategory, isEntry: boolean, run: PathStep[]): TraceNode {
  const head = run[0].hop;
  const tail = run[run.length - 1].hop;
  const memberIds = run.map((s) => s.id);
  const confidence = Math.min(...run.map((s) => s.hop.confidence));
  const branchOmitted = run.reduce((sum, s) => sum + Math.max(0, s.hop.children.length - 1), 0);
  const ranOutOfPath = tail.children.length === 0;
  const terminalReason = ranOutOfPath && isTerminalReason(tail.terminal_reason) ? tail.terminal_reason : null;

  const subtitle =
    run.length === 1
      ? `${shortName(head.callee_qualified_name)}()`
      : `${shortName(head.callee_qualified_name)}() → ${shortName(tail.callee_qualified_name)}() · ${run.length} steps`;

  return {
    id,
    kind: isEntry ? "entry" : "stage",
    status: isEntry ? "OBSERVED" : "DERIVED",
    label: tail.label,
    name: isEntry ? shortName(head.callee_qualified_name) : STAGE_LABEL[category],
    subtitle: isEntry ? null : subtitle,
    qualifiedName: tail.callee_qualified_name,
    callerQualifiedName: head.caller_qualified_name,
    filePath: tail.callee_file_path,
    memberIds,
    sourceFile: tail.source_file,
    sourceLine: tail.source_line,
    relationshipType: tail.relationship_type,
    confidence,
    terminalKind: tail.terminal_kind,
    terminalReason,
    childrenOmitted: tail.children_omitted,
    componentId: tail.component_id,
    componentRole: tail.component_role,
    componentName: tail.component_name,
    note: null,
    collapsedCount: run.length,
    branchOmitted,
    scope: "application",
    children: [],
  };
}

export function buildUnderstandStages(root: FlowHop): TraceNode[] {
  const entryTop = topDir(root.callee_file_path);
  const path = primaryPath(root);
  const stages: TraceNode[] = [];

  let i = 0;
  while (i < path.length) {
    const isEntry = i === 0;
    const category = stageCategory(path[i].hop, entryTop, isEntry);
    let j = i + 1;
    while (j < path.length && stageCategory(path[j].hop, entryTop, false) === category) j++;
    stages.push(stageNode(path[i].id, category, isEntry, path.slice(i, j)));
    i = j;
  }
  return stages;
}

interface ComponentAccumulator {
  key: string;
  componentId: string | null;
  role: ComponentRole | null;
  name: string;
  memberIds: string[];
  hops: FlowHop[];
  order: number;
  transitionsTo: Set<string>;
}

function componentKey(hop: FlowHop): string {
  return hop.component_id ?? `unclassified:${hop.component_role ?? "none"}`;
}

/** Walks every branch (not just the primary path) and groups hops by the
 * Architecture component they belong to, deduplicating a component that's
 * reached more than once into a single participation entry. */
export function buildComponentParticipation(root: FlowHop): TraceNode[] {
  const byKey = new Map<string, ComponentAccumulator>();
  const nameByKey = new Map<string, string>();
  let order = 0;

  function visit(hop: FlowHop, id: string, parentKey: string | null) {
    const key = componentKey(hop);
    let acc = byKey.get(key);
    if (!acc) {
      acc = {
        key,
        componentId: hop.component_id,
        role: hop.component_role,
        name: hop.component_name ?? (hop.component_role ? ROLE_LABELS[hop.component_role] : "Unclassified"),
        memberIds: [],
        hops: [],
        order: order++,
        transitionsTo: new Set(),
      };
      byKey.set(key, acc);
      nameByKey.set(key, acc.name);
    }
    acc.memberIds.push(id);
    acc.hops.push(hop);
    if (parentKey && parentKey !== key) byKey.get(parentKey)?.transitionsTo.add(key);
    hop.children.forEach((c, i) => visit(c, `${id}.${i}`, key));
  }
  visit(root, "root.0", null);

  return [...byKey.values()]
    .sort((a, b) => a.order - b.order)
    .map((acc): TraceNode => {
      const terminalHops = acc.hops.filter((h) => h.children.length === 0 && h.terminal_reason);
      const reasonCounts = new Map<TerminalReason, number>();
      for (const h of terminalHops) {
        if (isTerminalReason(h.terminal_reason)) reasonCounts.set(h.terminal_reason, (reasonCounts.get(h.terminal_reason) ?? 0) + 1);
      }
      const representativeReason = terminalHops.length > 0 && isTerminalReason(terminalHops[0].terminal_reason) ? terminalHops[0].terminal_reason : null;
      const breakdown = [...reasonCounts.entries()].map(([reason, count]) => `${count}× ${reason.replace(/_/g, " ").toLowerCase()}`).join(", ");
      const leadsTo = [...acc.transitionsTo].map((k) => nameByKey.get(k) ?? k);

      return {
        id: acc.memberIds[0],
        kind: acc.order === 0 ? "entry" : "component",
        status: acc.order === 0 ? "OBSERVED" : "DERIVED",
        label: "OBSERVED",
        name: acc.name,
        subtitle:
          acc.memberIds.length === 1
            ? `${shortName(acc.hops[0].callee_qualified_name)}()`
            : `${acc.memberIds.length} participating step${acc.memberIds.length === 1 ? "" : "s"}${leadsTo.length > 0 ? ` · leads to ${leadsTo.join(", ")}` : ""}`,
        qualifiedName: acc.hops[0].callee_qualified_name,
        callerQualifiedName: acc.hops[0].caller_qualified_name,
        filePath: acc.hops[0].callee_file_path,
        memberIds: acc.memberIds,
        sourceFile: acc.hops[0].source_file,
        sourceLine: acc.hops[0].source_line,
        relationshipType: acc.hops[0].relationship_type,
        confidence: Math.min(...acc.hops.map((h) => h.confidence)),
        terminalKind: acc.hops.find((h) => h.terminal_kind)?.terminal_kind ?? null,
        terminalReason: representativeReason,
        childrenOmitted: acc.hops.reduce((sum, h) => sum + h.children_omitted, 0),
        componentId: acc.componentId,
        componentRole: acc.role,
        componentName: acc.name,
        note:
          terminalHops.length > 0
            ? `${terminalHops.length} of ${acc.memberIds.length} participating step${acc.memberIds.length === 1 ? "" : "s"} terminate here (${breakdown}).`
            : null,
        collapsedCount: acc.memberIds.length,
        branchOmitted: 0,
        scope: "application",
        children: [],
      };
    });
}
