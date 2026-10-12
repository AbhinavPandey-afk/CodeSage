import { ArrowDown, Boxes, Database, Globe } from "lucide-react";
import type { ArchitectureComponent, ComponentRelationship } from "@/api/types";
import { EvidenceStatusBadge } from "@/components/flow/EvidenceStatusBadge";
import {
  classifyStructure,
  deriveLayerTransitions,
  type AggregatedDependency,
  type Layer,
} from "@/lib/architectureModel";
import { ConfidenceBadge } from "@/components/evidence/ConfidenceBadge";
import { confidenceLabel } from "@/lib/flowModel";
import { cn } from "@/lib/utils";
import { ComponentCard } from "./ComponentCard";
import { roleColorVar } from "./roleStyle";

/** The primary architecture visualization: SYSTEM -> Layers -> Components,
 * a strict hierarchy rendered with plain flex layout (no force-directed
 * graph library) — every layer band is a real, role-derived grouping, not a
 * repeated folder-per-node dump of the raw dependency graph. */
export function ArchitectureDiagram({
  layers,
  components,
  relationships,
  selectedId,
  onSelect,
}: {
  layers: Layer[];
  components: ArchitectureComponent[];
  relationships: ComponentRelationship[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const componentById = new Map(components.map((c) => [c.id, c]));
  const transitions = deriveLayerTransitions(layers, relationships);
  const transitionByPair = new Map(transitions.map((t) => [`${t.sourceLayerId}->${t.targetLayerId}`, t.callCount]));

  const runtimeComponents = components.filter((c) => classifyStructure(c) === "runtime");
  const supportingComponents = components.filter((c) => classifyStructure(c) === "supporting");
  const unlayeredRuntime = runtimeComponents.filter((c) => !layers.some((l) => l.componentIds.includes(c.id)));

  return (
    <div className="flex flex-col items-center rounded-lg border border-(--border) bg-(--bg-inset) px-4 py-8 sm:px-8">
      <div className="mb-3 rounded-md border-2 border-(--border-strong) bg-(--bg-raised) px-4 py-1.5 text-center font-mono text-[0.68rem] font-semibold tracking-[0.15em] text-(--text-faint) uppercase">
        System
      </div>
      <ArrowDown className="mb-4 size-4 text-(--text-faint)" />

      <div className="flex w-full max-w-4xl flex-col items-stretch gap-0">
        {layers.map((layer, i) => {
          const memberComponents = layer.componentIds.map((id) => componentById.get(id)).filter((c): c is ArchitectureComponent => !!c);
          const roleVar = roleColorVar(layer.role);
          const outgoing = layers
            .map((next) => ({ next, count: transitionByPair.get(`${layer.id}->${next.id}`) }))
            .filter((x) => x.count && x.next.id !== layer.id);

          return (
            <div key={layer.id} className="flex flex-col items-center">
              <div
                className="w-full rounded-xl border-2 bg-(--bg-raised)/60 p-4"
                style={{ borderColor: `color-mix(in oklab, var(${roleVar}) 35%, var(--border))` }}
              >
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <span className="size-2.5 shrink-0 rounded-full" style={{ backgroundColor: `var(${roleVar})` }} />
                  <h3 className="font-display text-lg font-medium text-(--text)">{layer.name}</h3>
                  <EvidenceStatusBadge status="DERIVED" />
                  <ConfidenceBadge label={confidenceLabel(layer.confidence)} />
                  <span className="ml-auto font-mono text-[0.65rem] text-(--text-faint)">
                    {memberComponents.length} component{memberComponents.length === 1 ? "" : "s"}
                  </span>
                </div>
                <p className="mb-3 max-w-2xl text-xs text-(--text-faint)">{layer.purpose}</p>

                <div className="flex flex-wrap gap-3">
                  {memberComponents.map((c) => (
                    <ComponentCard key={c.id} component={c} selected={selectedId === c.id} faded={false} onSelect={() => onSelect(c.id)} />
                  ))}
                </div>
              </div>

              {i < layers.length - 1 && (
                <div className="flex flex-col items-center py-2">
                  <ArrowDown className="size-4 text-(--text-faint)" />
                  {outgoing.length > 0 && (
                    <span className="mt-0.5 font-mono text-[0.62rem] text-(--text-faint)">
                      {outgoing.map((o) => `${o.count} call${o.count === 1 ? "" : "s"} → ${o.next.name}`).join(" · ")}
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {unlayeredRuntime.length > 0 && (
        <div className="mt-4 w-full max-w-4xl">
          <p className="mb-2 text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
            Other runtime components (no dominant role signal)
          </p>
          <div className="flex flex-wrap gap-3">
            {unlayeredRuntime.map((c) => (
              <ComponentCard key={c.id} component={c} selected={selectedId === c.id} faded={false} onSelect={() => onSelect(c.id)} />
            ))}
          </div>
        </div>
      )}

      {supportingComponents.length > 0 && (
        <>
          <div className="my-6 flex w-full max-w-4xl items-center gap-3">
            <span className="h-px flex-1 border-t border-dashed border-(--border-strong)" />
            <span className="font-mono text-[0.62rem] font-semibold tracking-[0.15em] text-(--text-faint) uppercase">
              Supporting structure
            </span>
            <span className="h-px flex-1 border-t border-dashed border-(--border-strong)" />
          </div>
          <p className="mb-3 max-w-xl text-center text-xs text-(--text-faint)">
            Tests and development tooling — present in the repository, but not part of the running system.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            {supportingComponents.map((c) => (
              <ComponentCard key={c.id} component={c} selected={selectedId === c.id} faded={false} dim onSelect={() => onSelect(c.id)} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export function ExternalDependencyBoundary({ dependencies }: { dependencies: AggregatedDependency[] }) {
  if (dependencies.length === 0) return null;
  const byCategory = {
    database: dependencies.filter((d) => d.category === "database"),
    external_service: dependencies.filter((d) => d.category === "external_service"),
  };

  return (
    <div className="mt-6 rounded-lg border border-dashed border-(--border-strong) bg-(--bg-inset) p-4">
      <div className="mb-1 flex items-center gap-2">
        <Boxes className="size-3.5 text-(--text-faint)" />
        <h3 className="text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">Repository boundary — external dependencies</h3>
      </div>
      <p className="mb-3 text-xs text-(--text-faint)">
        Real package names imported across the codebase — distinct from the internal components above, which may only *integrate with* these,
        not be them. A name matching this repository's own package may appear here for self-referential imports (a known limitation of
        import-based detection).
      </p>
      <div className="flex flex-col gap-3">
        {byCategory.database.length > 0 && <DependencyRow icon={Database} label="Database clients" deps={byCategory.database} />}
        {byCategory.external_service.length > 0 && <DependencyRow icon={Globe} label="External services / libraries" deps={byCategory.external_service} />}
      </div>
    </div>
  );
}

function DependencyRow({ icon: Icon, label, deps }: { icon: typeof Database; label: string; deps: AggregatedDependency[] }) {
  return (
    <div>
      <p className="mb-1.5 flex items-center gap-1.5 text-[0.65rem] font-medium text-(--text-soft)">
        <Icon className="size-3 text-(--text-faint)" /> {label}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {deps.map((d) => (
          <span
            key={d.name}
            title={`Imported by ${d.usedBy.length} component${d.usedBy.length === 1 ? "" : "s"}: ${d.usedBy.join(", ")}`}
            className={cn(
              "rounded-full border px-2.5 py-1 font-mono text-xs",
              d.category === "database" ? "border-(--bronze)/40 text-(--bronze)" : "border-(--sage)/40 text-(--sage)",
            )}
          >
            {d.name}
          </span>
        ))}
      </div>
    </div>
  );
}
