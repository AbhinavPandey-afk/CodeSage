import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { EntryPoint, ExecutionFlowReport } from "../api/types";
import { ComponentFlow } from "@/components/flow/ComponentFlow";
import { EntryPointSelector } from "@/components/flow/EntryPointSelector";
import { FlowDiffSummary } from "@/components/flow/FlowDiffSummary";
import { LimitedTraceState, NoEntryPointsState, TraceErrorState, TraceLoadingState } from "@/components/flow/FlowStates";
import { TraceCanvas } from "@/components/flow/TraceCanvas";
import { TraceContext } from "@/components/flow/TraceContext";
import { TraceInspector } from "@/components/flow/TraceInspector";
import { TraceLegend } from "@/components/flow/TraceLegend";
import { TraceNarrative } from "@/components/flow/TraceNarrative";
import { UnderstandFlow } from "@/components/flow/UnderstandFlow";
import { SectionLabel } from "@/components/evidence/SectionLabel";
import {
  buildFlatNarrative,
  buildNarrative,
  buildSymbolTree,
  collectProposedChanges,
  findInList,
  findNode,
  hasFrameworkBoundary,
  pruneByScope,
  tagScope,
  type AbstractionLevel,
  type FlowMode,
  type TraceNode,
  type TraceScope,
} from "@/lib/flowModel";
import { buildComponentParticipation, buildUnderstandStages } from "@/lib/semanticFlow";
import { useInvestigation } from "@/lib/investigation";
import { cn } from "@/lib/utils";

const LEVELS: { value: AbstractionLevel; label: string }[] = [
  { value: "overview", label: "Understand" },
  { value: "components", label: "Components" },
  { value: "symbols", label: "Symbols" },
];

const DEPTH_OPTIONS: { value: number | null; label: string }[] = [
  { value: 1, label: "1" },
  { value: 2, label: "2" },
  { value: 3, label: "3" },
  { value: 5, label: "5" },
  { value: null, label: "All" },
];

function toggleGroupBtn(active: boolean, isFirst: boolean) {
  return cn(
    "px-3 py-1.5 text-xs font-medium focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-(--accent) focus-visible:outline-none",
    !isFirst && "border-l border-(--border)",
    active ? "bg-(--accent-soft) text-(--accent-text)" : "bg-(--bg-raised) text-(--text-faint)",
  );
}

export function ExecutionFlowPanel({ repoId }: { repoId: string }) {
  const { focus } = useInvestigation();
  const consumedFocusRef = useRef(false);

  const [entryPoints, setEntryPoints] = useState<EntryPoint[] | null>(null);
  const [entryPointsError, setEntryPointsError] = useState<string | null>(null);
  const [selected, setSelected] = useState<EntryPoint | null>(null);
  const [report, setReport] = useState<ExecutionFlowReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [reconstructError, setReconstructError] = useState<string | null>(null);
  const [language, setLanguage] = useState<string | null>(null);

  const [mode, setMode] = useState<FlowMode>("observed");
  const [level, setLevel] = useState<AbstractionLevel>("symbols");
  const [scope, setScope] = useState<"repository" | TraceScope>("repository");
  const [depthLimit, setDepthLimit] = useState<number | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  useEffect(() => {
    api
      .getEntryPoints(repoId)
      .then(setEntryPoints)
      .catch((err) => setEntryPointsError(err instanceof Error ? err.message : "Failed to list entry points."));
    api
      .getRepository(repoId)
      .then((r) => {
        const dominant = Object.entries(r.languages).sort((a, b) => b[1] - a[1])[0]?.[0];
        setLanguage(dominant ? dominant[0].toUpperCase() + dominant.slice(1) : null);
      })
      .catch(() => setLanguage(null));
  }, [repoId]);

  const runReconstruction = async (entry: EntryPoint) => {
    setSelected(entry);
    setReport(null);
    setReconstructError(null);
    setLoading(true);
    setMode("observed");
    setScope("repository");
    setSelectedNodeId(null);
    try {
      const r = await api.reconstructFlow(repoId, entry.uid);
      setReport(r);
    } catch (err) {
      setReconstructError(err instanceof Error ? err.message : "Failed to reconstruct execution flow.");
    } finally {
      setLoading(false);
    }
  };

  // Arriving from another page (e.g. Architecture's "Trace Flow" on a
  // component) should land on a relevant entry point rather than an empty
  // selector — component_id is itself a directory prefix, so it can match
  // directly against an entry's own file path without a second API call.
  useEffect(() => {
    if (consumedFocusRef.current || !entryPoints || entryPoints.length === 0) return;
    if (!focus?.qualifiedName && !focus?.componentId) return;
    consumedFocusRef.current = true;
    const match =
      entryPoints.find((e) => e.qualified_name === focus.qualifiedName) ??
      entryPoints.find((e) => focus.componentId && e.file_path.startsWith(`${focus.componentId}/`));
    if (match) void runReconstruction(match);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entryPoints, focus]);

  const activeHop = report ? (mode === "proposed" && report.proposed ? report.proposed : report.observed) : null;
  const isLimitedTrace = activeHop ? activeHop.children.length === 0 : false;

  // Understand, Components, and Symbols are genuinely different aggregations
  // of the same evidence (see lib/semanticFlow.ts), not the same tree
  // rendered at different sizes — so each produces its own data shape here.
  const symbolTree = useMemo(() => (activeHop && level === "symbols" ? tagScope(buildSymbolTree(activeHop)) : null), [activeHop, level]);
  const frameworkBoundary = useMemo(() => (symbolTree ? hasFrameworkBoundary(symbolTree) : false), [symbolTree]);
  const scopedTree = useMemo(() => {
    if (!symbolTree) return null;
    if (scope === "repository") return symbolTree;
    return pruneByScope(symbolTree, scope);
  }, [symbolTree, scope]);

  const stages = useMemo(() => (activeHop && level === "overview" ? buildUnderstandStages(activeHop) : null), [activeHop, level]);
  const components = useMemo(() => (activeHop && level === "components" ? buildComponentParticipation(activeHop) : null), [activeHop, level]);

  const narrativeSteps = useMemo(() => {
    if (scopedTree) return buildNarrative(scopedTree);
    if (stages) return buildFlatNarrative(stages);
    if (components) return buildFlatNarrative(components);
    return [];
  }, [scopedTree, stages, components]);

  const proposedChanges = useMemo(() => (report?.proposed ? collectProposedChanges(report.proposed) : []), [report]);

  const selectedNode: TraceNode | null = useMemo(() => {
    if (!selectedNodeId) return null;
    if (scopedTree) return findNode(scopedTree, selectedNodeId);
    if (stages) return findInList(stages, selectedNodeId);
    if (components) return findInList(components, selectedNodeId);
    return null;
  }, [scopedTree, stages, components, selectedNodeId]);

  const selectLevel = (next: AbstractionLevel) => {
    setLevel(next);
    setSelectedNodeId(null);
  };
  const selectMode = (next: FlowMode) => {
    setMode(next);
    setSelectedNodeId(null);
  };
  const selectScope = (next: "repository" | TraceScope) => {
    setScope(next);
    setSelectedNodeId(null);
  };
  /** Understand/Components stages are DERIVED groupings — "expand evidence"
   * jumps to the real underlying symbol at Symbols level, never fakes detail
   * inline for something that isn't itself a single repository fact. */
  const expandEvidence = (memberId: string) => {
    setLevel("symbols");
    setSelectedNodeId(memberId);
  };

  if (entryPointsError) return <p className="text-sm text-(--bad)">{entryPointsError}</p>;

  if (!entryPoints) {
    return (
      <div className="flex flex-col gap-2">
        {[0, 1].map((i) => (
          <div key={i} className="h-11 w-72 animate-pulse rounded-md bg-(--bg-sunken)" />
        ))}
      </div>
    );
  }

  if (entryPoints.length === 0) return <NoEntryPointsState />;

  return (
    <div className={cn("min-w-0", selectedNode && "lg:flex lg:items-start lg:gap-5")}>
      <div className="min-w-0 flex-1">
        <SectionLabel index="01">System trace</SectionLabel>
        <p className="mb-5 max-w-2xl text-sm text-(--text-soft)">
          Reconstructed statically from resolved call relationships in the knowledge graph — the repository is never
          executed, and dynamic dispatch, reflection, or dependency injection may cause the real path to differ from
          what's shown here.
        </p>

        <div className="mb-5 flex flex-wrap items-center gap-3">
          <EntryPointSelector entryPoints={entryPoints} selected={selected} onSelect={runReconstruction} />

          {report && (
            <div role="group" aria-label="Abstraction level" className="inline-flex overflow-hidden rounded-md border border-(--border)">
              {LEVELS.map((l, i) => (
                <button key={l.value} onClick={() => selectLevel(l.value)} aria-pressed={level === l.value} className={toggleGroupBtn(level === l.value, i === 0)}>
                  {l.label}
                </button>
              ))}
            </div>
          )}

          {report?.proposed && (
            <div role="group" aria-label="Current or proposed" className="inline-flex overflow-hidden rounded-md border border-(--border)">
              <button onClick={() => selectMode("observed")} aria-pressed={mode === "observed"} className={toggleGroupBtn(mode === "observed", true)}>
                Current
              </button>
              <button onClick={() => selectMode("proposed")} aria-pressed={mode === "proposed"} className={toggleGroupBtn(mode === "proposed", false)}>
                Proposed
              </button>
            </div>
          )}

          {level === "symbols" && frameworkBoundary && (
            <div role="group" aria-label="Trace scope" className="inline-flex overflow-hidden rounded-md border border-(--border)">
              <button
                onClick={() => selectScope("application")}
                aria-pressed={scope === "application"}
                title="Only this repository's own top-level directory"
                className={toggleGroupBtn(scope === "application", true)}
              >
                Application
              </button>
              <button
                onClick={() => selectScope("framework")}
                aria-pressed={scope === "framework"}
                title="Only code outside the entry point's own directory"
                className={toggleGroupBtn(scope === "framework", false)}
              >
                Framework
              </button>
              <button
                onClick={() => selectScope("repository")}
                aria-pressed={scope === "repository"}
                title="Everything reconstructed, unfiltered"
                className={toggleGroupBtn(scope === "repository", false)}
              >
                Repository
              </button>
            </div>
          )}

          {level === "symbols" && report && !isLimitedTrace && (
            <div role="group" aria-label="Trace depth" className="inline-flex items-center gap-1.5 text-xs text-(--text-faint)">
              Depth
              <div className="inline-flex overflow-hidden rounded-md border border-(--border)">
                {DEPTH_OPTIONS.map((d, i) => (
                  <button
                    key={d.label}
                    onClick={() => setDepthLimit(d.value)}
                    aria-pressed={depthLimit === d.value}
                    className={cn(toggleGroupBtn(depthLimit === d.value, i === 0), "px-2.5")}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {!selected && (
          <p className="rounded-lg border border-dashed border-(--border) px-6 py-10 text-center text-sm text-(--text-faint)">
            Select an entry point above to reconstruct how a request moves through this repository.
          </p>
        )}

        {loading && <TraceLoadingState />}
        {reconstructError && <TraceErrorState message={reconstructError} onRetry={() => selected && runReconstruction(selected)} />}

        {report && activeHop && !loading && (
          <div>
            <TraceContext entry={report.entry} entryHop={activeHop} language={language} />

            <p className="mb-2.5 text-xs text-(--text-faint)">
              {mode === "proposed"
                ? "Design projection based on Architecture Optimization — this path does not exist yet."
                : "Observed / statically reconstructed from repository evidence."}
            </p>

            {isLimitedTrace ? (
              <LimitedTraceState entry={report.entry} entryHop={activeHop} />
            ) : (
              <>
                {level === "symbols" && <TraceLegend showProposed={mode === "proposed"} />}

                <div className="mt-3">
                  {level === "symbols" && scopedTree && (
                    <TraceCanvas
                      tree={scopedTree}
                      selectedId={selectedNodeId}
                      onSelect={setSelectedNodeId}
                      onExpandScope={() => selectScope("repository")}
                      depthLimit={depthLimit}
                    />
                  )}
                  {level === "overview" && stages && (
                    <UnderstandFlow stages={stages} selectedId={selectedNodeId} onSelect={setSelectedNodeId} onExpandEvidence={expandEvidence} />
                  )}
                  {level === "components" && components && (
                    <ComponentFlow components={components} selectedId={selectedNodeId} onSelect={setSelectedNodeId} onExpandEvidence={expandEvidence} />
                  )}
                </div>

                {mode === "proposed" && (
                  <div className="mt-5">
                    <FlowDiffSummary
                      changes={proposedChanges}
                      onSelectChange={level === "symbols" ? (id) => setSelectedNodeId(id) : undefined}
                    />
                  </div>
                )}

                <div className="mt-6 rounded-lg border border-(--border) bg-(--bg-raised) p-4">
                  <h3 className="mb-2 text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                    Trace narrative
                  </h3>
                  <TraceNarrative steps={narrativeSteps} selectedId={selectedNodeId} onSelectStep={setSelectedNodeId} />
                </div>
              </>
            )}

            {report.detection_notes.length > 0 && (
              <ul className="mt-5 flex flex-col gap-1 border-t border-(--border) pt-4">
                {report.detection_notes.map((n, i) => (
                  <li key={i} className="text-xs text-(--text-faint) italic">
                    {n}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {report && (
        <TraceInspector
          node={selectedNode}
          entryLabel={report.entry.route_hint ?? report.entry.qualified_name}
          onClose={() => setSelectedNodeId(null)}
          onExpandEvidence={expandEvidence}
        />
      )}
    </div>
  );
}
