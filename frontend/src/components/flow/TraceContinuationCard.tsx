import { ArrowRight, Layers2 } from "lucide-react";
import type { TraceNode } from "@/lib/flowModel";

/** The inline marker Trace Scope leaves where it hid steps — a *display*
 * boundary ("continues elsewhere"), never phrased as if execution stopped.
 * Clicking it switches to Repository scope to reveal what's hidden. */
export function TraceContinuationCard({ node, onExpand }: { node: TraceNode; onExpand: () => void }) {
  return (
    <button
      type="button"
      onClick={onExpand}
      className="flex w-60 shrink-0 flex-col items-center gap-1.5 rounded-lg border border-dashed border-(--border-strong) bg-(--bg-sunken) px-3.5 py-3 text-center transition-colors hover:border-(--accent)/50 hover:bg-(--bg-inset) focus-visible:ring-2 focus-visible:ring-(--accent) focus-visible:outline-none"
    >
      <Layers2 className="size-4 text-(--text-faint)" strokeWidth={2} />
      <span className="text-xs font-semibold tracking-wide text-(--text-soft) uppercase">{node.name}</span>
      <span className="text-[0.68rem] text-(--text-faint)">{node.note}</span>
      <span className="flex items-center gap-1 text-[0.68rem] font-medium text-(--accent-text)">
        Expand in Repository scope <ArrowRight className="size-3" />
      </span>
    </button>
  );
}
