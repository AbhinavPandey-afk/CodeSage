import { CheckCircle2, CircleDashed, CircleHelp } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ArchitectureConfidenceLabel } from "@/api/types";

const CONFIG: Record<
  ArchitectureConfidenceLabel,
  { icon: typeof CheckCircle2; className: string; hint: string }
> = {
  Confirmed: {
    icon: CheckCircle2,
    className: "text-(--ok) bg-(--ok)/12 border-(--ok)/25",
    hint: "Derived directly from repository evidence.",
  },
  Inferred: {
    icon: CircleDashed,
    className: "text-(--bronze) bg-(--bronze)/14 border-(--bronze)/28",
    hint: "Derived from multiple pieces of evidence using deterministic heuristics.",
  },
  Uncertain: {
    icon: CircleHelp,
    className: "text-(--text-faint) bg-(--bg-sunken) border-(--border)",
    hint: "The available evidence was insufficient for a confident determination.",
  },
};

export function ConfidenceBadge({
  label,
  className,
}: {
  label: ArchitectureConfidenceLabel;
  className?: string;
}) {
  const cfg = CONFIG[label];
  const Icon = cfg.icon;
  return (
    <span
      title={cfg.hint}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[0.68rem] font-semibold tracking-wide uppercase",
        cfg.className,
        className,
      )}
    >
      <Icon className="size-3" strokeWidth={2.5} />
      {label}
    </span>
  );
}
