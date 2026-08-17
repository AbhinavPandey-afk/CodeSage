import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Smell } from "../api/types";

const TYPE_LABELS: Record<string, string> = {
  circular_dependency: "Circular dependency",
  god_class: "God class",
  large_function: "Large function",
  dead_code_candidate: "Dead code candidate",
};

const MEDIUM_DISPLAY_LIMIT = 5;

function selectTopFindings(smells: Smell[]): { shown: Smell[]; hiddenCount: number } {
  const high = smells.filter((s) => s.severity === "HIGH");
  const medium = smells.filter((s) => s.severity === "MEDIUM").slice(0, MEDIUM_DISPLAY_LIMIT);
  const hiddenCount = smells.length - high.length - medium.length;
  return { shown: [...high, ...medium], hiddenCount };
}

export function SmellsPanel({ repoId }: { repoId: string }) {
  const [smells, setSmells] = useState<Smell[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getSmells(repoId).then(setSmells).catch((err) => setError(err.message));
  }, [repoId]);

  if (error) return <p className="form-error">{error}</p>;
  if (!smells) return <p className="hint">Analyzing architecture…</p>;
  if (smells.length === 0) return <p className="hint">No issues detected against the current thresholds.</p>;

  const { shown, hiddenCount } = selectTopFindings(smells);

  if (shown.length === 0) {
    return <p className="hint">Only low-priority findings were detected ({smells.length} total, not shown here).</p>;
  }

  return (
    <div className="smells-panel">
      {shown.map((s, i) => (
        <div key={i} className={`smell-item severity-${s.severity.toLowerCase()}`}>
          <div className="smell-header">
            <span className={`severity-pill severity-${s.severity.toLowerCase()}`}>{s.severity}</span>
            <span className="smell-type">{TYPE_LABELS[s.smell_type] ?? s.smell_type}</span>
          </div>
          <p className="smell-title">{s.title}</p>
          <p className="smell-explanation">{s.explanation}</p>
          <p className="smell-evidence">{s.evidence}</p>
          {s.affected.length > 0 && (
            <ul className="smell-affected">
              {s.affected.slice(0, 6).map((a, j) => (
                <li key={j}>
                  <code>{a.qualified_name}</code> — {a.file_path}:{a.start_line}
                </li>
              ))}
              {s.affected.length > 6 && <li>…and {s.affected.length - 6} more</li>}
            </ul>
          )}
        </div>
      ))}
      {hiddenCount > 0 && (
        <p className="hint smells-hidden-note">
          {hiddenCount} lower-priority finding{hiddenCount === 1 ? "" : "s"} not shown.
        </p>
      )}
    </div>
  );
}
