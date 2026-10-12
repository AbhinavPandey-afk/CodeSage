import { AnimatePresence, motion } from "motion/react";
import { ArrowDown, ArrowRight, Layers3, Network, Radar, Wrench, X } from "lucide-react";
import type { ArchitectureComponent, EvidenceRelationship, Smell } from "@/api/types";
import { FindingConfidenceMeter } from "@/components/analysis/FindingCard";
import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { confidenceTier, findingActionTargets, splitObservedInterpretation } from "@/lib/analysisModel";
import {
  CONTEXT_FLAG_DESCRIPTIONS,
  CONTEXT_FLAG_LABELS,
  DETECTION_BASIS_FLAGS,
  SMELL_TYPE_LABELS,
} from "@/lib/labels";
import { useInvestigation } from "@/lib/investigation";
import { cn } from "@/lib/utils";

const SEVERITY_STYLE = {
  HIGH: "bg-(--bad)/14 text-(--bad)",
  MEDIUM: "bg-(--warn)/14 text-(--warn)",
  LOW: "bg-(--bg-sunken) text-(--text-faint)",
} as const;

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-1.5 text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">{children}</h3>
  );
}

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
      className="flex items-center gap-1.5 rounded-md border border-(--border) bg-(--bg-raised) px-2.5 py-1.5 text-xs font-medium text-(--text-soft) transition-colors hover:border-(--accent)/40 hover:text-(--text)"
    >
      <Icon className="size-3.5" strokeWidth={2} />
      {label}
    </button>
  );
}

function RelationshipRow({ detail }: { detail: EvidenceRelationship }) {
  return (
    <div className="rounded-md border border-(--border) bg-(--bg) px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        <code className="min-w-0 truncate text-(--text)">{detail.source}</code>
        <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.6rem] font-semibold tracking-wide text-(--accent-text) uppercase">
          {detail.relationship_type}
        </span>
        <code className="min-w-0 truncate text-(--text)">{detail.target}</code>
      </div>
      <div className="mt-1 flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <span className="font-mono text-[0.65rem] text-(--text-faint)">
          {detail.source_file ? `${detail.source_file}${detail.source_line ? `:${detail.source_line}` : ""}` : "location unknown"}
        </span>
        {detail.resolver_confidence !== null && (
          <span className="font-mono text-[0.65rem] text-(--text-faint)">
            resolver confidence {Math.round(detail.resolver_confidence * 100)}%
          </span>
        )}
      </div>
      {(detail.source_role || detail.target_role) && (
        <p className="mt-1 text-[0.65rem] text-(--text-faint)">
          {detail.source_role ?? "?"} → {detail.target_role ?? "?"}
        </p>
      )}
    </div>
  );
}

/** STATIC CALL GRAPH CYCLE (PART 24) — the explicit, ordered path the
 * backend's find_cycle_path() reconstructed, never an implied runtime
 * order. Node labels close back to the start to make the loop visually
 * obvious. */
function CycleChain({ details }: { details: EvidenceRelationship[] }) {
  const closingTarget = details[details.length - 1]?.target;
  return (
    <div>
      <p className="mb-1 text-[0.65rem] font-semibold tracking-wide text-(--accent-text) uppercase">
        Static call graph cycle
      </p>
      <p className="mb-2 text-xs text-(--text-faint)">
        A static fact about the resolved CALLS graph — not an observed runtime execution order.
      </p>
      <ol className="flex flex-col">
        {details.map((d, i) => (
          <li key={i}>
            <code className="block px-1.5 py-1 font-mono text-sm text-(--text)">{d.source}</code>
            <div className="ml-4 flex flex-col gap-0.5 border-l-2 border-(--border) py-1 pl-3.5">
              <div className="flex items-center gap-1.5">
                <ArrowDown className="size-3 text-(--text-faint)" />
                <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.6rem] font-semibold tracking-wide text-(--accent-text) uppercase">
                  {d.relationship_type}
                </span>
              </div>
              <span className="font-mono text-[0.65rem] text-(--text-faint)">
                {d.source_file ? `${d.source_file}${d.source_line ? `:${d.source_line}` : ""}` : "location unknown"}
                {d.resolver_confidence !== null ? ` · ${Math.round(d.resolver_confidence * 100)}% confidence` : ""}
              </span>
            </div>
          </li>
        ))}
        {closingTarget && (
          <li>
            <code className="block px-1.5 py-1 font-mono text-sm text-(--text)">
              {closingTarget} <span className="text-(--text-faint) italic">(closes the cycle)</span>
            </code>
          </li>
        )}
      </ol>
    </div>
  );
}

export function FindingInspector({
  smell,
  allFindingsById,
  components,
  onClose,
  onSelectFinding,
}: {
  /** Null closes the drawer — same open/close contract as
   * architecture/ComponentInspector.tsx, so this file owns its own
   * AnimatePresence rather than the parent guessing visibility. */
  smell: Smell | null;
  allFindingsById: Map<string, Smell>;
  components: ArchitectureComponent[];
  onClose: () => void;
  onSelectFinding: (id: string) => void;
}) {
  const { navigate } = useInvestigation();
  const open = smell !== null;

  const { observed, interpretation } = open
    ? splitObservedInterpretation(smell.explanation)
    : { observed: "", interpretation: null };
  const targets = open ? findingActionTargets(smell, components) : null;
  const basisFlags = open ? smell.context_flags.filter((f) => DETECTION_BASIS_FLAGS.has(f)) : [];
  const otherFlags = open ? smell.context_flags.filter((f) => !DETECTION_BASIS_FLAGS.has(f)) : [];
  const relatedFindings = open
    ? smell.related_finding_ids.map((id) => allFindingsById.get(id)).filter((s): s is Smell => s !== undefined)
    : [];
  const isCycle = open && smell.smell_type === "circular_dependency" && smell.evidence_details.length > 0;

  return (
    <AnimatePresence>
      {open && smell && targets && (
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
            className="fixed top-14 right-0 bottom-0 z-50 flex w-full max-w-sm flex-col border-l border-(--border) bg-(--bg-raised) shadow-xl lg:w-96 lg:max-w-none lg:shadow-none"
          >
            <div className="flex shrink-0 items-start justify-between gap-3 border-b border-(--border) px-4 py-3.5">
              <Breadcrumbs items={[{ label: "Architecture Analysis", onClick: onClose }, { label: smell.title }]} />
              <button
                onClick={onClose}
                aria-label="Close finding details"
                className="shrink-0 rounded text-(--text-faint) hover:text-(--text)"
              >
                <X className="size-4" />
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.62rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                  {SMELL_TYPE_LABELS[smell.smell_type] ?? smell.smell_type}
                </span>
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 font-mono text-[0.65rem] font-bold tracking-wide",
                    SEVERITY_STYLE[smell.severity],
                  )}
                >
                  {smell.severity}
                </span>
                <FindingConfidenceMeter confidence={smell.confidence} />
              </div>
              <p className="text-sm font-medium text-(--text)">{smell.title}</p>

              <div className="mt-3">
                <SectionHeading>Observed condition</SectionHeading>
                <p className="text-sm leading-relaxed text-(--text-soft)">{observed}</p>
              </div>

              {interpretation && (
                <div className="mt-3">
                  <SectionHeading>Interpreted as</SectionHeading>
                  <p className="text-sm leading-relaxed text-(--text-soft)">{interpretation}</p>
                </div>
              )}

              <div className="mt-3">
                <SectionHeading>Finding confidence</SectionHeading>
                <div className="flex items-center gap-2">
                  <FindingConfidenceMeter confidence={smell.confidence} />
                  <span className="font-mono text-xs text-(--text-faint)">
                    {confidenceTier(smell.confidence)} · {Math.round(smell.confidence * 100)}%
                  </span>
                </div>
                <p className="mt-1 text-xs text-(--text-faint)">
                  How strongly the available evidence supports interpreting this condition as an architectural
                  issue — not a probability that the finding is "true."
                </p>
              </div>

              {basisFlags.length > 0 && (
                <div className="mt-3">
                  <SectionHeading>Detection basis</SectionHeading>
                  <div className="flex flex-wrap gap-1.5">
                    {basisFlags.map((flag) => (
                      <span
                        key={flag}
                        title={CONTEXT_FLAG_DESCRIPTIONS[flag]}
                        className="rounded-full border border-(--border) bg-(--bg-sunken) px-2 py-0.5 text-[0.65rem] font-medium text-(--text-soft)"
                      >
                        {CONTEXT_FLAG_LABELS[flag]}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {otherFlags.length > 0 && (
                <div className="mt-3 border-t border-(--border) pt-3">
                  <SectionHeading>Context</SectionHeading>
                  <ul className="flex flex-col gap-1.5">
                    {otherFlags.map((flag) => (
                      <li key={flag} className="text-xs text-(--text-soft)">
                        <span className="font-semibold text-(--text)">{CONTEXT_FLAG_LABELS[flag]}</span> —{" "}
                        {CONTEXT_FLAG_DESCRIPTIONS[flag]}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="mt-3 border-t border-(--border) pt-3">
                <SectionHeading>Evidence</SectionHeading>
                {isCycle ? (
                  <CycleChain details={smell.evidence_details} />
                ) : smell.evidence_details.length > 0 ? (
                  <div className="flex flex-col gap-2">
                    {smell.evidence_details.map((d, i) => (
                      <RelationshipRow key={i} detail={d} />
                    ))}
                  </div>
                ) : (
                  <>
                    <p className="mb-2 font-mono text-xs text-(--text-soft)">{smell.evidence}</p>
                    {smell.affected.length > 0 && (
                      <ul className="flex flex-col gap-0.5">
                        {smell.affected.map((a, i) => (
                          <li key={i} className="font-mono text-xs text-(--text-faint)">
                            <code className="text-(--text-soft)">{a.qualified_name}</code> — {a.file_path}:
                            {a.start_line}
                          </li>
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </div>

              {relatedFindings.length > 0 && (
                <div className="mt-3 border-t border-(--border) pt-3">
                  <SectionHeading>Related findings — same root entity</SectionHeading>
                  <ul className="flex flex-col gap-1">
                    {relatedFindings.map((r) => (
                      <li key={r.id}>
                        <button
                          onClick={() => onSelectFinding(r.id)}
                          className="flex w-full items-center gap-1.5 rounded px-1.5 py-1 text-left text-xs hover:bg-(--bg-sunken)"
                        >
                          <span className="rounded bg-(--bg-sunken) px-1 py-0.5 font-mono text-[0.6rem] text-(--text-faint) uppercase">
                            {SMELL_TYPE_LABELS[r.smell_type] ?? r.smell_type}
                          </span>
                          <span className="min-w-0 flex-1 truncate text-(--text-soft)">{r.title}</span>
                          <ArrowRight className="size-3 shrink-0 text-(--text-faint)" />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="mt-3 border-t border-(--border) pt-3">
                <SectionHeading>Restoration / optimization</SectionHeading>
                {smell.optimization_supported ? (
                  <ActionButton icon={Wrench} label="Review optimization" onClick={() => navigate("optimization")} />
                ) : (
                  <p className="text-xs text-(--text-faint)">
                    No deterministic restoration proposal is currently generated for this finding type.
                  </p>
                )}
              </div>

              <div className="mt-3 border-t border-(--border) pt-3">
                <SectionHeading>Actions</SectionHeading>
                <div className="flex flex-wrap gap-1.5">
                  {targets.architectureComponentId && (
                    <ActionButton
                      icon={Layers3}
                      label="Show on Architecture"
                      onClick={() => navigate("architecture", { componentId: targets.architectureComponentId! })}
                    />
                  )}
                  {(targets.evidenceQualifiedName || targets.evidenceComponentId) && (
                    <ActionButton
                      icon={Network}
                      label="View Evidence"
                      onClick={() =>
                        navigate(
                          "graph",
                          targets.evidenceQualifiedName
                            ? { qualifiedName: targets.evidenceQualifiedName }
                            : { componentId: targets.evidenceComponentId! },
                        )
                      }
                    />
                  )}
                  {targets.impactQualifiedName && (
                    <ActionButton
                      icon={Radar}
                      label="View Impact"
                      onClick={() => navigate("impact", { qualifiedName: targets.impactQualifiedName! })}
                    />
                  )}
                </div>
              </div>

              <p
                className="mt-3 border-t border-(--border) pt-3 font-mono text-[0.6rem] text-(--text-faint)"
                title="Stable finding identifier"
              >
                {smell.id}
              </p>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
