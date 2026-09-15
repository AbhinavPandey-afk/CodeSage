import { Network, Radar } from "lucide-react";
import { useInvestigation } from "@/lib/investigation";
import { cn } from "@/lib/utils";
import type { EvidenceItem } from "@/api/types";

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
      className="flex items-center gap-1.5 rounded-md border border-(--border) bg-(--bg) px-2.5 py-1.5 text-xs font-medium text-(--text-soft) transition-colors hover:border-(--accent)/40 hover:text-(--text)"
    >
      <Icon className="size-3.5" strokeWidth={2} />
      {label}
    </button>
  );
}

/** A source citation as a first-class UI object — the evidence behind an
 * answer should never be an afterthought under a wall of prose. */
export function EvidenceCitation({ evidence }: { evidence: EvidenceItem }) {
  const { navigate } = useInvestigation();

  return (
    <div className="rounded-lg border border-(--border) bg-(--bg-raised) p-4">
      <div className="mb-2.5 flex flex-wrap items-center gap-2">
        <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.62rem] font-semibold tracking-wide text-(--text-faint) uppercase">
          {evidence.symbol_type}
        </span>
        <code className="min-w-0 flex-1 truncate text-sm text-(--text)">{evidence.qualified_name}</code>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3">
        <div>
          <dt className="text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">File</dt>
          <dd className="truncate font-mono text-xs text-(--text-soft)">{evidence.file_path}</dd>
        </div>
        <div>
          <dt className="text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">Lines</dt>
          <dd className="font-mono text-xs text-(--text-soft)">
            {evidence.start_line}–{evidence.end_line}
          </dd>
        </div>
      </dl>

      {evidence.related.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1 border-t border-(--border) pt-2.5">
          {evidence.related.slice(0, 5).map((r, i) => (
            <li key={i} className="flex flex-wrap items-center gap-1.5 text-xs">
              <span
                className={cn(
                  "rounded px-1 py-0.5 font-mono text-[0.6rem] font-semibold tracking-wide uppercase",
                  "bg-(--bg-sunken) text-(--accent-text)",
                )}
              >
                {r.relationship_type}
              </span>
              <span className="text-(--text-faint)">{r.direction === "outgoing" ? "→" : "←"}</span>
              <code className="min-w-0 flex-1 truncate text-(--text-soft)">{r.qualified_name}</code>
              <span className="shrink-0 font-mono text-(--text-faint)">{Math.round(r.confidence * 100)}%</span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex flex-wrap gap-1.5 border-t border-(--border) pt-3">
        <ActionButton
          icon={Network}
          label="View Evidence"
          onClick={() => navigate("graph", { qualifiedName: evidence.qualified_name })}
        />
        <ActionButton
          icon={Radar}
          label="View Impact"
          onClick={() => navigate("impact", { qualifiedName: evidence.qualified_name })}
        />
      </div>
    </div>
  );
}
