import type { ComponentRole, ContextFlag, OptimizationGoal, SmellType } from "@/api/types";
import type { Tab } from "@/lib/navigation";

/** Keys match backend/app/core/languages.py's `Language` enum values —
 * the only five languages CLAUDE.md scopes this project to. */
export const LANGUAGE_LABELS: Record<string, string> = {
  python: "Python",
  javascript: "JavaScript",
  typescript: "TypeScript",
  java: "Java",
  cpp: "C++",
};

/** Overview's "Quick investigation actions" — action-oriented, distinct from
 * NAV_GROUPS' `question` (the dominant question each page's own PageHeader
 * answers) so the two can read differently without one overwriting the other. */
export const NAV_ACTION_HINTS: Partial<Record<Tab, string>> = {
  architecture: "Understand the reconstructed structure",
  flow: "Trace an operation",
  graph: "Inspect structural evidence",
  smells: "Investigate structural problems",
  impact: "Assess change consequences",
  optimization: "Review restoration proposals",
  history: "Study architectural evolution",
  ask: "Ask an evidence-backed question",
};

export const ROLE_LABELS: Record<ComponentRole, string> = {
  api: "API layer",
  service: "Service layer",
  data_access: "Data access",
  external_integration: "External integration",
  model: "Model / schema",
  test: "Tests",
  other: "Other",
};

export const SMELL_TYPE_LABELS: Record<SmellType, string> = {
  circular_dependency: "Circular dependency",
  god_class: "God class",
  large_function: "Large function",
  dead_code_candidate: "Dead code candidate",
  architecture_boundary_violation: "Architecture boundary violation",
  layer_skip: "Layer skip",
  circular_component_dependency: "Circular component dependency",
  excessive_component_coupling: "Excessive component coupling",
};

export const OPTIMIZATION_GOAL_LABELS: Record<OptimizationGoal, string> = {
  enforce_layering: "Enforce layering",
  reduce_circularity: "Reduce circularity",
  reduce_coupling: "Reduce coupling",
};

export type SmellCategory = "layering" | "circularity" | "coupling" | "symbol";

export const SMELL_CATEGORY: Record<SmellType, SmellCategory> = {
  layer_skip: "layering",
  architecture_boundary_violation: "layering",
  circular_dependency: "circularity",
  circular_component_dependency: "circularity",
  excessive_component_coupling: "coupling",
  god_class: "symbol",
  large_function: "symbol",
  dead_code_candidate: "symbol",
};

export const SMELL_CATEGORY_LABELS: Record<SmellCategory, string> = {
  layering: "Layer violations",
  circularity: "Circular dependencies",
  coupling: "Coupling",
  symbol: "Symbol smells",
};

/**
 * Disclosed detection limitations, taken directly from README.md's own
 * documentation of each detector — never invented here.
 *
 * architecture_boundary_violation, layer_skip and dead_code_candidate are
 * deliberately absent: the backend already bakes their caveat into
 * `explanation` itself (`_ROLE_HEURISTIC_CAVEAT` in
 * analysis/smells/architecture_violations.py, and dead-code's own
 * heuristic-limits sentence) — repeating it here would just duplicate the
 * same sentence directly underneath.
 */
export const SMELL_LIMITATIONS: Partial<Record<SmellType, string>> = {
  circular_component_dependency:
    "Component roles are inferred heuristically from directory and naming conventions.",
  excessive_component_coupling:
    "Component roles are inferred heuristically from directory and naming conventions.",
};

/** Human-readable labels for context_flags (backend:
 * analysis/smells/context.py + each detector's confidence rule) — the raw
 * enum string is never shown as the primary UI (CLAUDE.md V2 UI §3). */
export const CONTEXT_FLAG_LABELS: Record<ContextFlag, string> = {
  EXPECTED_TEST_DEPENDENCY: "Expected test dependency",
  FRAMEWORK_HUB: "Framework hub",
  SUPPORTING_STRUCTURE: "Supporting structure",
  DYNAMIC_DISPATCH_RISK: "Dynamic dispatch risk",
  HEURISTIC_LAYERING: "Heuristic layering",
  INTRA_CLASS_DELEGATION: "Intra-class delegation",
  METHOD_COUNT_HEURISTIC: "Method-count heuristic",
  LENGTH_BASED_HEURISTIC: "Length-based heuristic",
};

/** One-sentence explanation per flag, evidence-derived and taken from the
 * same reasoning the backend's own confidence rule applies — never a
 * separate, unverified claim invented for the UI. */
export const CONTEXT_FLAG_DESCRIPTIONS: Record<ContextFlag, string> = {
  EXPECTED_TEST_DEPENDENCY:
    "One participant is reconstructed as test infrastructure — bidirectional test/source interaction is common and expected.",
  FRAMEWORK_HUB:
    "This component is widely relied upon by others, or plays an API/integration role — high connectivity or a large surface can reflect that rather than poor design.",
  SUPPORTING_STRUCTURE:
    "This entity lives in supporting infrastructure (tests, docs, tooling) rather than the runtime system.",
  DYNAMIC_DISPATCH_RISK:
    "Static analysis cannot see dynamic dispatch, reflection, or framework-invoked hooks — absence of a recorded caller is not proof of dead code.",
  HEURISTIC_LAYERING:
    "The component roles behind this finding are inferred heuristically from directory structure and naming conventions.",
  INTRA_CLASS_DELEGATION:
    "Every symbol in this cycle belongs to the same class — likely internal delegation between its own methods, not cross-module coupling.",
  METHOD_COUNT_HEURISTIC:
    "Based on method count alone — a proxy for cohesion, not direct proof of it.",
  LENGTH_BASED_HEURISTIC:
    "Based on line count alone — measures length, not cognitive complexity.",
};

/** The subset of flags that specifically describe *how* a finding was
 * detected (as opposed to *why confidence was adjusted*) — surfaced as a
 * finding's "Detection basis" (CLAUDE.md V2 UI §25). */
export const DETECTION_BASIS_FLAGS: ReadonlySet<ContextFlag> = new Set([
  "METHOD_COUNT_HEURISTIC",
  "LENGTH_BASED_HEURISTIC",
  "DYNAMIC_DISPATCH_RISK",
]);
