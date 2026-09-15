import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { EntryPoint, ExecutionFlowReport } from "../api/types";
import { EntryPointSelector } from "@/components/flow/EntryPointSelector";
import { FlowDiffSummary } from "@/components/flow/FlowDiffSummary";
import { EntryOnlyState, NoEntryPointsState, TraceErrorState, TraceLoadingState } from "@/components/flow/FlowStates";
import { TraceCanvas } from "@/components/flow/TraceCanvas";
import { TraceInspector } from "@/components/flow/TraceInspector";
import { TraceLegend } from "@/components/flow/TraceLegend";
import { TraceNarrative } from "@/components/flow/TraceNarrative";
import { SectionLabel } from "@/components/evidence/SectionLabel";
import {
  buildNarrative,
  buildTrace,
  collectProposedChanges,
  findNode,
  type AbstractionLevel,
  type FlowMode,
} from "@/lib/flowModel";
import { cn } from "@/lib/utils";

const LEVELS: { value: AbstractionLevel; label: string }[] = [
  { value: "overview", label: "Overview" },
  { value: "components", label: "Components" },
  { value: "symbols", label: "Symbols" },
];

export function ExecutionFlowPanel({ repoId }: { repoId: string }) {
  const [entryPoints, setEntryPoints] = useState<EntryPoint[] | null>(null);
  const [entryPointsError, setEntryPointsError] = useState<string | null>(null);
  const [selected, setSelected] = useState<EntryPoint | null>(null);
  const [report, setReport] = useState<ExecutionFlowReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [reconstructError, setReconstructError] = useState<string | null>(null);

  const [mode, setMode] = useState<FlowMode>("observed");
  const [level, setLevel] = useState<AbstractionLevel>("symbols");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  useEffect(() => {
    api
      .getEntryPoints(repoId)
      .then(setEntryPoints)
      .catch((err) => setEntryPointsError(err instanceof Error ? err.message : "Failed to list entry points."));
  }, [repoId]);

  const runReconstruction = async (entry: EntryPoint) => {
    setSelected(entry);
    setReport(null);
    setReconstructError(null);
    setLoading(true);
    setMode("observed");
    try {
      const r = await api.reconstructFlow(repoId, entry.uid);
      setReport(r);
    } catch (err) {
      setReconstructError(err instanceof Error ? err.message : "Failed to reconstruct execution flow.");
    } finally {
      setLoading(false);
    }
  };

  const activeHop = report ? (mode === "proposed" && report.proposed ? report.proposed : report.observed) : null;
  const tree = useMemo(() => (activeHop ? buildTrace(activeHop, level) : null), [activeHop, level]);
  const narrativeSteps = useMemo(() => (tree ? buildNarrative(tree) : []), [tree]);
  const proposedChanges = useMemo(() => (report?.proposed ? collectProposedChanges(report.proposed) : []), [report]);
  const selectedNode = useMemo(() => (tree && selectedNodeId ? findNode(tree, selectedNodeId) : null), [tree, selectedNodeId]);

  // A different level/mode produces a different tree with different node
  // ids, so a stale selection either points nowhere or at the wrong thing.
  useEffect(() => setSelectedNodeId(null), [mode, level, report]);

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

          {report?.proposed && (
            <div className="inline-flex overflow-hidden rounded-md border border-(--border)">
              <button
                onClick={() => setMode("observed")}
                aria-pressed={mode === "observed"}
                className={cn(
                  "px-3 py-1.5 text-xs font-medium",
                  mode === "observed" ? "bg-(--accent-soft) text-(--accent-text)" : "bg-(--bg-raised) text-(--text-faint)",
                )}
              >
                Current
              </button>
              <button
                onClick={() => setMode("proposed")}
                aria-pressed={mode === "proposed"}
                className={cn(
                  "border-l border-(--border) px-3 py-1.5 text-xs font-medium",
                  mode === "proposed" ? "bg-(--accent-soft) text-(--accent-text)" : "bg-(--bg-raised) text-(--text-faint)",
                )}
              >
                Proposed
              </button>
            </div>
          )}

          {report && (
            <div className="inline-flex overflow-hidden rounded-md border border-(--border)">
              {LEVELS.map((l, i) => (
                <button
                  key={l.value}
                  onClick={() => setLevel(l.value)}
                  aria-pressed={level === l.value}
                  className={cn(
                    "px-3 py-1.5 text-xs font-medium",
                    i > 0 && "border-l border-(--border)",
                    level === l.value ? "bg-(--accent-soft) text-(--accent-text)" : "bg-(--bg-raised) text-(--text-faint)",
                  )}
                >
                  {l.label}
                </button>
              ))}
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

        {report && tree && !loading && (
          <div>
            <p className="mb-2.5 text-xs text-(--text-faint)">
              {mode === "proposed"
                ? "Design projection based on Architecture Optimization — this path does not exist yet."
                : "Observed / statically reconstructed from repository evidence."}
            </p>

            <TraceLegend showProposed={mode === "proposed"} />
            <div className="mt-3">
              <TraceCanvas tree={tree} selectedId={selectedNodeId} onSelect={setSelectedNodeId} />
            </div>

            {tree.children.length === 0 && <EntryOnlyState />}

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
        <TraceInspector node={selectedNode} entryLabel={report.entry.route_hint ?? report.entry.qualified_name} onClose={() => setSelectedNodeId(null)} />
      )}
    </div>
  );
}
