import { ChevronRight } from "lucide-react";
import { confidenceLabel, type TraceNode } from "@/lib/flowModel";
import { ROLE_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { EvidenceStatusBadge } from "@/components/flow/EvidenceStatusBadge";
import { nodeIcon, nodeRoleVar } from "./roleStyle";

/** COMPONENTS: each distinct Architecture component that participates
 * anywhere in the trace appears exactly once — reached from three different
 * call paths is still one card, with "participates N times" and "leads to"
 * disclosed on it, not three repeated boxes for the same folder. This
 * answers "which architectural units participate, and in what order do they
 * first get involved", not the branching call structure (that's Symbols). */
export function ComponentFlow({
  components,
  selectedId,
  onSelect,
  onExpandEvidence,
}: {
  components: TraceNode[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onExpandEvidence: (memberId: string) => void;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-(--border) bg-(--bg-inset) p-4 sm:p-6">
      {components.map((component, i) => {
        const Icon = nodeIcon(component);
        const roleVar = nodeRoleVar(component);
        const isSelected = selectedId === component.id;
        const isTerminal = component.terminalReason !== null;
        const conf = confidenceLabel(component.confidence);

        return (
          <div key={component.id} className="flex items-stretch gap-3">
            <div className="flex w-6 shrink-0 flex-col items-center">
              <span
                className="flex size-6 items-center justify-center rounded-full font-mono text-[0.65rem] font-semibold"
                style={{ backgroundColor: `color-mix(in oklab, var(${roleVar}) 18%, transparent)`, color: `var(${roleVar})` }}
              >
                {i + 1}
              </span>
              {i < components.length - 1 && <span className="mt-1 w-px flex-1 bg-(--border-strong)" />}
            </div>

            <button
              type="button"
              onClick={() => onSelect(component.id)}
              aria-pressed={isSelected}
              style={{ borderColor: isSelected ? `var(${roleVar})` : undefined }}
              className={cn(
                "mb-2 flex flex-1 flex-col gap-1.5 rounded-lg border bg-(--bg-raised) px-4 py-3.5 text-left shadow-sm transition-all hover:shadow-md",
                "focus-visible:ring-2 focus-visible:ring-(--accent) focus-visible:ring-offset-2 focus-visible:ring-offset-(--bg-inset) focus-visible:outline-none",
                isSelected ? "border-2 ring-2 ring-(--accent)/25" : "border-(--border)",
              )}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className="flex size-6 shrink-0 items-center justify-center rounded"
                  style={{ backgroundColor: `color-mix(in oklab, var(${roleVar}) 16%, transparent)`, color: `var(${roleVar})` }}
                >
                  <Icon className="size-3.5" strokeWidth={2.25} />
                </span>
                <p className="text-[0.95rem] font-medium text-(--text)">{component.name}</p>
                <EvidenceStatusBadge status={component.status} />
                {component.componentRole && (
                  <span className="font-mono text-[0.65rem] text-(--text-faint) uppercase">{ROLE_LABELS[component.componentRole]}</span>
                )}
              </div>

              {component.subtitle && <p className="text-xs text-(--text-faint)">{component.subtitle}</p>}

              <div className="flex flex-wrap items-center gap-1.5">
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
                {component.note && (
                  <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 text-[0.65rem] text-(--text-faint)">{component.note}</span>
                )}
                <span
                  role="button"
                  tabIndex={0}
                  onClick={(e) => {
                    e.stopPropagation();
                    onExpandEvidence(component.memberIds[0]);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.stopPropagation();
                      onExpandEvidence(component.memberIds[0]);
                    }
                  }}
                  className="ml-auto flex items-center gap-0.5 text-[0.7rem] font-medium text-(--accent-text) hover:underline"
                >
                  Expand evidence <ChevronRight className="size-3" />
                </span>
              </div>

              {isTerminal && (
                <p className="text-[0.68rem] text-(--text-faint) italic">Reconstruction stops within this component in at least one branch.</p>
              )}
            </button>
          </div>
        );
      })}

      {components.length === 0 && <p className="text-sm text-(--text-faint)">No architectural components were reconstructed for this trace.</p>}
    </div>
  );
}
