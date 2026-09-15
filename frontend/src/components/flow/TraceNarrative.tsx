import { useEffect, useRef } from "react";
import type { NarrativeStep } from "@/lib/flowModel";
import { cn } from "@/lib/utils";

export function TraceNarrative({
  steps,
  selectedId,
  onSelectStep,
}: {
  steps: NarrativeStep[];
  selectedId: string | null;
  onSelectStep: (nodeId: string) => void;
}) {
  const itemRefs = useRef<Map<string, HTMLLIElement>>(new Map());

  useEffect(() => {
    if (!selectedId) return;
    itemRefs.current.get(selectedId)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedId]);

  return (
    <ol className="flex flex-col gap-1">
      {steps.map((step, i) => {
        const isSelected = step.nodeId === selectedId;
        return (
          <li
            key={step.nodeId}
            ref={(el) => {
              if (el) itemRefs.current.set(step.nodeId, el);
              else itemRefs.current.delete(step.nodeId);
            }}
          >
            <button
              type="button"
              onClick={() => onSelectStep(step.nodeId)}
              className={cn(
                "flex w-full items-baseline gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors",
                isSelected ? "bg-(--accent-soft)" : "hover:bg-(--bg-sunken)",
              )}
            >
              <span className="font-mono text-xs text-(--text-faint) tabular-nums">{i + 1}.</span>
              <span className={cn(step.proposed ? "text-(--accent-text)" : isSelected ? "text-(--text)" : "text-(--text-soft)")}>
                {step.text}
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
