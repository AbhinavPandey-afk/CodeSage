import { X } from "lucide-react";
import type { GraphNode } from "@/api/types";

/** Evidence-style detail panel for a selected graph node — file/lines/symbol
 * laid out like a source citation, per the frontend-design skill's evidence
 * primitives (§17: FILE / LINES / SYMBOL / CONFIDENCE). */
export function NodeInspector({ node, onClose }: { node: GraphNode; onClose: () => void }) {
  return (
    <div className="absolute top-3 right-3 z-10 w-64 rounded-lg border border-(--border) bg-(--bg-raised) shadow-lg">
      <div className="flex items-start justify-between gap-2 border-b border-(--border) px-3.5 py-2.5">
        <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.62rem] font-semibold tracking-wide text-(--text-faint) uppercase">
          {node.symbol_type}
        </span>
        <button onClick={onClose} aria-label="Close" className="shrink-0 text-(--text-faint) hover:text-(--text)">
          <X className="size-3.5" />
        </button>
      </div>
      <div className="px-3.5 py-3">
        <code className="block text-sm break-words text-(--text)">{node.qualified_name}</code>

        <dl className="mt-3 flex flex-col gap-2">
          <div>
            <dt className="text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">File</dt>
            <dd className="font-mono text-xs break-all text-(--text-soft)">{node.file_path}</dd>
          </div>
          <div>
            <dt className="text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">Lines</dt>
            <dd className="font-mono text-xs text-(--text-soft)">
              {node.start_line}–{node.end_line}
            </dd>
          </div>
          <div>
            <dt className="text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">
              Connections
            </dt>
            <dd className="font-mono text-xs text-(--text-soft)">{node.degree}</dd>
          </div>
        </dl>

        <p className="mt-3 text-[0.7rem] text-(--text-faint) italic">
          Ctrl/Cmd-click a second node to investigate how they're connected.
        </p>
      </div>
    </div>
  );
}
