import { LayoutGrid, Network, Radar } from "lucide-react";
import { useInvestigation } from "@/lib/investigation";
import { SMELL_LIMITATIONS, SMELL_TYPE_LABELS } from "@/lib/labels";
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

function ActionButton({
  icon: Icon,
  label,
  onClick,
}: {
  icon: typeof Network;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1.5 rounded-md border border-(--border) bg-(--bg-raised) px-2.5 py-1.5 text-xs font-medium text-(--text-soft) transition-colors hover:border-(--accent)/40 hover:text-(--text)"
    >
      <Icon className="size-3.5" strokeWidth={2} />
      {label}
    </button>
  );
}

export function FindingCard({ smell, componentId }: { smell: Smell; componentId: string | null }) {
  const { navigate } = useInvestigation();
  const limitation = SMELL_LIMITATIONS[smell.smell_type];
  const primary = smell.affected[0];

  return (
    <div className={cn("rounded-lg border border-(--border) border-l-[3px] bg-(--bg-raised) p-4", SEVERITY_STYLE[smell.severity])}>
      <div className="flex flex-wrap items-center gap-2">
        <SeverityPill severity={smell.severity} />
        <span className="text-[0.68rem] font-semibold tracking-wide text-(--text-faint) uppercase">
          {SMELL_TYPE_LABELS[smell.smell_type] ?? smell.smell_type}
        </span>
      </div>

      <p className="mt-2 text-sm font-medium text-(--text)">{smell.title}</p>

      <div className="mt-2.5">
        <p className="text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">Why this matters</p>
        <p className="mt-1 text-sm leading-relaxed text-(--text-soft)">{smell.explanation}</p>
      </div>

      <div className="mt-2.5">
        <p className="text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">Evidence</p>
        <p className="mt-1 font-mono text-xs text-(--text-faint)">{smell.evidence}</p>
      </div>

      {smell.affected.length > 0 && (
        <ul className="mt-2.5 flex flex-col gap-0.5 border-t border-(--border) pt-2.5">
          {smell.affected.slice(0, 4).map((a, i) => (
            <li key={i} className="font-mono text-xs text-(--text-faint)">
              <code className="text-(--text-soft)">{a.qualified_name}</code> — {a.file_path}:{a.start_line}
            </li>
          ))}
          {smell.affected.length > 4 && (
            <li className="text-xs text-(--text-faint) italic">…and {smell.affected.length - 4} more</li>
          )}
        </ul>
      )}

      {limitation && (
        <p className="mt-2.5 border-t border-(--border) pt-2.5 text-xs text-(--text-faint) italic">{limitation}</p>
      )}

      <div className="mt-3 flex flex-wrap gap-1.5">
        {componentId && (
          <ActionButton
            icon={LayoutGrid}
            label="Show on Architecture"
            onClick={() => navigate("architecture", { componentId })}
          />
        )}
        {primary && (
          <>
            <ActionButton
              icon={Network}
              label="View Evidence"
              onClick={() => navigate("graph", { qualifiedName: primary.qualified_name })}
            />
            <ActionButton
              icon={Radar}
              label="View Impact"
              onClick={() => navigate("impact", { qualifiedName: primary.qualified_name })}
            />
          </>
        )}
      </div>
    </div>
  );
}
