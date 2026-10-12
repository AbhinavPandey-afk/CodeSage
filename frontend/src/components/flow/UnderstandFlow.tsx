import { ArrowDown, ChevronRight } from "lucide-react";
import { confidenceLabel, type TraceNode } from "@/lib/flowModel";
import { TERMINAL_REASON_LABEL } from "@/lib/terminalReasons";
import { cn } from "@/lib/utils";
import { EvidenceStatusBadge } from "@/components/flow/EvidenceStatusBadge";
import { nodeIcon, nodeRoleVar } from "./roleStyle";

/** UNDERSTAND: a strictly linear, staged pipeline — no branch routing, no
 * file paths, no line numbers. This is deliberately a different component
 * from the Symbols tree, not a resized version of it: the question it
 * answers is "what happens", not "which functions call which". */
export function UnderstandFlow({
  stages,
  selectedId,
  onSelect,
  onExpandEvidence,
}: {
  stages: TraceNode[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onExpandEvidence: (memberId: string) => void;
}) {
  return (
    <div className="flex flex-col items-center rounded-lg border border-(--border) bg-(--bg-inset) px-4 py-8 sm:px-8">
      <div className="flex w-full max-w-xl flex-col items-center">
        <div className="mb-3 rounded-md border border-(--border-strong) bg-(--bg-raised) px-3 py-1 text-center font-mono text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
          Incoming Request
        </div>
        <ArrowDown className="mb-3 size-4 text-(--text-faint)" />

        {stages.map((stage, i) => {
          const Icon = nodeIcon(stage);
          const roleVar = nodeRoleVar(stage);
          const isSelected = selectedId === stage.id;
          const isTerminal = stage.terminalReason !== null;
          const conf = confidenceLabel(stage.confidence);

          return (
            <div key={stage.id} className="flex w-full flex-col items-center">
              <button
                type="button"
                onClick={() => onSelect(stage.id)}
                aria-pressed={isSelected}
                style={{ borderColor: isSelected ? `var(${roleVar})` : undefined }}
                className={cn(
                  "flex w-full flex-col items-center gap-1.5 rounded-xl border-2 bg-(--bg-raised) px-6 py-5 text-center shadow-sm transition-all hover:shadow-md",
                  "focus-visible:ring-2 focus-visible:ring-(--accent) focus-visible:ring-offset-2 focus-visible:ring-offset-(--bg-inset) focus-visible:outline-none",
                  isSelected ? "ring-2 ring-(--accent)/25" : "border-(--border)",
                )}
              >
                <span
                  className="flex size-9 items-center justify-center rounded-full"
                  style={{ backgroundColor: `color-mix(in oklab, var(${roleVar}) 16%, transparent)`, color: `var(${roleVar})` }}
                >
                  <Icon className="size-4.5" strokeWidth={2} />
                </span>

                <EvidenceStatusBadge status={stage.status} />

                <p className="font-display text-lg font-medium text-(--text)">{stage.name}</p>
                {stage.subtitle && <p className="font-mono text-xs text-(--text-faint)">{stage.subtitle}</p>}

                <div className="mt-1 flex flex-wrap items-center justify-center gap-1.5">
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
                  {isTerminal && (
                    <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                      {TERMINAL_REASON_LABEL[stage.terminalReason!]}
                    </span>
                  )}
                </div>

                {stage.branchOmitted > 0 && (
                  <p className="text-[0.68rem] text-(--text-faint) italic">
                    +{stage.branchOmitted} other branch{stage.branchOmitted === 1 ? "" : "es"} not shown here — see Components or Symbols
                  </p>
                )}

                {stage.kind !== "entry" && (
                  <span
                    role="button"
                    tabIndex={0}
                    onClick={(e) => {
                      e.stopPropagation();
                      onExpandEvidence(stage.memberIds[stage.memberIds.length - 1]);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.stopPropagation();
                        onExpandEvidence(stage.memberIds[stage.memberIds.length - 1]);
                      }
                    }}
                    className="mt-1 flex items-center gap-0.5 text-[0.7rem] font-medium text-(--accent-text) hover:underline"
                  >
                    Expand evidence <ChevronRight className="size-3" />
                  </span>
                )}
              </button>

              {i < stages.length - 1 && <ArrowDown className="my-3 size-4 text-(--text-faint)" />}
            </div>
          );
        })}

        <ArrowDown className="mt-3 mb-3 size-4 text-(--text-faint)" />
        <div className="rounded-md border border-(--border-strong) bg-(--bg-raised) px-3 py-1 text-center font-mono text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
          {stages[stages.length - 1]?.terminalReason ? "Reconstruction Boundary" : "Response / Completion"}
        </div>
      </div>
    </div>
  );
}
