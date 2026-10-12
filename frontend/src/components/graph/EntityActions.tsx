import { History, Layers3, Radar, Route, ScrollText, SearchCheck } from "lucide-react";
import { useInvestigation } from "@/lib/investigation";

/** Contextual navigation for one graph entity (PART 14) — every action
 * reuses an existing page's existing focus mechanism (ArchitecturePanel's
 * componentId, ImpactPanel's/ExecutionFlowPanel's qualifiedName, AskPanel's
 * presetQuestion); none of it is new page behavior. Historical Record has no
 * focus mechanism to reuse (confirmed in the read-only audit), so its
 * action only switches tabs — labeled plainly, not oversold. */
function ActionButton({
  icon: Icon,
  label,
  onClick,
}: {
  icon: typeof Route;
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

export function EntityActions({
  qualifiedName,
  componentId,
  findingsCount,
}: {
  qualifiedName: string;
  componentId: string | null;
  /** Findings whose evidence touches this entity's file — 0 hides the
   * Architecture Analysis action rather than linking to an empty search. */
  findingsCount: number;
}) {
  const { navigate } = useInvestigation();

  return (
    <div className="flex flex-wrap gap-1.5">
      {componentId && (
        <ActionButton
          icon={Layers3}
          label="Architecture"
          onClick={() => navigate("architecture", { componentId })}
        />
      )}
      <ActionButton
        icon={Route}
        label="Execution Flow"
        onClick={() => navigate("flow", { qualifiedName, componentId: componentId ?? undefined })}
      />
      <ActionButton icon={Radar} label="Impact & Risk" onClick={() => navigate("impact", { qualifiedName })} />
      {findingsCount > 0 && (
        <ActionButton
          icon={SearchCheck}
          label={`Findings (${findingsCount})`}
          onClick={() => navigate("smells")}
        />
      )}
      <ActionButton icon={History} label="History" onClick={() => navigate("history")} />
      <ActionButton
        icon={ScrollText}
        label="Ask"
        onClick={() =>
          navigate("ask", { presetQuestion: `What is \`${qualifiedName}\` and how does it fit into this codebase?` })
        }
      />
    </div>
  );
}
