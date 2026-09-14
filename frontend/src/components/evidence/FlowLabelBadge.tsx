import { Compass, Eye } from "lucide-react";
import { cn } from "@/lib/utils";
import type { FlowLabel } from "@/api/types";

/**
 * Marks a piece of UI as OBSERVED (reconstructed from repository evidence)
 * vs PROPOSED (a design recommendation). Per CLAUDE.md §50 this distinction
 * must never be blurred — proposed content is never allowed to look like a
 * confirmed fact.
 */
export function FlowLabelBadge({ label, className }: { label: FlowLabel; className?: string }) {
  const isProposed = label === "PROPOSED";
  const Icon = isProposed ? Compass : Eye;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-[0.65rem] font-bold tracking-wider uppercase",
        isProposed
          ? "text-(--accent-text) bg-(--accent-soft) border-(--accent)/30"
          : "text-(--text-faint) bg-(--bg-sunken) border-(--border)",
        className,
      )}
    >
      <Icon className="size-3" strokeWidth={2.5} />
      {isProposed ? "Proposed" : "Observed"}
    </span>
  );
}
