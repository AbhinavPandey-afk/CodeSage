import { Compass, Layers, Play } from "lucide-react";
import { ROLE_LEGEND } from "@/components/architecture/ArchitectureMap";
import { ROLE_LABELS } from "@/lib/labels";

export function TraceLegend({ showProposed }: { showProposed: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-(--text-faint)">
      <span className="flex items-center gap-1.5">
        <Play className="size-3 text-(--ok)" strokeWidth={2.5} /> Entry point
      </span>
      {ROLE_LEGEND.map(({ role, color }) => (
        <span key={role} className="flex items-center gap-1.5">
          <span className="size-2 rounded-full" style={{ backgroundColor: color }} />
          {ROLE_LABELS[role]}
        </span>
      ))}
      <span className="flex items-center gap-1.5">
        <Layers className="size-3" /> Derived stage
      </span>
      {showProposed && (
        <span className="flex items-center gap-1.5">
          <Compass className="size-3 text-(--accent-text)" /> Proposed (design projection)
        </span>
      )}
    </div>
  );
}
