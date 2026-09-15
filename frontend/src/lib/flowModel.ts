import type { ArchitectureConfidenceLabel, ComponentRole, FlowHop, FlowLabel } from "@/api/types";
import { ROLE_LABELS } from "@/lib/labels";

/** Mirrors backend/analysis/reconstruction/grouping.py's confidence_label
 * thresholds, so a 0.82 hop and an 82%-confidence component read the same
 * way everywhere in the UI instead of inventing a second vocabulary. */
export function confidenceLabel(score: number): ArchitectureConfidenceLabel {
  if (score >= 0.75) return "Confirmed";
  if (score >= 0.4) return "Inferred";
  return "Uncertain";
}

export type AbstractionLevel = "overview" | "components" | "symbols";
export type FlowMode = "observed" | "proposed";
export type TraceNodeKind = "entry" | "call" | "derived" | "proposed";

/** A single presentable step in the trace — built from one or more merged
 * FlowHops, never from anything the backend didn't already resolve. */
export interface TraceNode {
  id: string;
  kind: TraceNodeKind;
  label: FlowLabel;
  name: string;
  qualifiedName: string;
  callerQualifiedName: string;
  filePath: string | null;
  /** Call-site evidence for the edge *into* this node (source_file/line on the hop). */
  sourceFile: string | null;
  sourceLine: number | null;
  relationshipType: string;
  /** Lowest confidence among any hops merged into this node. */
  confidence: number;
  terminalKind: "database" | "external_service" | null;
  componentId: string | null;
  componentRole: ComponentRole | null;
  componentName: string | null;
  note: string | null;
  /** How many symbol-level hops were merged into this single presented step. */
  collapsedCount: number;
  /** Sibling branches that existed at a merge point but were not followed (overview level only). */
  branchOmitted: number;
  children: TraceNode[];
}

function shortName(qualifiedName: string): string {
  const parts = qualifiedName.split(".");
  return parts[parts.length - 1] || qualifiedName;
}

function baseNode(hop: FlowHop, id: string, isEntry: boolean): TraceNode {
  return {
    id,
    kind: isEntry ? "entry" : hop.label === "PROPOSED" ? "proposed" : "call",
    label: hop.label,
    name: shortName(hop.callee_qualified_name),
    qualifiedName: hop.callee_qualified_name,
    callerQualifiedName: hop.caller_qualified_name,
    filePath: hop.callee_file_path,
    sourceFile: hop.source_file,
    sourceLine: hop.source_line,
    relationshipType: hop.relationship_type,
    confidence: hop.confidence,
    terminalKind: hop.terminal_kind,
    componentId: hop.component_id,
    componentRole: hop.component_role,
    componentName: hop.component_name,
    note: hop.note,
    collapsedCount: 1,
    branchOmitted: 0,
    children: [],
  };
}

/** Symbols level: one TraceNode per resolved hop, exactly as reconstructed. */
export function buildSymbolTree(root: FlowHop): TraceNode {
  function walk(hop: FlowHop, parentId: string, index: number, isEntry: boolean): TraceNode {
    const id = `${parentId}.${index}`;
    const node = baseNode(hop, id, isEntry);
    node.children = hop.children.map((c, i) => walk(c, id, i, false));
    return node;
  }
  return walk(root, "root", 0, true);
}

interface CollapseOptions {
  /** Hops that should merge into the same presented step. */
  keyOf: (hop: FlowHop) => string;
  /** Overview: follow only the highest-confidence child, disclosing the rest as `branchOmitted`.
   * Components: follow every branch, just collapsing same-key runs within each. */
  followPrimaryOnly: boolean;
  nameOf: (headHop: FlowHop, mergedTail: FlowHop) => string;
}

function collapse(root: FlowHop, opts: CollapseOptions): TraceNode {
  function walk(hop: FlowHop, parentId: string, index: number, isEntry: boolean): TraceNode {
    const id = `${parentId}.${index}`;
    const node = baseNode(hop, id, isEntry);
    const key = opts.keyOf(hop);

    let tail = hop;
    let confMin = hop.confidence;
    let omitted = 0;
    for (;;) {
      if (tail.children.length === 0) break;
      if (opts.followPrimaryOnly) {
        omitted += tail.children.length - 1;
      } else if (tail.children.length > 1) {
        // A real branch point (not just Overview's deliberate "follow the
        // primary child") — stop merging here so every sibling still gets
        // rendered below, instead of silently keeping only children[0].
        break;
      }
      const primary = tail.children[0];
      if (opts.keyOf(primary) !== key || primary.label !== hop.label) break;
      tail = primary;
      confMin = Math.min(confMin, tail.confidence);
      node.collapsedCount += 1;
    }

    node.confidence = confMin;
    node.branchOmitted = omitted;
    node.terminalKind = tail.terminal_kind;
    node.name = isEntry ? shortName(hop.callee_qualified_name) : opts.nameOf(hop, tail);
    node.kind = isEntry ? "entry" : hop.label === "PROPOSED" ? "proposed" : "derived";

    if (tail.children.length === 0) {
      node.children = [];
    } else if (opts.followPrimaryOnly) {
      node.children = [walk(tail.children[0], id, 0, false)];
    } else {
      node.children = tail.children.map((c, i) => walk(c, id, i, false));
    }
    return node;
  }
  return walk(root, "root", 0, true);
}

/** Components level: collapse consecutive hops that belong to the same
 * reconstructed Architecture component (same evidence Architecture Reconstruction
 * already established), preserving every branch. */
export function buildComponentTree(root: FlowHop): TraceNode {
  return collapse(root, {
    keyOf: (h) => h.component_id ?? `unclassified:${h.component_role ?? "none"}:${h.callee_qualified_name}`,
    followPrimaryOnly: false,
    nameOf: (hop, tail) =>
      hop.component_name ?? (hop.component_role ? ROLE_LABELS[hop.component_role] : shortName(tail.callee_qualified_name)),
  });
}

/** Overview level: collapse consecutive hops sharing the same architectural
 * *role* (API/Service/Data-access/External) and follow only the
 * highest-confidence branch at each step, to give a short lifecycle-shaped
 * summary. Omitted sibling branches are counted, never hidden silently. */
export function buildOverviewTree(root: FlowHop): TraceNode {
  return collapse(root, {
    keyOf: (h) => h.component_role ?? `terminal:${h.terminal_kind ?? "none"}`,
    followPrimaryOnly: true,
    nameOf: (hop, tail) => {
      if (tail.terminal_kind === "database") return "Database";
      if (tail.terminal_kind === "external_service") return "External service";
      if (hop.label === "PROPOSED") return hop.component_name ? `${hop.component_name} (proposed)` : "Proposed step";
      if (hop.component_role) return ROLE_LABELS[hop.component_role];
      return shortName(hop.callee_qualified_name);
    },
  });
}

export function buildTrace(root: FlowHop, level: AbstractionLevel): TraceNode {
  if (level === "symbols") return buildSymbolTree(root);
  if (level === "components") return buildComponentTree(root);
  return buildOverviewTree(root);
}

export interface NarrativeStep {
  nodeId: string;
  text: string;
  proposed: boolean;
}

/** Plain-language narrative generated straight from the currently displayed
 * TraceNode tree, so it can never say more than the diagram shows. */
export function buildNarrative(tree: TraceNode): NarrativeStep[] {
  const lines: NarrativeStep[] = [];

  function describe(node: TraceNode): string {
    const loc = node.filePath ? ` (${node.filePath}${node.sourceLine ? `:${node.sourceLine}` : ""})` : "";
    if (node.kind === "entry") return `The trace begins at ${node.name}${loc}.`;
    if (node.kind === "proposed") {
      return node.note ? `${node.name} — ${node.note}` : `${node.name} would be introduced here as a design recommendation.`;
    }
    const verb = node.kind === "derived" ? "moves into" : "calls";
    const span = node.collapsedCount > 1 ? ` (${node.collapsedCount} resolved calls)` : "";
    const branchNote = node.branchOmitted > 0 ? ` ${node.branchOmitted} other branch${node.branchOmitted === 1 ? "" : "es"} not shown here.` : "";
    let text = `${shortName(node.callerQualifiedName)} ${verb} ${node.name}${span}${loc}.${branchNote}`;
    if (node.terminalKind) {
      const dest = node.terminalKind === "database" ? "a database" : "an external service";
      text += ` This terminates the reconstructed trace at ${dest}.`;
    }
    return text;
  }

  function walk(node: TraceNode) {
    lines.push({ nodeId: node.id, text: describe(node), proposed: node.kind === "proposed" });
    node.children.forEach(walk);
  }
  walk(tree);
  return lines;
}

export interface ProposedChange {
  nodeId: string;
  summary: string;
  note: string | null;
}

/** "What changed" — derived only from synthetic PROPOSED_CALL splice points
 * the backend already produced; never invented independently here. */
export function collectProposedChanges(root: FlowHop): ProposedChange[] {
  const changes: ProposedChange[] = [];
  function walk(hop: FlowHop, id: string, index: number) {
    const nodeId = `${id}.${index}`;
    if (hop.relationship_type === "PROPOSED_CALL") {
      const bridged = hop.children[0];
      const target = bridged ? shortName(bridged.callee_qualified_name) : "its destination";
      changes.push({
        nodeId,
        summary: `${shortName(hop.caller_qualified_name)} would route through ${hop.component_name ?? shortName(hop.callee_qualified_name)} before reaching ${target}, instead of calling it directly.`,
        note: hop.note,
      });
    }
    hop.children.forEach((c, i) => walk(c, nodeId, i));
  }
  walk(root, "root", 0);
  return changes;
}

export function findNode(tree: TraceNode, id: string): TraceNode | null {
  if (tree.id === id) return tree;
  for (const child of tree.children) {
    const found = findNode(child, id);
    if (found) return found;
  }
  return null;
}

/** Ancestor ids (inclusive) and descendant ids (inclusive) of `id` — used to
 * highlight the up/downstream path through a selected node and fade the rest. */
export function pathAround(tree: TraceNode, id: string): Set<string> {
  const result = new Set<string>();

  function collectDescendants(node: TraceNode) {
    result.add(node.id);
    node.children.forEach(collectDescendants);
  }

  function findAncestors(node: TraceNode, trail: TraceNode[]): boolean {
    const nextTrail = [...trail, node];
    if (node.id === id) {
      nextTrail.forEach((n) => result.add(n.id));
      collectDescendants(node);
      return true;
    }
    return node.children.some((c) => findAncestors(c, nextTrail));
  }

  findAncestors(tree, []);
  return result;
}

export function countNodes(tree: TraceNode): number {
  return 1 + tree.children.reduce((sum, c) => sum + countNodes(c), 0);
}

/** Nodes deep enough in a large tree to start collapsed by default, so the
 * initial view stays readable (CLAUDE.md-adjacent spec §40 "bounded rendering"). */
export function defaultCollapsedIds(tree: TraceNode, depthThreshold: number): Set<string> {
  const ids = new Set<string>();
  function walk(node: TraceNode, depth: number) {
    if (depth >= depthThreshold && node.children.length > 0) {
      ids.add(node.id);
      return;
    }
    node.children.forEach((c) => walk(c, depth + 1));
  }
  walk(tree, 0);
  return ids;
}
