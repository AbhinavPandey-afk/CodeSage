import type { ComponentRole, OptimizationGoal, SmellType } from "@/api/types";

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
