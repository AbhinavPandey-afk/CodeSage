import { AnimatePresence, motion } from "motion/react";
import { Hammer, Layers3, Network, Radar, ScrollText, X } from "lucide-react";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { ConfidenceBadge } from "@/components/evidence/ConfidenceBadge";
import { FlowLabelBadge } from "@/components/evidence/FlowLabelBadge";
import { confidenceLabel, type TraceNode } from "@/lib/flowModel";
import { useInvestigation } from "@/lib/investigation";
import { ROLE_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";

function ActionButton({ icon: Icon, label, onClick }: { icon: typeof Network; label: string; onClick: () => void }) {
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

function whatItDoes(node: TraceNode): string {
  if (node.kind === "entry") return "Entry point into the system — the reconstructed operation begins here.";
  if (node.kind === "proposed") return node.note ?? "A proposed design step, not part of the current implementation.";
  if (node.terminalKind === "database")
    return "Reaches a data-access component; the reconstructed trace stops here because this is a recognized persistence boundary.";
  if (node.terminalKind === "external_service")
    return "Reaches an external-integration component; the reconstructed trace stops here because this is a recognized external-service boundary.";
  if (node.kind === "derived") {
    const label = node.componentName ?? (node.componentRole ? ROLE_LABELS[node.componentRole] : "this stage");
    return `Represents ${node.collapsedCount} resolved call${node.collapsedCount === 1 ? "" : "s"} within ${label}.`;
  }
  return `Called from ${node.callerQualifiedName || "the entry point"}.`;
}

function whyItMatters(node: TraceNode): string {
  if (node.kind === "entry") return "This is where an external request enters the reconstructed system.";
  if (node.kind === "proposed") return "Introducing this step is intended to enforce a cleaner architectural boundary — see Optimization for the full rationale.";
  if (node.terminalKind === "database") return "Data-access steps are where the system reads or writes persistent state.";
  if (node.terminalKind === "external_service") return "External-integration steps hand control to a system outside this repository.";
  switch (node.componentRole) {
    case "api":
      return "Part of the API layer that receives and routes the request.";
    case "service":
      return "Service-layer steps typically coordinate business logic between the API and data access.";
    case "data_access":
      return "Data-access steps are where the system reads or writes persistent state.";
    case "external_integration":
      return "External-integration steps hand control to a system outside this repository.";
    default:
      return "This step's architectural role could not be confidently classified from repository evidence.";
  }
}

export function TraceInspector({
  node,
  entryLabel,
  onClose,
}: {
  node: TraceNode | null;
  entryLabel: string;
  onClose: () => void;
}) {
  const { navigate } = useInvestigation();
  const open = node !== null;
  const canLinkToSymbol = node !== null && node.kind !== "proposed";

  const explainQuestion = node
    ? node.kind === "proposed"
      ? `In the execution flow starting at ${entryLabel}, why does Architecture Optimization recommend introducing ${node.name}?`
      : `In the execution flow starting at ${entryLabel}, why does it reach ${node.name} (${node.qualifiedName})?`
    : "";

  return (
    <AnimatePresence>
      {open && node && (
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
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="fixed inset-x-0 bottom-0 z-50 flex max-h-[80vh] flex-col rounded-t-xl border-t border-(--border) bg-(--bg-raised) shadow-xl lg:sticky lg:top-[4.5rem] lg:inset-x-auto lg:max-h-[calc(100vh-6rem)] lg:w-[22rem] lg:rounded-lg lg:border"
          >
            <div className="flex items-start justify-between gap-3 border-b border-(--border) px-4 py-3.5">
              <Breadcrumbs items={[{ label: "Trace", onClick: onClose }, { label: node.name }]} />
              <button onClick={onClose} aria-label="Close inspector" className="shrink-0 rounded text-(--text-faint) hover:text-(--text)">
                <X className="size-4" />
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <FlowLabelBadge label={node.label} />
                {node.componentRole && (
                  <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                    {ROLE_LABELS[node.componentRole]}
                  </span>
                )}
                {node.kind !== "proposed" && <ConfidenceBadge label={confidenceLabel(node.confidence)} />}
              </div>

              <code className="mb-5 block text-sm break-words text-(--text)">{node.qualifiedName}</code>

              <div className="mb-5">
                <h3 className="mb-1.5 text-[0.65rem] font-semibold tracking-wide text-(--accent-text) uppercase">What it does</h3>
                <p className="text-sm leading-relaxed text-(--text-soft)">{whatItDoes(node)}</p>
              </div>

              <div className="mb-5">
                <h3 className="mb-1.5 text-[0.65rem] font-semibold tracking-wide text-(--accent-text) uppercase">Why it matters</h3>
                <p className="text-sm leading-relaxed text-(--text-soft)">{whyItMatters(node)}</p>
                <p className="mt-1.5 text-[0.65rem] text-(--text-faint) italic">Interpretation, not a repository fact.</p>
              </div>

              <div className="mb-5 rounded-md border border-(--border) bg-(--bg) p-3">
                <h3 className="mb-2 text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">Evidence</h3>
                <dl className="flex flex-col gap-2">
                  <div>
                    <dt className="text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">Where it lives</dt>
                    <dd className="font-mono text-xs break-all text-(--text-soft)">{node.filePath ?? "Not resolved for this step."}</dd>
                  </div>
                  {node.kind !== "entry" && node.kind !== "proposed" && (
                    <div>
                      <dt className="text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">Call-site evidence</dt>
                      <dd className="font-mono text-xs break-all text-(--text-soft)">
                        {node.relationshipType}
                        {node.sourceFile ? ` — ${node.sourceFile}${node.sourceLine ? `:${node.sourceLine}` : ""}` : ""}
                      </dd>
                    </div>
                  )}
                  <div>
                    <dt className="text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">What calls it</dt>
                    <dd className="truncate font-mono text-xs text-(--text-soft)">
                      {node.callerQualifiedName || "External client (incoming request)"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                      What it calls ({node.children.length})
                    </dt>
                    {node.children.length === 0 ? (
                      <dd className="text-xs text-(--text-faint)">Nothing further was resolved from here.</dd>
                    ) : (
                      <dd className="flex flex-col gap-0.5">
                        {node.children.slice(0, 6).map((c) => (
                          <code key={c.id} className="truncate text-xs text-(--text-soft)">
                            {c.name}
                          </code>
                        ))}
                      </dd>
                    )}
                  </div>
                </dl>
              </div>

              {node.note && (
                <p className={cn("mb-5 rounded-md border px-3 py-2 text-xs italic", "border-(--accent)/25 bg-(--accent-soft) text-(--accent-text)")}>
                  {node.note}
                </p>
              )}
            </div>

            <div className="flex flex-wrap gap-1.5 border-t border-(--border) px-4 py-3">
              {canLinkToSymbol && (
                <ActionButton icon={Network} label="View Evidence" onClick={() => navigate("graph", { qualifiedName: node.qualifiedName })} />
              )}
              {node.componentId && (
                <ActionButton icon={Layers3} label="Show Architecture" onClick={() => navigate("architecture", { componentId: node.componentId! })} />
              )}
              {node.kind === "proposed" && (
                <ActionButton icon={Hammer} label="View Optimization" onClick={() => navigate("optimization")} />
              )}
              {canLinkToSymbol && (
                <ActionButton icon={Radar} label="Analyze Impact" onClick={() => navigate("impact", { qualifiedName: node.qualifiedName })} />
              )}
              <ActionButton icon={ScrollText} label="Explain" onClick={() => navigate("ask", { presetQuestion: explainQuestion })} />
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
