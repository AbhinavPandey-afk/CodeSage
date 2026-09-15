import { Plus } from "lucide-react";
import type { ProposedChange } from "@/lib/flowModel";

export function FlowDiffSummary({
  changes,
  onSelectChange,
}: {
  changes: ProposedChange[];
  onSelectChange?: (nodeId: string) => void;
}) {
  if (changes.length === 0) return null;

  return (
    <div className="rounded-lg border border-(--accent)/25 bg-(--accent-soft) p-4">
      <h3 className="mb-2 text-[0.65rem] font-semibold tracking-wide text-(--accent-text) uppercase">What changed</h3>
      <ul className="flex flex-col gap-2">
        {changes.map((change, i) => (
          <li key={i} className="flex items-start gap-2 text-sm">
            <Plus className="mt-0.5 size-3.5 shrink-0 text-(--accent-text)" strokeWidth={2.5} />
            <div className="text-(--text)">
              {change.summary}
              {change.note && <span className="mt-0.5 block text-xs text-(--text-soft) italic">{change.note}</span>}
              {onSelectChange && (
                <button
                  type="button"
                  onClick={() => onSelectChange(change.nodeId)}
                  className="mt-1 block text-xs font-medium text-(--accent-text) hover:underline"
                >
                  Locate in trace →
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
