import { AlertOctagon, AlertTriangle, ShieldAlert, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import type { RiskLevel } from "@/api/types";

const CONFIG: Record<RiskLevel, { icon: typeof ShieldCheck; className: string }> = {
  LOW: { icon: ShieldCheck, className: "text-(--ok) bg-(--ok)/12 border-(--ok)/25" },
  MEDIUM: { icon: ShieldAlert, className: "text-(--warn) bg-(--warn)/14 border-(--warn)/28" },
  HIGH: { icon: AlertTriangle, className: "text-(--bad) bg-(--bad)/14 border-(--bad)/30" },
  CRITICAL: {
    icon: AlertOctagon,
    className: "text-(--critical-fg) bg-(--critical) border-(--critical)",
  },
};

export function RiskBadge({ level, className }: { level: RiskLevel; className?: string }) {
  const cfg = CONFIG[level];
  const Icon = cfg.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-[0.7rem] font-bold tracking-wide",
        cfg.className,
        className,
      )}
    >
      <Icon className="size-3.5" strokeWidth={2.5} />
      {level}
    </span>
  );
}
