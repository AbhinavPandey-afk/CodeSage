import { ChevronDown, ChevronRight } from "lucide-react";
import type { TraceNode } from "@/lib/flowModel";
import { confidenceLabel } from "@/lib/flowModel";
import { TERMINAL_REASON_LABEL } from "@/lib/terminalReasons";
import { cn } from "@/lib/utils";
import { nodeIcon, nodeRoleVar } from "./roleStyle";

export type CardVisualState = "normal" | "faded" | "selected";

const KIND_LABEL: Record<TraceNode["kind"], string> = {
  entry: "Entry point",
  call: "Call step",
  proposed: "Proposed",
  continuation: "Continuation",
  stage: "Stage",
  component: "Component",
};

/** The Symbols-level card — the detailed, source-oriented trace. Deliberately
 * a single consistent technical style (name, qualified name, file:line,
 * relationship, confidence, terminal reason) rather than a "density variant"
 * shared with Understand/Components, which are entirely different
 * components with their own information architecture. */
export function TraceNodeCard({
  node,
  state,
  collapsed,
  onToggleCollapse,
  onSelect,
}: {
  node: TraceNode;
  state: CardVisualState;
  collapsed: boolean;
  onToggleCollapse: (() => void) | null;
  onSelect: () => void;
}) {
  const Icon = nodeIcon(node);
  const roleVar = nodeRoleVar(node);
  const isProposed = node.kind === "proposed";
  const isTerminal = node.terminalReason !== null;
  const conf = confidenceLabel(node.confidence);

  return (
    <div className={cn("relative w-64 shrink-0 transition-opacity duration-200", state === "faded" && "opacity-25")}>
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={state === "selected"}
        aria-label={`${node.name}, ${KIND_LABEL[node.kind]}${isTerminal ? `, ${TERMINAL_REASON_LABEL[node.terminalReason!]}` : ""}`}
        style={{ borderColor: state === "selected" ? `var(${roleVar})` : undefined }}
        className={cn(
          "flex w-full flex-col gap-1 rounded-lg border bg-(--bg-raised) px-3.5 py-3 text-left shadow-sm transition-all hover:shadow-md",
          "focus-visible:ring-2 focus-visible:ring-(--accent) focus-visible:ring-offset-2 focus-visible:ring-offset-(--bg-inset) focus-visible:outline-none",
          state === "selected" ? "border-2 ring-2 ring-(--accent)/25" : "border-(--border)",
          isProposed && "border-dashed",
        )}
      >
        <div className="flex items-center gap-1.5">
          <span
            className="flex size-5 shrink-0 items-center justify-center rounded"
            style={{ backgroundColor: `color-mix(in oklab, var(${roleVar}) 16%, transparent)`, color: `var(${roleVar})` }}
          >
            <Icon className="size-3.5" strokeWidth={2.25} />
          </span>
          <span className="truncate text-[0.62rem] font-semibold tracking-wide uppercase" style={{ color: `var(${roleVar})` }}>
            {KIND_LABEL[node.kind]}
          </span>
          {node.relationshipType && (
            <span className="ml-auto shrink-0 font-mono text-[0.6rem] text-(--text-faint)">{node.relationshipType}</span>
          )}
        </div>

        <p className="truncate text-sm font-medium text-(--text)">{node.name}</p>
        {node.qualifiedName && node.qualifiedName !== node.name && (
          <p className="truncate font-mono text-[0.65rem] text-(--text-faint)" title={node.qualifiedName}>
            {node.qualifiedName}
          </p>
        )}

        {node.filePath && (
          <p className="truncate font-mono text-[0.68rem] text-(--text-faint)">
            {node.filePath}
            {node.sourceLine ? `:${node.sourceLine}` : ""}
          </p>
        )}

        <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
          {!isProposed && (
            <span
              className={cn(
                "rounded px-1.5 py-0.5 font-mono text-[0.6rem] font-semibold tracking-wide uppercase",
                conf === "Confirmed" && "bg-(--ok)/12 text-(--ok)",
                conf === "Inferred" && "bg-(--bronze)/14 text-(--bronze)",
                conf === "Uncertain" && "bg-(--bg-sunken) text-(--text-faint)",
              )}
            >
              {conf}
            </span>
          )}
          {isProposed && (
            <span className="rounded bg-(--accent-soft) px-1.5 py-0.5 font-mono text-[0.6rem] font-semibold tracking-wide text-(--accent-text) uppercase">
              Design projection
            </span>
          )}
          {/* Terminal state comes from terminal_reason (did traversal actually
              stop here?), never from terminal_kind (architectural role) alone —
              a component classified external_integration can still have
              resolved children, and must not read as "terminal" when it does. */}
          {isTerminal && (
            <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">
              {TERMINAL_REASON_LABEL[node.terminalReason!]}
            </span>
          )}
          {node.children.length > 0 && (
            <span className="font-mono text-[0.6rem] text-(--text-faint)">
              → {node.children.length} {node.children.length === 1 ? "child" : "children"}
            </span>
          )}
        </div>
      </button>

      {onToggleCollapse && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onToggleCollapse();
          }}
          aria-label={collapsed ? `Expand ${node.name}` : `Collapse ${node.name}`}
          className="absolute -bottom-2.5 left-1/2 z-10 flex size-5 -translate-x-1/2 items-center justify-center rounded-full border border-(--border) bg-(--bg-raised) text-(--text-faint) shadow-sm hover:text-(--accent-text) focus-visible:ring-2 focus-visible:ring-(--accent) focus-visible:outline-none"
        >
          {collapsed ? <ChevronRight className="size-3" /> : <ChevronDown className="size-3" />}
        </button>
      )}

      {node.childrenOmitted > 0 && (
        <p className="mt-3 text-center text-[0.65rem] text-(--text-faint) italic">
          +{node.childrenOmitted} more resolved call{node.childrenOmitted === 1 ? "" : "s"} omitted
        </p>
      )}
    </div>
  );
}
