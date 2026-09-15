import { ChevronDown, ChevronRight, Layers } from "lucide-react";
import type { TraceNode } from "@/lib/flowModel";
import { confidenceLabel } from "@/lib/flowModel";
import { cn } from "@/lib/utils";
import { nodeIcon, nodeRoleVar } from "./roleStyle";

export type CardVisualState = "normal" | "faded" | "selected";

const KIND_LABEL: Record<TraceNode["kind"], string> = {
  entry: "Entry point",
  call: "Call step",
  derived: "Derived stage",
  proposed: "Proposed",
};

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
  const isDerived = node.kind === "derived";
  const conf = confidenceLabel(node.confidence);

  return (
    <div
      className={cn(
        "relative w-60 shrink-0 transition-opacity duration-200",
        state === "faded" && "opacity-25",
      )}
    >
      <button
        type="button"
        onClick={onSelect}
        style={{ borderColor: state === "selected" ? `var(${roleVar})` : undefined }}
        className={cn(
          "flex w-full flex-col gap-1.5 rounded-lg border bg-(--bg-raised) px-3.5 py-3 text-left shadow-sm transition-all hover:shadow-md",
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
          <span
            className="truncate text-[0.62rem] font-semibold tracking-wide uppercase"
            style={{ color: `var(${roleVar})` }}
          >
            {KIND_LABEL[node.kind]}
          </span>
          {isDerived && <Layers className="ml-auto size-3 shrink-0 text-(--text-faint)" aria-label="Derived stage" />}
        </div>

        <p className="truncate text-sm font-medium text-(--text)" title={node.qualifiedName}>
          {node.name}
        </p>

        {node.filePath && (
          <p className="truncate font-mono text-[0.68rem] text-(--text-faint)">{node.filePath}</p>
        )}
        {!node.filePath && node.kind !== "entry" && node.kind !== "proposed" && node.collapsedCount > 1 && (
          <p className="font-mono text-[0.68rem] text-(--text-faint)">{node.collapsedCount} resolved calls</p>
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
          {node.terminalKind && (
            <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">
              Terminal
            </span>
          )}
          {node.collapsedCount > 1 && node.kind !== "derived" && (
            <span className="font-mono text-[0.6rem] text-(--text-faint)">×{node.collapsedCount}</span>
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
          className="absolute -bottom-2.5 left-1/2 z-10 flex size-5 -translate-x-1/2 items-center justify-center rounded-full border border-(--border) bg-(--bg-raised) text-(--text-faint) shadow-sm hover:text-(--accent-text)"
        >
          {collapsed ? <ChevronRight className="size-3" /> : <ChevronDown className="size-3" />}
        </button>
      )}

      {node.branchOmitted > 0 && (
        <p className="mt-3 text-center text-[0.65rem] text-(--text-faint) italic">
          +{node.branchOmitted} other branch{node.branchOmitted === 1 ? "" : "es"} not shown
        </p>
      )}
    </div>
  );
}
