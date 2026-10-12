import { ConfidenceBadge } from "@/components/evidence/ConfidenceBadge";
import { classifyStructure } from "@/lib/architectureModel";
import { ROLE_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { ArchitectureComponent } from "@/api/types";

/** Non-visual alternative to the architecture diagram — same data, screen-
 * reader and keyboard friendly, for users who prefer structured browsing
 * over the hierarchical map. */
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
      {components.map((c) => {
        const supporting = classifyStructure(c) === "supporting";
        return (
          <li key={c.id}>
            <button
              onClick={() => onSelect(c.id)}
              aria-current={selectedId === c.id ? "true" : undefined}
              className={cn(
                "flex w-full items-center gap-3 rounded-md border px-3.5 py-2.5 text-left transition-colors",
                selectedId === c.id
                  ? "border-(--accent)/50 bg-(--accent-soft)"
                  : "border-(--border) bg-(--bg-raised) hover:border-(--accent)/30",
                supporting && "opacity-70",
              )}
            >
              <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                {ROLE_LABELS[c.role] ?? c.role}
              </span>
              {supporting && (
                <span className="rounded border border-(--border) px-1.5 py-0.5 font-mono text-[0.6rem] tracking-wide text-(--text-faint) uppercase">
                  Supporting
                </span>
              )}
              <code className="min-w-0 flex-1 truncate text-sm text-(--text)">{c.name}</code>
              <span className="hidden shrink-0 text-xs text-(--text-faint) sm:inline">
                {c.file_count} file{c.file_count === 1 ? "" : "s"} · {c.symbol_count} symbol
                {c.symbol_count === 1 ? "" : "s"}
                {c.third_party_dependencies.length > 0 ? ` · ${c.third_party_dependencies.length} deps` : ""}
              </span>
              <ConfidenceBadge label={c.confidence_label} />
            </button>
          </li>
        );
      })}
    </ul>
  );
}
