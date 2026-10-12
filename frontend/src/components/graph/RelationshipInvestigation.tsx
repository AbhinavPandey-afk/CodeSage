import { ArrowDown, GitBranch, ScrollText, Sparkles, X } from "lucide-react";
import type { ArchitectureComponent, RelationshipResponse, RelationshipStep, Smell } from "@/api/types";
import { EntityActions } from "@/components/graph/EntityActions";
import { componentForFile, evidenceLedger, findingsForFile, pathChain, weakestLinkConfidence } from "@/lib/evidenceExplorer";
import { useInvestigation } from "@/lib/investigation";
import { cn } from "@/lib/utils";

function ConfidenceMeter({ value }: { value: number | null }) {
  if (value === null) return <span className="font-mono text-[0.65rem] text-(--text-faint)">confidence n/a</span>;
  return (
    <span className="inline-flex items-center gap-1 font-mono text-[0.65rem] text-(--text-faint)">
      <span className="h-1 w-8 overflow-hidden rounded-full bg-(--bg-sunken)">
        <span className="block h-full bg-(--accent)" style={{ width: `${Math.round(value * 100)}%` }} />
      </span>
      {Math.round(value * 100)}%
    </span>
  );
}

/** file:line + confidence for one hop's real evidence (PART 11) — never a
 * source excerpt, only the citation the backend actually returned. */
function StepEvidence({ step }: { step: RelationshipStep }) {
  return (
    <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
      <span className="font-mono text-[0.65rem] text-(--text-faint)">
        {step.source_file ? `${step.source_file}${step.source_line ? `:${step.source_line}` : ""}` : "location unknown"}
      </span>
      <ConfidenceMeter value={step.confidence} />
    </div>
  );
}

function EntityIdentityCard({
  label,
  qualifiedName,
  symbolType,
  filePath,
}: {
  label: string;
  qualifiedName: string;
  symbolType: string;
  filePath: string;
}) {
  return (
    <div className="min-w-0 flex-1 rounded-md border border-(--border) bg-(--bg) px-3 py-2.5">
      <span className="font-mono text-[0.6rem] font-semibold tracking-wide text-(--accent-text) uppercase">
        {label}
      </span>
      <code className="mt-0.5 block truncate text-sm text-(--text)" title={qualifiedName}>
        {qualifiedName}
      </code>
      <div className="mt-1 flex flex-wrap items-center gap-1.5">
        <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">
          {symbolType}
        </span>
        <span className="truncate font-mono text-[0.65rem] text-(--text-faint)">{filePath}</span>
      </div>
    </div>
  );
}

function RelatedFindingsList({ label, findings }: { label: string; findings: Smell[] }) {
  const { navigate } = useInvestigation();
  if (findings.length === 0) return null;
  return (
    <div>
      <p className="mb-1 text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">
        {label} ({findings.length})
      </p>
      <ul className="flex flex-col gap-0.5">
        {findings.slice(0, 3).map((s, i) => (
          <li key={i}>
            <button
              onClick={() => navigate("smells")}
              className="block w-full truncate rounded px-1.5 py-0.5 text-left text-xs text-(--text-soft) hover:bg-(--bg-sunken)"
            >
              <span className={s.severity === "HIGH" ? "text-(--bad)" : s.severity === "MEDIUM" ? "text-(--warn)" : "text-(--text-faint)"}>
                ●
              </span>{" "}
              {s.title}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function RelationshipInvestigation({
  relationship,
  components,
  smells,
  resolveUid,
  onFocusNode,
  onClose,
}: {
  relationship: RelationshipResponse;
  /** Reconstructed architecture components, for source/target action context
   * (PART 14) — omitted (empty array) is a valid, honest "not loaded yet". */
  components: ArchitectureComponent[];
  smells: Smell[];
  /** Resolves a path-hop's qualified name back to a graph UID, when that
   * entity is present in the currently loaded graph view (PART 9). */
  resolveUid: (qualifiedName: string) => string | null;
  onFocusNode: (uid: string) => void;
  onClose: () => void;
}) {
  const { navigate } = useInvestigation();
  const { source, target, connected, steps, relationship_kind, hop_count, explanation } = relationship;

  const sourceComponent = componentForFile(components, source.file_path);
  const targetComponent = componentForFile(components, target.file_path);
  const sourceFindings = findingsForFile(smells, source.file_path);
  const targetFindings = findingsForFile(smells, target.file_path);

  const ledger = evidenceLedger(relationship);
  const weakest = relationship_kind === "INDIRECT" && steps.length > 1 ? weakestLinkConfidence(steps) : null;
  const chain = relationship_kind === "INDIRECT" ? pathChain(relationship) : [];

  return (
    <section className="rounded-lg border border-(--border) bg-(--bg-raised) shadow-sm">
      <div className="flex items-center justify-between gap-2 border-b border-(--border) px-4 py-3">
        <div className="flex items-center gap-2.5">
          <span className="text-xs font-semibold tracking-[0.12em] text-(--text-faint) uppercase">
            Relationship investigation
          </span>
          {connected && relationship_kind && (
            <span
              className={cn(
                "rounded-full border px-2 py-0.5 font-mono text-[0.65rem] font-bold tracking-wide uppercase",
                relationship_kind === "DIRECT"
                  ? "border-(--ok)/30 bg-(--ok)/12 text-(--ok)"
                  : "border-(--bronze)/30 bg-(--bronze)/14 text-(--bronze)",
              )}
            >
              {relationship_kind}
              {relationship_kind === "INDIRECT" && hop_count ? ` · ${hop_count} hop${hop_count === 1 ? "" : "s"}` : ""}
            </span>
          )}
        </div>
        <button onClick={onClose} aria-label="Close relationship investigation" className="text-(--text-faint) hover:text-(--text)">
          <X className="size-4" />
        </button>
      </div>

      <div className="flex flex-col gap-4 px-4 py-4">
        {/* SOURCE / TARGET (PART 8) */}
        <div className="flex flex-wrap gap-3">
          <EntityIdentityCard label="Source" qualifiedName={source.qualified_name} symbolType={source.symbol_type} filePath={source.file_path} />
          <EntityIdentityCard label="Target" qualifiedName={target.qualified_name} symbolType={target.symbol_type} filePath={target.file_path} />
        </div>

        {!connected ? (
          /* NO PATH STATE (PART 19) — explanation here is the backend's own
           * deterministic sentence (ai/retrieval/relationship_service.py's
           * not_connected_explanation), never LLM-generated. */
          <div className="rounded-md border border-(--border) bg-(--bg) px-3.5 py-3">
            <p className="text-xs font-semibold tracking-wide text-(--text-faint) uppercase">
              No verified structural path
            </p>
            <p className="mt-1.5 text-sm leading-relaxed text-(--text-soft)">{explanation}</p>
          </div>
        ) : relationship_kind === "DIRECT" ? (
          /* DIRECT CONNECTION(S) (PART 7/20) — parallel edges, never a chain. */
          <div>
            <p className="mb-2 text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
              {steps.length === 1 ? "Direct connection" : `Direct connections (${steps.length})`}
            </p>
            <div className="flex flex-col gap-2">
              {steps.map((step, i) => (
                <div key={i} className="rounded-md border border-(--border) bg-(--bg) px-3 py-2.5">
                  <div className="flex flex-wrap items-center gap-1.5 text-xs">
                    <GitBranch className="size-3 text-(--text-faint)" />
                    <code className="min-w-0 truncate text-(--text)">{step.from_qualified_name}</code>
                    <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.6rem] font-semibold tracking-wide text-(--accent-text) uppercase">
                      {step.relationship_type}
                    </span>
                    <code className="min-w-0 truncate text-(--text)">{step.to_qualified_name}</code>
                  </div>
                  <StepEvidence step={step} />
                </div>
              ))}
            </div>
          </div>
        ) : (
          /* EVIDENCE PATH (PART 6/9) — sequential chain, each node clickable. */
          <div>
            <p className="mb-2 text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
              Evidence path
            </p>
            <ol className="flex flex-col">
              {chain.map((name, i) => {
                const uid = resolveUid(name);
                return (
                  <li key={i}>
                    {uid ? (
                      <button
                        onClick={() => onFocusNode(uid)}
                        className="rounded px-1.5 py-1 text-left font-mono text-sm text-(--text) hover:bg-(--bg-sunken) hover:underline"
                        title="Focus this entity in the graph"
                      >
                        {name}
                      </button>
                    ) : (
                      <code className="block px-1.5 py-1 font-mono text-sm text-(--text)" title="Not present in the currently loaded graph view">
                        {name}
                      </code>
                    )}
                    {i < steps.length && (
                      <div className="ml-4 flex flex-col gap-0.5 border-l-2 border-(--border) py-1 pl-3.5">
                        <div className="flex items-center gap-1.5">
                          <ArrowDown className="size-3 text-(--text-faint)" />
                          <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.6rem] font-semibold tracking-wide text-(--accent-text) uppercase">
                            {steps[i].relationship_type}
                          </span>
                        </div>
                        <StepEvidence step={steps[i]} />
                      </div>
                    )}
                  </li>
                );
              })}
            </ol>
          </div>
        )}

        {/* WEAKEST-LINK CONFIDENCE (PART 12) — only for a genuine multi-hop chain. */}
        {weakest !== null && (
          <div className="rounded-md border border-(--border) bg-(--bg) px-3.5 py-2.5">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                Weakest-link confidence
              </span>
              <ConfidenceMeter value={weakest} />
            </div>
            <p className="mt-1 text-xs text-(--text-faint)">
              Overall relationship confidence is bounded by the least-confident hop.
            </p>
          </div>
        )}

        {/* EVIDENCE LEDGER (PART 18) */}
        {connected && (
          <div className="flex flex-wrap gap-x-5 gap-y-1.5 rounded-md border border-(--border) bg-(--bg) px-3.5 py-2.5 font-mono text-[0.65rem] text-(--text-faint)">
            <span>{ledger.relationshipCount} relationship{ledger.relationshipCount === 1 ? "" : "s"}</span>
            {ledger.hopCount !== null && <span>{ledger.hopCount} hop{ledger.hopCount === 1 ? "" : "s"}</span>}
            <span>{ledger.sourceLocationCount} source location{ledger.sourceLocationCount === 1 ? "" : "s"}</span>
            <span>{ledger.confidenceAssessmentCount} confidence assessment{ledger.confidenceAssessmentCount === 1 ? "" : "s"}</span>
            {ledger.observedEvidencePct !== null && <span>Observed evidence {ledger.observedEvidencePct}%</span>}
          </div>
        )}

        {/* RELATED FINDINGS (PART 15) */}
        {(sourceFindings.length > 0 || targetFindings.length > 0) && (
          <div className="flex flex-col gap-2 border-t border-(--border) pt-3">
            <RelatedFindingsList label="Related findings — source" findings={sourceFindings} />
            <RelatedFindingsList label="Related findings — target" findings={targetFindings} />
          </div>
        )}

        {/* CONTEXTUAL ACTIONS (PART 14) */}
        <div className="flex flex-col gap-2 border-t border-(--border) pt-3">
          <div>
            <p className="mb-1 text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">Source actions</p>
            <EntityActions qualifiedName={source.qualified_name} componentId={sourceComponent?.id ?? null} findingsCount={sourceFindings.length} />
          </div>
          <div>
            <p className="mb-1 text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">Target actions</p>
            <EntityActions qualifiedName={target.qualified_name} componentId={targetComponent?.id ?? null} findingsCount={targetFindings.length} />
          </div>
          <button
            onClick={() =>
              navigate("ask", {
                presetQuestion: `How is \`${source.qualified_name}\` related to \`${target.qualified_name}\`?`,
              })
            }
            className="flex w-fit items-center gap-1.5 rounded-md border border-(--border) bg-(--bg-raised) px-2.5 py-1.5 text-xs font-medium text-(--text-soft) transition-colors hover:border-(--accent)/40 hover:text-(--text)"
          >
            <ScrollText className="size-3.5" strokeWidth={2} />
            Ask about this relationship
          </button>
        </div>

        {/* INTERPRETATION (PART 13) — LLM narration, last, clearly labeled,
         * never the primary structural claim. */}
        {connected && (
          <div className="border-t border-(--border) pt-3">
            <p className="mb-1.5 flex items-center gap-1.5 text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">
              <Sparkles className="size-3" /> Archeologist interpretation
            </p>
            <p className="text-xs leading-relaxed text-(--text-soft)">{explanation}</p>
          </div>
        )}
      </div>
    </section>
  );
}
