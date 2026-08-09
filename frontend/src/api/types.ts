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

export type SmellType = "circular_dependency" | "god_class" | "large_function" | "dead_code_candidate";
export type Severity = "LOW" | "MEDIUM" | "HIGH";

export interface Smell {
  smell_type: SmellType;
  severity: Severity;
  title: string;
  explanation: string;
  evidence: string;
  affected: AffectedSymbol[];
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
