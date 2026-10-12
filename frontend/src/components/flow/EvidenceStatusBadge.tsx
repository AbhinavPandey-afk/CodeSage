import { Compass, Eye, Layers } from "lucide-react";
import type { EvidenceStatus } from "@/lib/flowModel";
import { cn } from "@/lib/utils";

const CONFIG: Record<EvidenceStatus, { icon: typeof Eye; label: string; className: string; hint: string }> = {
  OBSERVED: {
    icon: Eye,
    label: "Observed",
    className: "text-(--text-faint) bg-(--bg-sunken) border-(--border)",
    hint: "Directly a resolved repository symbol or relationship.",
  },
  DERIVED: {
    icon: Layers,
    label: "Derived",
    className: "text-(--bronze) bg-(--bronze)/14 border-(--bronze)/28",
    hint: "A semantic grouping built from observed evidence — an interpretation, not a repository fact on its own.",
  },
  PROPOSED: {
    icon: Compass,
    label: "Proposed",
    className: "text-(--accent-text) bg-(--accent-soft) border-(--accent)/30",
    hint: "A design projection from Architecture Optimization — not part of the current implementation.",
  },
};

/** The one place OBSERVED/DERIVED/PROPOSED gets rendered, so Understand,
 * Components, and the inspector never drift into inconsistent wording. */
export function EvidenceStatusBadge({ status, className }: { status: EvidenceStatus; className?: string }) {
  const cfg = CONFIG[status];
  const Icon = cfg.icon;
  return (
    <span
      title={cfg.hint}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[0.62rem] font-semibold tracking-wide uppercase",
        cfg.className,
        className,
      )}
    >
      <Icon className="size-2.5" strokeWidth={2.5} />
      {cfg.label}
    </span>
  );
}
