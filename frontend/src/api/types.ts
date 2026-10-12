export type RepositoryStatus =
  | "pending"
  | "cloning"
  | "cloned"
  | "parsing"
  | "building_graph"
  | "embedding"
  | "ready"
  | "failed";

export interface Repository {
  id: string;
  url: string;
  owner: string;
  name: string;
  status: RepositoryStatus;
  default_branch: string | null;
  commit_sha: string | null;
  languages: Record<string, number>;
  file_count: number;
  symbol_count: number;
  relationship_count: number;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface RelatedSymbol {
  relationship_type: string;
  direction: "outgoing" | "incoming";
  qualified_name: string;
  file_path: string;
  start_line: number;
  confidence: number;
}

export interface EvidenceItem {
  symbol_type: string;
  name: string;
  qualified_name: string;
  file_path: string;
  start_line: number;
  end_line: number;
  relevance: number;
  related: RelatedSymbol[];
}

export interface AskResponse {
  answer: string;
  confidence_score: number;
  confidence_label: "Confirmed" | "Inferred" | "Uncertain";
  evidence: EvidenceItem[];
}

export interface AffectedSymbol {
  qualified_name: string;
  file_path: string;
  start_line: number;
  end_line: number;
}

export type SmellType =
  | "circular_dependency"
  | "god_class"
  | "large_function"
  | "dead_code_candidate"
  | "architecture_boundary_violation"
  | "layer_skip"
  | "circular_component_dependency"
  | "excessive_component_coupling";
export type Severity = "LOW" | "MEDIUM" | "HIGH";

/** Deterministic, evidence-derived interpretation tags (backend:
 * analysis/smells/context.py + each detector's own confidence rule) --
 * never a subjective/LLM judgment, and never used to suppress a finding.
 * Kept as a union for documentation; the field itself stays `string[]` so an
 * unrecognized future flag from the backend doesn't become a type error. */
export type ContextFlag =
  | "EXPECTED_TEST_DEPENDENCY"
  | "FRAMEWORK_HUB"
  | "SUPPORTING_STRUCTURE"
  | "DYNAMIC_DISPATCH_RISK"
  | "HEURISTIC_LAYERING"
  | "INTRA_CLASS_DELEGATION"
  | "METHOD_COUNT_HEURISTIC"
  | "LENGTH_BASED_HEURISTIC";

/** Structured counterpart of a Smell's `evidence` string -- lets a future UI
 * render real evidence without parsing prose. `resolver_confidence` is the
 * cross-file CALL/IMPORT resolver's confidence in this specific edge --
 * distinct from the finding's own `confidence` on Smell. */
export interface EvidenceRelationship {
  source: string;
  target: string;
  relationship_type: string;
  source_file: string | null;
  source_line: number | null;
  resolver_confidence: number | null;
  source_role: string | null;
  target_role: string | null;
}

export interface Smell {
  /** Stable, content-addressed identifier (backend:
   * analysis/smells/context.py's compute_finding_id) -- reproducible across
   * repeated requests for the same analyzed repository state. Never an
   * array index. */
  id: string;
  smell_type: SmellType;
  severity: Severity;
  /** How strongly the evidence supports reading this condition AS a finding
   * (0.0-1.0) -- distinct from `severity` (magnitude, if real) and from any
   * per-relationship resolver confidence inside `evidence_details`. */
  confidence: number;
  title: string;
  explanation: string;
  evidence: string;
  affected: AffectedSymbol[];
  context_flags: ContextFlag[];
  evidence_details: EvidenceRelationship[];
  /** Whether analysis.optimization currently has a deterministic
   * restoration strategy for this finding type -- false is an honest
   * "detectable, not (yet) actionable" status. */
  optimization_supported: boolean;
  /** IDs of other findings sharing the same root entity (e.g. a god_class
   * on a class and a large_function on one of its own methods). */
  related_finding_ids: string[];
}

export interface GraphNode {
  uid: string;
  symbol_type: string;
  name: string;
  qualified_name: string;
  file_path: string;
  start_line: number;
  end_line: number;
  degree: number;
}

export interface GraphEdge {
  source_uid: string;
  target_uid: string;
  relationship_type: string;
  weight: number;
}

export interface GraphViewResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  truncated: boolean;
}

export interface SymbolRef {
  uid: string;
  symbol_type: string;
  qualified_name: string;
  file_path: string;
}

export interface RelationshipStep {
  from_qualified_name: string;
  to_qualified_name: string;
  relationship_type: string;
  source_file: string | null;
  source_line: number | null;
  confidence: number | null;
}

/** Deterministic — decided by the resolver's direct-edge-first, then
 * shortest-path-fallback query order, never inferred client-side from
 * `steps.length` (a DIRECT pair can carry more than one parallel edge, e.g.
 * both CALLS and IMPORTS at once — see evidenceExplorer.ts). Null only when
 * `connected` is false. */
export type RelationshipKind = "DIRECT" | "INDIRECT";

export interface RelationshipResponse {
  source: SymbolRef;
  target: SymbolRef;
  connected: boolean;
  steps: RelationshipStep[];
  explanation: string;
  relationship_kind: RelationshipKind | null;
  hop_count: number | null;
}

export interface SymbolSearchResult {
  uid: string;
  symbol_type: string;
  name: string;
  qualified_name: string;
  file_path: string;
  start_line: number;
}

export interface Dependent {
  uid: string;
  symbol_type: string;
  name: string;
  qualified_name: string;
  file_path: string;
  start_line: number;
  end_line: number;
  depth: number;
}

export interface ExternalDependency {
  name: string;
  category: "database" | "external_service";
}

export interface RiskSignal {
  name: string;
  value: string;
  points: number;
}

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type ComponentRole =
  | "api"
  | "service"
  | "data_access"
  | "external_integration"
  | "model"
  | "test"
  | "other";

export type ArchitectureConfidenceLabel = "Confirmed" | "Inferred" | "Uncertain";

export interface ThirdPartyDependency {
  name: string;
  category: "database" | "external_service";
}

export interface ArchitectureComponent {
  id: string;
  name: string;
  role: ComponentRole;
  file_count: number;
  symbol_count: number;
  files: string[];
  confidence: number;
  confidence_label: ArchitectureConfidenceLabel;
  evidence: string[];
  third_party_dependencies: ThirdPartyDependency[];
}

export interface ComponentRelationship {
  source_id: string;
  target_id: string;
  call_count: number;
  confidence: number;
  confidence_label: ArchitectureConfidenceLabel;
  evidence: string[];
}

export interface ArchitectureModel {
  repo_id: string;
  components: ArchitectureComponent[];
  relationships: ComponentRelationship[];
  truncated: boolean;
  detection_notes: string[];
}

export type OptimizationGoal = "enforce_layering" | "reduce_circularity" | "reduce_coupling";

export interface RepresentativeImpact {
  symbol_qualified_name: string;
  direct_dependents: number;
  indirect_dependents: number;
  risk_level: RiskLevel;
}

export interface OptimizationProposal {
  id: string;
  goal: OptimizationGoal;
  problem: string;
  evidence: string;
  proposed_change: string;
  expected_benefit: string;
  potential_risk: string;
  risk_level: RiskLevel;
  confidence: number;
  confidence_label: ArchitectureConfidenceLabel;
  affected_components: string[];
  affected_files: string[];
  representative_impact: RepresentativeImpact | null;
  /** The Architecture Analysis finding this proposal was generated from,
   * when one exists -- an explicit, stable link (via the same content-
   * addressed id /smells uses) replacing the previous implicit
   * title-string correlation between the two endpoints. */
  finding_id: string | null;
}

export interface OptimizationReport {
  repo_id: string;
  current_architecture_summary: string;
  proposals: OptimizationProposal[];
  detection_notes: string[];
}

export type FlowLabel = "OBSERVED" | "PROPOSED";

export interface EntryPoint {
  uid: string;
  qualified_name: string;
  file_path: string;
  start_line: number;
  route_hint: string | null;
}

export interface FlowHop {
  label: FlowLabel;
  caller_qualified_name: string;
  callee_qualified_name: string;
  callee_uid: string | null;
  relationship_type: string;
  source_file: string | null;
  source_line: number | null;
  confidence: number;
  terminal_kind: "database" | "external_service" | null;
  /** The callee's own file — distinct from source_file/source_line, which is
   * the call-site evidence inside the *caller*. */
  callee_file_path: string | null;
  component_id: string | null;
  component_role: ComponentRole | null;
  component_name: string | null;
  /** Why traversal stopped here — null whenever `children` is non-empty.
   * "NO_RESOLVED_CALLEES" | "STANDARD_LIBRARY" | "EXTERNAL_DEPENDENCY" |
   * "UNRESOLVED" | "DEPTH_LIMIT" | "BRANCH_LIMIT". Distinct from
   * `terminal_kind`, which is the callee's Architecture *role* and no longer
   * implies traversal stopped there. */
  terminal_reason: string | null;
  /** Additional resolved calls this symbol has beyond the branch cap. */
  children_omitted: number;
  note: string | null;
  children: FlowHop[];
}

export interface ExecutionFlowReport {
  repo_id: string;
  entry: EntryPoint;
  observed: FlowHop;
  proposed: FlowHop | null;
  truncated: boolean;
  detection_notes: string[];
}

export interface CommitInfo {
  sha: string;
  short_sha: string;
  author_name: string;
  authored_date: string;
  subject: string;
  files_changed: number;
}

export interface ComponentHistory {
  component_id: string;
  component_name: string;
  role: ComponentRole;
  commit_count: number;
  first_seen: string;
  last_changed: string;
  top_authors: [string, number][];
  introduction_commit: CommitInfo;
}

export interface HistoryReport {
  repo_id: string;
  commits_analyzed: number;
  history_truncated: boolean;
  components: ComponentHistory[];
  recent_commits: CommitInfo[];
  detection_notes: string[];
}

export interface ImpactReport {
  target_uid: string;
  target_qualified_name: string;
  target_symbol_type: string;
  target_file_path: string;
  direct_dependents: Dependent[];
  indirect_dependents: Dependent[];
  affected_apis: Dependent[];
  affected_services: Dependent[];
  affected_tests: Dependent[];
  external_dependencies: ExternalDependency[];
  risk_level: RiskLevel;
  risk_score: number;
  risk_signals: RiskSignal[];
  explanation: string;
  detection_notes: string[];
}
