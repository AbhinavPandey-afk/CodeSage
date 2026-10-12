import type { ArchitectureConfidenceLabel, ComponentRole, FlowHop, FlowLabel } from "@/api/types";
import { isTerminalReason, TERMINAL_REASON_EXPLANATION, type TerminalReason } from "@/lib/terminalReasons";

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
/** "continuation" is a synthetic placeholder for steps a Trace Scope filter
 * hid — never a real symbol, never selectable for evidence, just a display
 * boundary the user can expand. "stage" (Understand) and "component"
 * (Components) are aggregated, always-DERIVED groupings built in
 * lib/semanticFlow.ts — never presented as an observed repository fact on
 * their own. See pruneByScope(). */
export type TraceNodeKind = "entry" | "call" | "proposed" | "continuation" | "stage" | "component";

/** OBSERVED: directly a resolved repository symbol/relationship.
 * DERIVED: a semantic grouping built from OBSERVED evidence (a stage or
 * component participation) — never itself a repository fact.
 * PROPOSED: a design projection from Architecture Optimization. */
export type EvidenceStatus = "OBSERVED" | "DERIVED" | "PROPOSED";

/** A single presentable step in the trace — built from one or more merged
 * FlowHops, never from anything the backend didn't already resolve. */
export interface TraceNode {
  id: string;
  kind: TraceNodeKind;
  status: EvidenceStatus;
  label: FlowLabel;
  name: string;
  /** Secondary line under the name — e.g. a stage's representative symbol,
   * or a component's role + participation count. Null when the name alone
   * already says everything (Symbols level). */
  subtitle: string | null;
  qualifiedName: string;
  callerQualifiedName: string;
  filePath: string | null;
  /** Symbols-level TraceNode ids (same id scheme as buildSymbolTree) this
   * stage/component aggregates — how "Expand evidence" finds its way to
   * the underlying symbol trace. Empty for plain Symbols-level nodes. */
  memberIds: string[];
  /** Call-site evidence for the edge *into* this node (source_file/line on the hop). */
  sourceFile: string | null;
  sourceLine: number | null;
  relationshipType: string;
  /** Lowest confidence among any hops merged into this node. */
  confidence: number;
  /** The callee's Architecture *role* (database/external_service) — purely
   * descriptive. Never implies traversal stopped; use `terminalReason` for that. */
  terminalKind: "database" | "external_service" | null;
  /** Why traversal actually stopped here — null whenever `children` is non-empty. */
  terminalReason: TerminalReason | null;
  /** Additional resolved calls this symbol has beyond the branch cap, disclosed not dropped. */
  childrenOmitted: number;
  componentId: string | null;
  componentRole: ComponentRole | null;
  componentName: string | null;
  note: string | null;
  /** How many symbol-level hops were merged into this single presented step. */
  collapsedCount: number;
  /** Sibling branches that existed at a merge point but were not followed (overview level only). */
  branchOmitted: number;
  /** "application" = same top-level directory as the entry point; "framework"
   * = a different one (often vendored/dependency code). Set by tagScope(). */
  scope: TraceScope;
  children: TraceNode[];
}

export type TraceScope = "application" | "framework";

export function shortName(qualifiedName: string): string {
  const parts = qualifiedName.split(".");
  return parts[parts.length - 1] || qualifiedName;
}

function baseNode(hop: FlowHop, id: string, isEntry: boolean): TraceNode {
  return {
    id,
    kind: isEntry ? "entry" : hop.label === "PROPOSED" ? "proposed" : "call",
    status: isEntry ? "OBSERVED" : hop.label === "PROPOSED" ? "PROPOSED" : "OBSERVED",
    label: hop.label,
    name: shortName(hop.callee_qualified_name),
    subtitle: null,
    qualifiedName: hop.callee_qualified_name,
    callerQualifiedName: hop.caller_qualified_name,
    filePath: hop.callee_file_path,
    memberIds: [],
    sourceFile: hop.source_file,
    sourceLine: hop.source_line,
    relationshipType: hop.relationship_type,
    confidence: hop.confidence,
    terminalKind: hop.terminal_kind,
    terminalReason: isTerminalReason(hop.terminal_reason) ? hop.terminal_reason : null,
    childrenOmitted: hop.children_omitted,
    componentId: hop.component_id,
    componentRole: hop.component_role,
    componentName: hop.component_name,
    note: hop.note,
    collapsedCount: 1,
    branchOmitted: 0,
    scope: "application",
    children: [],
  };
}

export function topDir(filePath: string | null): string | null {
  if (!filePath) return null;
  const idx = filePath.indexOf("/");
  return idx === -1 ? filePath : filePath.slice(0, idx);
}

/** Tags every node as "application" (same top-level directory as the entry
 * point) or "framework" (a different one) purely from the real
 * callee_file_path already on each hop — nothing invented, just a grouping
 * of evidence already present. Mutates and returns the same tree. */
export function tagScope(tree: TraceNode): TraceNode {
  const entryTop = topDir(tree.filePath);
  function walk(node: TraceNode) {
    node.scope = !node.filePath || entryTop === null || topDir(node.filePath) === entryTop ? "application" : "framework";
    node.children.forEach(walk);
  }
  walk(tree);
  return tree;
}

/** Whether this trace actually crosses a directory boundary at all — the
 * Trace Scope control should only appear when there's a real distinction to
 * filter, not for every repository. */
export function hasFrameworkBoundary(tree: TraceNode): boolean {
  if (tree.scope === "framework") return true;
  return tree.children.some(hasFrameworkBoundary);
}

function continuationNode(id: string, hiddenCount: number, hiddenScope: TraceScope): TraceNode {
  return {
    id: `${id}.continuation`,
    kind: "continuation",
    status: "OBSERVED",
    label: "OBSERVED",
    name: hiddenScope === "framework" ? "Framework continuation" : "Application continuation",
    subtitle: null,
    qualifiedName: "",
    callerQualifiedName: "",
    filePath: null,
    memberIds: [],
    sourceFile: null,
    sourceLine: null,
    relationshipType: "",
    confidence: 1,
    terminalKind: null,
    terminalReason: null,
    childrenOmitted: 0,
    componentId: null,
    componentRole: null,
    componentName: null,
    note: `${hiddenCount} step${hiddenCount === 1 ? "" : "s"} hidden by the ${hiddenScope === "framework" ? "Application" : "Framework"} scope filter.`,
    collapsedCount: 1,
    branchOmitted: 0,
    scope: hiddenScope,
    children: [],
  };
}

/** Filters the tree to one scope, keeping any node that's on the path to a
 * kept descendant (so a filtered-out node isn't deleted if it's the only
 * thing connecting the entry to something the requested scope does want to
 * show). Hidden steps are never just dropped — a synthetic "continuation"
 * node takes their place, showing this is a *display* boundary the user can
 * expand back to Repository scope, not a claim that execution stopped. */
export function pruneByScope(tree: TraceNode, want: TraceScope): TraceNode {
  const hiddenScope: TraceScope = want === "application" ? "framework" : "application";

  function walk(node: TraceNode): TraceNode | null {
    const keptChildren: TraceNode[] = [];
    let hidden = 0;
    for (const child of node.children) {
      const kept = walk(child);
      if (kept) keptChildren.push(kept);
      else hidden += countNodes(child);
    }
    const selfMatches = node.scope === want || node.kind === "entry";
    if (!selfMatches && keptChildren.length === 0) return null;
    if (hidden > 0) keptChildren.push(continuationNode(node.id, hidden, hiddenScope));
    return { ...node, children: keptChildren };
  }
  return walk(tree) ?? { ...tree, children: [] };
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

export interface NarrativeStep {
  nodeId: string;
  text: string;
  proposed: boolean;
}

/** One sentence describing a single TraceNode, grounded entirely in its own
 * fields — shared by the tree-walking (Symbols) and flat-list (Understand /
 * Components) narrative builders below, so the wording logic lives in
 * exactly one place. */
export function describeTraceNode(node: TraceNode): string {
  const loc = node.filePath ? ` (${node.filePath}${node.sourceLine ? `:${node.sourceLine}` : ""})` : "";
  if (node.kind === "entry") return `The trace begins at ${node.name}${loc}.`;
  if (node.kind === "continuation") return "";
  if (node.kind === "proposed") {
    return node.note ? `${node.name} — ${node.note}` : `${node.name} would be introduced here as a design recommendation.`;
  }
  if (node.kind === "stage" || node.kind === "component") {
    const span = node.memberIds.length > 1 ? ` (${node.memberIds.length} resolved steps)` : "";
    let text = `Execution moves into ${node.name}${span}${node.subtitle ? ` — ${node.subtitle}` : ""}.`;
    if (node.terminalReason) text += ` ${TERMINAL_REASON_EXPLANATION[node.terminalReason]}`;
    return text;
  }
  const span = node.collapsedCount > 1 ? ` (${node.collapsedCount} resolved calls)` : "";
  const branchNote = node.branchOmitted > 0 ? ` ${node.branchOmitted} other branch${node.branchOmitted === 1 ? "" : "es"} not shown here.` : "";
  let text = `${shortName(node.callerQualifiedName)} calls ${node.name}${span}${loc}.${branchNote}`;
  if (node.terminalReason) {
    text += ` ${TERMINAL_REASON_EXPLANATION[node.terminalReason]}`;
  }
  if (node.childrenOmitted > 0) {
    text += ` ${node.childrenOmitted} further resolved call${node.childrenOmitted === 1 ? "" : "s"} from here were omitted to keep the trace readable.`;
  }
  return text;
}

/** Plain-language narrative generated straight from the currently displayed
 * Symbols-level TraceNode tree, so it can never say more than the diagram shows. */
export function buildNarrative(tree: TraceNode): NarrativeStep[] {
  const lines: NarrativeStep[] = [];
  function walk(node: TraceNode) {
    if (node.kind !== "continuation") {
      lines.push({ nodeId: node.id, text: describeTraceNode(node), proposed: node.kind === "proposed" });
    }
    node.children.forEach(walk);
  }
  walk(tree);
  return lines;
}

/** Same, for the flat Understand/Components lists. */
export function buildFlatNarrative(nodes: TraceNode[]): NarrativeStep[] {
  return nodes.map((node) => ({ nodeId: node.id, text: describeTraceNode(node), proposed: node.kind === "proposed" }));
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

export function findInList(nodes: TraceNode[], id: string): TraceNode | null {
  return nodes.find((n) => n.id === id) ?? null;
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
