import { LayoutGrid, Link2Off, Radar, RefreshCcw, SquareStack } from "lucide-react";
import { ConfidenceBadge } from "@/components/evidence/ConfidenceBadge";
import { RiskBadge } from "@/components/evidence/RiskBadge";
import { useInvestigation } from "@/lib/investigation";
import { OPTIMIZATION_GOAL_LABELS } from "@/lib/labels";
import type { OptimizationProposal } from "@/api/types";

const GOAL_ICON = {
  enforce_layering: SquareStack,
  reduce_circularity: RefreshCcw,
  reduce_coupling: Link2Off,
};

function ActionButton({
  icon: Icon,
  label,
  onClick,
}: {
  icon: typeof Radar;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1.5 rounded-md border border-(--border) bg-(--bg) px-2.5 py-1.5 text-xs font-medium text-(--text-soft) transition-colors hover:border-(--accent)/40 hover:text-(--text)"
    >
      <Icon className="size-3.5" strokeWidth={2} />
      {label}
    </button>
  );
}

export function RestorationCard({
  proposal,
  index,
  componentId,
}: {
  proposal: OptimizationProposal;
  index: number;
  componentId: string | null;
}) {
  const { navigate } = useInvestigation();
  const Icon = GOAL_ICON[proposal.goal] ?? SquareStack;

  return (
    <div className="rounded-lg border border-(--border) bg-(--bg-raised) p-5">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs font-semibold text-(--accent-text) tabular-nums">
          {String(index).padStart(2, "0")}
        </span>
        <span className="flex items-center gap-1.5 rounded bg-(--bg-sunken) px-2 py-0.5 text-xs font-medium text-(--text-soft)">
          <Icon className="size-3.5" strokeWidth={2} />
          {OPTIMIZATION_GOAL_LABELS[proposal.goal] ?? proposal.goal}
        </span>
        <RiskBadge level={proposal.risk_level} />
        <ConfidenceBadge label={proposal.confidence_label} />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-md border border-(--border) bg-(--bg) p-3.5">
          <span className="inline-flex items-center gap-1 rounded-md border border-(--border) bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.6rem] font-bold tracking-wider text-(--text-faint) uppercase">
            Observed
          </span>
          <p className="mt-2 text-sm text-(--text)">{proposal.problem}</p>
          <p className="mt-2 font-mono text-xs text-(--text-faint)">{proposal.evidence}</p>
        </div>
        <div className="rounded-md border border-(--accent)/25 bg-(--accent-soft) p-3.5">
          <span className="inline-flex items-center gap-1 rounded-md border border-(--accent)/30 bg-(--bg-raised) px-1.5 py-0.5 font-mono text-[0.6rem] font-bold tracking-wider text-(--accent-text) uppercase">
            Proposed — recommendation only
          </span>
          <p className="mt-2 text-sm text-(--text)">{proposal.proposed_change}</p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <p className="text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
            Expected benefit
          </p>
          <p className="mt-1 text-sm text-(--text-soft)">{proposal.expected_benefit}</p>
        </div>
        <div>
          <p className="text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
            Potential risk
          </p>
          <p className="mt-1 text-sm text-(--text-soft)">{proposal.potential_risk}</p>
        </div>
      </div>

      {proposal.representative_impact && (
        <p className="mt-4 border-t border-(--border) pt-3 text-xs text-(--text-faint)">
          Representative impact check:{" "}
          <code className="text-(--text-soft)">{proposal.representative_impact.symbol_qualified_name}</code> has{" "}
          {proposal.representative_impact.direct_dependents} direct and{" "}
          {proposal.representative_impact.indirect_dependents} indirect dependent(s).
        </p>
      )}

      <p className="mt-3 text-xs text-(--text-faint)">
        Affects: {proposal.affected_components.join(", ")} ({proposal.affected_files.length} file
        {proposal.affected_files.length === 1 ? "" : "s"})
      </p>

      <div className="mt-4 flex flex-wrap gap-1.5 border-t border-(--border) pt-4">
        {componentId && (
          <ActionButton
            icon={LayoutGrid}
            label="Show on Architecture"
            onClick={() => navigate("architecture", { componentId })}
          />
        )}
        {proposal.representative_impact && (
          <ActionButton
            icon={Radar}
            label="View Impact"
            onClick={() =>
              navigate("impact", { qualifiedName: proposal.representative_impact!.symbol_qualified_name })
            }
          />
        )}
      </div>
    </div>
  );
}
