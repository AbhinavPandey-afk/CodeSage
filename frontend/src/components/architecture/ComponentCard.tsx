import { ConfidenceBadge } from "@/components/evidence/ConfidenceBadge";
import type { ArchitectureComponent } from "@/api/types";
import { cn } from "@/lib/utils";
import { roleColorVar, roleIcon } from "./roleStyle";

/** The diagram's component node — an architectural abstraction, not a bare
 * folder listing: leads with the component's role/responsibility, keeps the
 * literal directory path as secondary detail. */
export function ComponentCard({
  component,
  selected,
  faded,
  onSelect,
  dim = false,
}: {
  component: ArchitectureComponent;
  selected: boolean;
  faded: boolean;
  onSelect: () => void;
  /** Supporting-structure styling — present but visually de-emphasized. */
  dim?: boolean;
}) {
  const Icon = roleIcon(component.role);
  const roleVar = roleColorVar(component.role);

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      style={{ borderColor: selected ? `var(${roleVar})` : undefined }}
      className={cn(
        "flex w-56 shrink-0 flex-col gap-1.5 rounded-lg border bg-(--bg-raised) px-3.5 py-3 text-left shadow-sm transition-all hover:shadow-md",
        "focus-visible:ring-2 focus-visible:ring-(--accent) focus-visible:ring-offset-2 focus-visible:ring-offset-(--bg-inset) focus-visible:outline-none",
        selected ? "border-2 ring-2 ring-(--accent)/25" : "border-(--border)",
        faded && "opacity-25",
        dim && "opacity-70",
      )}
    >
      <div className="flex items-center gap-1.5">
        <span
          className="flex size-5 shrink-0 items-center justify-center rounded"
          style={{ backgroundColor: `color-mix(in oklab, var(${roleVar}) 16%, transparent)`, color: `var(${roleVar})` }}
        >
          <Icon className="size-3.5" strokeWidth={2.25} />
        </span>
        <ConfidenceBadge label={component.confidence_label} className="ml-auto" />
      </div>

      <p className="truncate text-sm font-medium text-(--text)" title={component.name}>
        {component.name}
      </p>
      <p className="truncate font-mono text-[0.65rem] text-(--text-faint)">{component.id}</p>

      <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[0.65rem] text-(--text-faint)">
        <span>
          {component.file_count} file{component.file_count === 1 ? "" : "s"}
        </span>
        <span>·</span>
        <span>
          {component.symbol_count} symbol{component.symbol_count === 1 ? "" : "s"}
        </span>
        {component.third_party_dependencies.length > 0 && (
          <>
            <span>·</span>
            <span>{component.third_party_dependencies.length} dependencies</span>
          </>
        )}
      </div>
    </button>
  );
}
