import { AnimatePresence, motion } from "motion/react";
import { Network, History, Radar, Route, ScrollText, SearchCheck, X } from "lucide-react";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { ConfidenceBadge } from "@/components/evidence/ConfidenceBadge";
import { EvidenceStatusBadge } from "@/components/flow/EvidenceStatusBadge";
import { classifyStructure, type Layer } from "@/lib/architectureModel";
import { useInvestigation } from "@/lib/investigation";
import { ROLE_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { ArchitectureComponent, ComponentRelationship, Smell } from "@/api/types";

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

export function ComponentInspector({
  component,
  layer,
  nameById,
  relationships,
  findings,
  onClose,
}: {
  component: ArchitectureComponent | null;
  /** The layer this component belongs to, if it's part of a reconstructed layer (null for Supporting-structure components). */
  layer: Layer | null;
  nameById: Map<string, string>;
  relationships: ComponentRelationship[];
  findings: Smell[];
  onClose: () => void;
}) {
  const { navigate } = useInvestigation();
  const open = component !== null;

  const related = component
    ? relationships.filter((r) => r.source_id === component.id || r.target_id === component.id)
    : [];
  const structure = component ? classifyStructure(component) : "runtime";

  const explainQuestion = component
    ? `Why does "${component.name}" exist as a ${ROLE_LABELS[component.role] ?? component.role} component, and what evidence supports that classification?`
    : "";

  return (
    <AnimatePresence>
      {open && component && (
        <>
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-40 bg-black/30 lg:hidden"
            onClick={onClose}
          />
          <motion.aside
            key="drawer"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="fixed top-14 right-0 bottom-0 z-50 flex w-full max-w-sm flex-col border-l border-(--border) bg-(--bg-raised) shadow-xl lg:w-80 lg:max-w-none lg:shadow-none"
          >
            <div className="flex items-start justify-between gap-3 border-b border-(--border) px-4 py-3.5">
              <Breadcrumbs
                items={[
                  { label: "Architecture", onClick: onClose },
                  { label: component.name },
                ]}
              />
              <button
                onClick={onClose}
                aria-label="Close component inspector"
                className="shrink-0 rounded text-(--text-faint) hover:text-(--text)"
              >
                <X className="size-4" />
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <EvidenceStatusBadge status="DERIVED" />
                <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                  {ROLE_LABELS[component.role] ?? component.role}
                </span>
                {structure === "supporting" && (
                  <span className="rounded border border-(--border) px-1.5 py-0.5 font-mono text-[0.6rem] tracking-wide text-(--text-faint) uppercase">
                    Supporting
                  </span>
                )}
                <ConfidenceBadge label={component.confidence_label} />
              </div>

              {layer && (
                <div className="mb-4">
                  <p className="text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">Architectural layer</p>
                  <p className="text-sm text-(--text)">{layer.name}</p>
                  <p className="text-xs text-(--text-faint)">{layer.purpose}</p>
                </div>
              )}

              <div className="mb-5 flex gap-6">
                <div>
                  <strong className="font-mono text-lg text-(--text) tabular-nums">{component.file_count}</strong>
                  <span className="block text-[0.65rem] font-medium tracking-wide text-(--text-faint) uppercase">
                    Files
                  </span>
                </div>
                <div>
                  <strong className="font-mono text-lg text-(--text) tabular-nums">{component.symbol_count}</strong>
                  <span className="block text-[0.65rem] font-medium tracking-wide text-(--text-faint) uppercase">
                    Symbols
                  </span>
                </div>
                <div>
                  <strong className="font-mono text-lg text-(--text) tabular-nums">{related.length}</strong>
                  <span className="block text-[0.65rem] font-medium tracking-wide text-(--text-faint) uppercase">
                    Relationships
                  </span>
                </div>
              </div>

              {findings.length > 0 && (
                <div className="mb-5">
                  <h3 className="mb-2 text-[0.68rem] font-semibold tracking-wide text-(--bad) uppercase">
                    Structural findings ({findings.length})
                  </h3>
                  <ul className="flex flex-col gap-1.5">
                    {findings.slice(0, 4).map((f, i) => (
                      <li key={i} className="flex items-start gap-2 text-xs text-(--text-soft)">
                        <span
                          className={cn(
                            "mt-1 size-1.5 shrink-0 rounded-full",
                            f.severity === "HIGH" && "bg-(--bad)",
                            f.severity === "MEDIUM" && "bg-(--warn)",
                            f.severity === "LOW" && "bg-(--text-faint)",
                          )}
                        />
                        {f.title}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="mb-5">
                <h3 className="mb-2 text-[0.68rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                  Why is this a component?
                </h3>
                <ul className="flex flex-col gap-1">
                  {component.evidence.map((e, i) => (
                    <li key={i} className="text-xs text-(--text-soft)">
                      · {e}
                    </li>
                  ))}
                </ul>
              </div>

              {component.third_party_dependencies.length > 0 && (
                <div className="mb-5">
                  <h3 className="mb-2 text-[0.68rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                    Third-party dependencies ({component.third_party_dependencies.length})
                  </h3>
                  <div className="flex flex-wrap gap-1.5">
                    {component.third_party_dependencies.map((d) => (
                      <span
                        key={d.name}
                        className={cn(
                          "rounded-full border px-2 py-0.5 font-mono text-xs",
                          d.category === "database" ? "border-(--bronze)/40 text-(--bronze)" : "border-(--sage)/40 text-(--sage)",
                        )}
                      >
                        {d.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {related.length > 0 && (
                <div className="mb-5">
                  <h3 className="mb-2 text-[0.68rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                    Related components
                  </h3>
                  <ul className="flex flex-col gap-1.5">
                    {related.slice(0, 8).map((r, i) => {
                      const otherId = r.source_id === component.id ? r.target_id : r.source_id;
                      const direction = r.source_id === component.id ? "→" : "←";
                      return (
                        <li key={i} className="flex items-center gap-1.5 text-xs">
                          <span className="text-(--text-faint)">{direction}</span>
                          <code className="min-w-0 flex-1 truncate text-(--text)">
                            {nameById.get(otherId) ?? otherId}
                          </code>
                          <span className="shrink-0 font-mono text-(--text-faint)">{r.call_count}</span>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}

              <div>
                <h3 className="mb-2 text-[0.68rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                  Files ({component.files.length})
                </h3>
                <ul className="flex flex-col gap-1 font-mono text-xs text-(--text-faint)">
                  {component.files.slice(0, 10).map((f) => (
                    <li key={f} className="truncate">
                      {f}
                    </li>
                  ))}
                  {component.files.length > 10 && <li>…and {component.files.length - 10} more</li>}
                </ul>
              </div>
            </div>

            <div className="flex flex-wrap gap-1.5 border-t border-(--border) px-4 py-3">
              <ActionButton icon={Network} label="Explore Evidence" onClick={() => navigate("graph", { componentId: component.id })} />
              <ActionButton icon={SearchCheck} label="Analyze" onClick={() => navigate("smells", { componentId: component.id })} />
              <ActionButton icon={Radar} label="View Impact" onClick={() => navigate("impact", { componentId: component.id })} />
              <ActionButton icon={Route} label="Trace Flow" onClick={() => navigate("flow", { componentId: component.id })} />
              <ActionButton icon={History} label="History" onClick={() => navigate("history", { componentId: component.id })} />
              <ActionButton icon={ScrollText} label="Ask" onClick={() => navigate("ask", { presetQuestion: explainQuestion })} />
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
