import { confidenceTier } from "@/lib/analysisModel";
import { CONTEXT_FLAG_LABELS, SMELL_TYPE_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { Smell } from "@/api/types";

const SEVERITY_STYLE = {
  HIGH: "border-l-(--bad)",
  MEDIUM: "border-l-(--warn)",
  LOW: "border-l-(--border-strong)",
} as const;

function SeverityPill({ severity }: { severity: Smell["severity"] }) {
  return (
    <span
      className={cn(
        "rounded px-1.5 py-0.5 font-mono text-[0.65rem] font-bold tracking-wide",
        severity === "HIGH" && "bg-(--bad)/14 text-(--bad)",
        severity === "MEDIUM" && "bg-(--warn)/14 text-(--warn)",
        severity === "LOW" && "bg-(--bg-sunken) text-(--text-faint)",
      )}
    >
      {severity}
    </span>
  );
}

/** Compact confidence indicator — deliberately a meter, not the
 * Confirmed/Inferred/Uncertain pill ConfidenceBadge uses elsewhere, so
 * finding confidence is never visually mistaken for component/relationship
 * (resolver) confidence (CLAUDE.md V2 UI §4). */
export function FindingConfidenceMeter({ confidence, className }: { confidence: number; className?: string }) {
  const tier = confidenceTier(confidence);
  const colorVar = tier === "High" ? "--ok" : tier === "Medium" ? "--bronze" : "--text-faint";
  return (
    <span className={cn("inline-flex shrink-0 items-center gap-1.5", className)} title="Finding confidence">
      <span className="h-1.5 w-9 overflow-hidden rounded-full bg-(--bg-sunken)">
        <span
          className="block h-full"
          style={{ width: `${Math.round(confidence * 100)}%`, backgroundColor: `var(${colorVar})` }}
        />
      </span>
      <span className="font-mono text-[0.65rem] font-semibold tracking-wide" style={{ color: `var(${colorVar})` }}>
        {tier}
      </span>
    </span>
  );
}

function affectedSummary(smell: Smell): string | null {
  if (smell.evidence_details.length > 0) {
    const d = smell.evidence_details[0];
    return `${d.source} → ${d.target}`;
  }
  return smell.affected[0]?.qualified_name ?? null;
}

export function FindingCard({
  smell,
  selected,
  onSelect,
}: {
  smell: Smell;
  selected: boolean;
  onSelect: () => void;
}) {
  const summary = affectedSummary(smell);
  const visibleFlags = smell.context_flags.slice(0, 3);
  const hiddenFlagCount = smell.context_flags.length - visibleFlags.length;

  return (
    <button
      onClick={onSelect}
      aria-current={selected ? "true" : undefined}
      className={cn(
        "flex w-full flex-col gap-1.5 rounded-lg border border-(--border) border-l-[3px] bg-(--bg-raised) p-3.5 text-left transition-colors",
        SEVERITY_STYLE[smell.severity],
        selected ? "ring-2 ring-(--accent)/40" : "hover:border-(--accent)/30",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <SeverityPill severity={smell.severity} />
        <span className="text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
          {SMELL_TYPE_LABELS[smell.smell_type] ?? smell.smell_type}
        </span>
        <FindingConfidenceMeter confidence={smell.confidence} className="ml-auto" />
      </div>

      <p className="text-sm font-medium text-(--text)">{smell.title}</p>

      {summary && <code className="truncate font-mono text-xs text-(--text-faint)">{summary}</code>}

      {visibleFlags.length > 0 && (
        <div className="flex flex-wrap items-center gap-1">
          {visibleFlags.map((flag) => (
            <span
              key={flag}
              className="rounded-full border border-(--border) bg-(--bg-sunken) px-1.5 py-0.5 text-[0.6rem] font-medium text-(--text-faint)"
            >
              {CONTEXT_FLAG_LABELS[flag]}
            </span>
          ))}
          {hiddenFlagCount > 0 && <span className="text-[0.6rem] text-(--text-faint)">+{hiddenFlagCount} more</span>}
        </div>
      )}
    </button>
  );
}
