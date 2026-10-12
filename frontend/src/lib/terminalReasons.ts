/** The backend's `terminal_reason` enum (analysis/execution_flow/models.py) —
 * why traversal actually stopped at a hop. Deliberately separate from
 * `terminal_kind` (the callee's Architecture *role*): a component classified
 * external_integration can still have further resolved calls within the
 * same repository, so `terminal_kind` truthy must never be read as "this
 * step is terminal" — only `terminal_reason` (equivalently: `children.length
 * === 0`) means that. */
export type TerminalReason =
  | "NO_RESOLVED_CALLEES"
  | "STANDARD_LIBRARY"
  | "EXTERNAL_DEPENDENCY"
  | "UNRESOLVED"
  | "DEPTH_LIMIT"
  | "BRANCH_LIMIT";

export const TERMINAL_REASON_LABEL: Record<TerminalReason, string> = {
  NO_RESOLVED_CALLEES: "No further calls",
  STANDARD_LIBRARY: "Standard library",
  EXTERNAL_DEPENDENCY: "External dependency",
  UNRESOLVED: "Unresolved",
  DEPTH_LIMIT: "Depth limit",
  BRANCH_LIMIT: "Branch limit",
};

/** Matches the phrasing given for each reason — generalized only where the
 * backend doesn't expose a specific module name to the API (e.g. "a
 * standard-library boundary" rather than naming a specific module, since
 * inventing one here would be a fabrication the backend data doesn't support). */
export const TERMINAL_REASON_EXPLANATION: Record<TerminalReason, string> = {
  NO_RESOLVED_CALLEES: "No additional repository calls were reconstructed from here.",
  STANDARD_LIBRARY: "Static reconstruction reaches a standard-library boundary — the call target is part of the language's own standard library, not this repository.",
  EXTERNAL_DEPENDENCY: "Execution crosses into a dependency whose implementation is outside the analyzed repository.",
  UNRESOLVED: "The call target could not be resolved from available repository evidence.",
  DEPTH_LIMIT: "Further resolved calls exist here, but traversal depth is capped to keep the trace readable.",
  BRANCH_LIMIT: "Additional resolved branches exist here but were omitted to keep the trace readable.",
};

export function isTerminalReason(value: string | null): value is TerminalReason {
  return value !== null && value in TERMINAL_REASON_LABEL;
}
