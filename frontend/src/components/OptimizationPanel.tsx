import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { OptimizationGoal, OptimizationProposal, OptimizationReport } from "../api/types";

const GOAL_LABELS: Record<OptimizationGoal, string> = {
  enforce_layering: "Enforce layering",
  reduce_circularity: "Reduce circularity",
  reduce_coupling: "Reduce coupling",
};

function ConfidencePill({ label }: { label: string }) {
  return <span className={`confidence-pill confidence-${label.toLowerCase()}`}>{label}</span>;
}

function ProposalCard({ proposal }: { proposal: OptimizationProposal }) {
  return (
    <div className="opt-proposal">
      <div className="opt-proposal-header">
        <span className="arch-role-pill">{GOAL_LABELS[proposal.goal] ?? proposal.goal}</span>
        <span className={`risk-pill risk-${proposal.risk_level.toLowerCase()}`}>{proposal.risk_level} RISK</span>
        <ConfidencePill label={proposal.confidence_label} />
      </div>

      <div className="opt-block">
        <span className="opt-block-label">Problem (observed)</span>
        <p>{proposal.problem}</p>
        <p className="opt-evidence">{proposal.evidence}</p>
      </div>

      <div className="opt-block">
        <span className="opt-block-label">Proposed change</span>
        <p>{proposal.proposed_change}</p>
      </div>

      <div className="opt-grid">
        <div>
          <span className="opt-block-label">Expected benefit</span>
          <p>{proposal.expected_benefit}</p>
        </div>
        <div>
          <span className="opt-block-label">Potential risk</span>
          <p>{proposal.potential_risk}</p>
        </div>
      </div>

      {proposal.representative_impact && (
        <p className="hint opt-impact-note">
          Representative impact check: <code>{proposal.representative_impact.symbol_qualified_name}</code> has{" "}
          {proposal.representative_impact.direct_dependents} direct and{" "}
          {proposal.representative_impact.indirect_dependents} indirect dependent(s).
        </p>
      )}

      <p className="opt-affected">
        Affects: {proposal.affected_components.join(", ")} ({proposal.affected_files.length} file
        {proposal.affected_files.length === 1 ? "" : "s"})
      </p>
    </div>
  );
}

export function OptimizationPanel({ repoId }: { repoId: string }) {
  const [report, setReport] = useState<OptimizationReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setReport(null);
    setError(null);
    api
      .getOptimization(repoId)
      .then(setReport)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to generate optimization proposals."));
  }, [repoId]);

  if (error) return <p className="form-error">{error}</p>;
  if (!report) return <p className="hint">Analyzing the reconstructed architecture for optimization opportunities…</p>;

  return (
    <div className="opt-panel">
      <p className="arch-intro">
        {report.current_architecture_summary} These are recommendations only — nothing here modifies the repository.
      </p>

      {report.proposals.length === 0 ? (
        <p className="hint">No structural violations were found, so no optimizations are proposed.</p>
      ) : (
        <div className="opt-proposals">
          {report.proposals.map((p) => (
            <ProposalCard key={p.id} proposal={p} />
          ))}
        </div>
      )}

      <ul className="detection-notes">
        {report.detection_notes.map((n, i) => (
          <li key={i}>{n}</li>
        ))}
      </ul>
    </div>
  );
}
