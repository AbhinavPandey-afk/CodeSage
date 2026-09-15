import { ConfidenceBadge } from "@/components/evidence/ConfidenceBadge";
import { ROLE_LABELS } from "@/lib/labels";
import type { ArchitectureComponent } from "@/api/types";

/** Non-visual alternative to the architecture map — same data, screen-reader
 * and keyboard friendly (frontend-design skill §68: the graph must have an
 * accessible inspector alternative). */
export function ArchitectureList({
  components,
  selectedId,
  onSelect,
}: {
  components: ArchitectureComponent[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <ul className="flex flex-col gap-1.5">
      {components.map((c) => (
        <li key={c.id}>
          <button
            onClick={() => onSelect(c.id)}
            aria-current={selectedId === c.id ? "true" : undefined}
            className={`flex w-full items-center gap-3 rounded-md border px-3.5 py-2.5 text-left transition-colors ${
              selectedId === c.id
                ? "border-(--accent)/50 bg-(--accent-soft)"
                : "border-(--border) bg-(--bg-raised) hover:border-(--accent)/30"
            }`}
          >
            <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
              {ROLE_LABELS[c.role] ?? c.role}
            </span>
            <code className="min-w-0 flex-1 truncate text-sm text-(--text)">{c.name}</code>
            <span className="hidden shrink-0 text-xs text-(--text-faint) sm:inline">
              {c.file_count} file{c.file_count === 1 ? "" : "s"} · {c.symbol_count} symbol
              {c.symbol_count === 1 ? "" : "s"}
            </span>
            <ConfidenceBadge label={c.confidence_label} />
          </button>
        </li>
      ))}
    </ul>
  );
}
