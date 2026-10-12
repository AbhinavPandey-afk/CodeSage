import { ArrowRight, X } from "lucide-react";
import type { GraphNode } from "@/api/types";

/** Makes EXPLORE vs INVESTIGATE (PART 2) a visible fact instead of something
 * the user has to remember from a caption — this is the discoverable
 * alternative to relying solely on the Ctrl/Cmd-click hint (PART 17). */
function NodeChip({ label, node }: { label: string; node: GraphNode }) {
  return (
    <span className="flex items-center gap-1.5 rounded-md border border-(--border) bg-(--bg-raised) px-2.5 py-1.5">
      <span className="font-mono text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">
        {label}
      </span>
      <code className="max-w-40 truncate text-xs text-(--text)">{node.name}</code>
    </span>
  );
}

export function SelectionStateBar({
  primary,
  secondary,
  investigating,
  onClear,
}: {
  primary: GraphNode | null;
  secondary: GraphNode | null;
  /** True once a comparison has been requested (loading, resolved, or errored) —
   * distinct from `secondary` alone so the bar reads correctly mid-request. */
  investigating: boolean;
  onClear: () => void;
}) {
  if (!primary) {
    return (
      <p className="mb-3 text-xs text-(--text-faint) italic">
        Select a node to inspect it, or use search to jump to one.
      </p>
    );
  }

  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <NodeChip label={investigating ? "Source" : "Node A"} node={primary} />
      {secondary ? (
        <>
          <ArrowRight className="size-3.5 shrink-0 text-(--text-faint)" />
          <NodeChip label="Target" node={secondary} />
          <span className="rounded-full border border-(--accent)/30 bg-(--accent-soft) px-2.5 py-1 font-mono text-[0.6rem] font-semibold tracking-wide text-(--accent-text) uppercase">
            Investigating relationship
          </span>
          <button
            onClick={onClear}
            aria-label="Exit relationship investigation"
            className="flex items-center gap-1 rounded-md px-1.5 py-1 text-xs text-(--text-faint) hover:text-(--text)"
          >
            <X className="size-3.5" />
          </button>
        </>
      ) : (
        <span className="text-xs text-(--text-faint)">
          + Ctrl/Cmd-click a second node, or use search, to investigate the relationship
        </span>
      )}
    </div>
  );
}
