import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { ArchitectureModel, OptimizationReport } from "../api/types";
import { RestorationCard } from "@/components/optimization/RestorationCard";

const RISK_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;

export function OptimizationPanel({ repoId }: { repoId: string }) {
  const [report, setReport] = useState<OptimizationReport | null>(null);
  const [architecture, setArchitecture] = useState<ArchitectureModel | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setReport(null);
    setError(null);
    api
      .getOptimization(repoId)
      .then(setReport)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to generate optimization proposals."));
    api.getArchitecture(repoId).then(setArchitecture).catch(() => setArchitecture(null));
  }, [repoId]);

  // Optimization's `affected_components` uses the component's path-slug id
  // ("src/flask"), not its display name ("src / flask" — spaced for
  // readability by the architecture endpoint), so match against id directly.
  const knownComponentIds = useMemo(
    () => new Set((architecture?.components ?? []).map((c) => c.id)),
    [architecture],
  );

  const riskCounts = useMemo(() => {
    const counts = { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 };
    for (const p of report?.proposals ?? []) counts[p.risk_level]++;
    return counts;
  }, [report]);

  if (error) return <p className="text-sm text-(--bad)">{error}</p>;
  if (!report)
    return (
      <div className="flex flex-col gap-3">
        {[0, 1].map((i) => (
          <div key={i} className="h-40 animate-pulse rounded-lg bg-(--bg-sunken)" />
        ))}
      </div>
    );

  return (
    <div>
      <p className="mb-5 max-w-2xl text-sm text-(--text-soft)">
        {report.current_architecture_summary} Every proposal below is a recommendation traced back to a specific
        structural finding — nothing here modifies the repository.
      </p>

      {report.proposals.length === 0 ? (
        <p className="text-sm text-(--text-faint)">
          No structural violations were found, so no restoration proposals are recommended.
        </p>
      ) : (
        <>
          <div className="mb-5 flex flex-wrap gap-x-8 gap-y-3">
            <div>
              <strong className="font-mono text-xl text-(--text) tabular-nums">{report.proposals.length}</strong>
              <span className="block text-[0.65rem] font-medium tracking-wide text-(--text-faint) uppercase">
                Proposals
              </span>
            </div>
            {RISK_ORDER.filter((r) => riskCounts[r] > 0).map((r) => (
              <div key={r}>
                <strong className="font-mono text-xl text-(--text) tabular-nums">{riskCounts[r]}</strong>
                <span className="block text-[0.65rem] font-medium tracking-wide text-(--text-faint) uppercase">
                  {r.charAt(0) + r.slice(1).toLowerCase()} risk
                </span>
              </div>
            ))}
          </div>

          <div className="flex flex-col gap-4">
            {report.proposals.map((p, i) => (
              <RestorationCard
                key={p.id}
                proposal={p}
                index={i + 1}
                componentId={knownComponentIds.has(p.affected_components[0]) ? p.affected_components[0] : null}
              />
            ))}
          </div>
        </>
      )}

      {report.detection_notes.length > 0 && (
        <ul className="mt-6 flex flex-col gap-1 border-t border-(--border) pt-4">
          {report.detection_notes.map((n, i) => (
            <li key={i} className="text-xs text-(--text-faint) italic">
              {n}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
