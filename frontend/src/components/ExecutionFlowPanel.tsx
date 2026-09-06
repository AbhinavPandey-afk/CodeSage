import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { EntryPoint, ExecutionFlowReport, FlowHop } from "../api/types";

function FlowNode({ hop, depth }: { hop: FlowHop; depth: number }) {
  return (
    <div className="flow-node" style={{ marginLeft: depth === 0 ? 0 : 18 }}>
      <div className={`flow-hop ${hop.label === "PROPOSED" ? "flow-hop-proposed" : ""}`}>
        <span className={`flow-label-pill flow-label-${hop.label.toLowerCase()}`}>{hop.label}</span>
        <code className="flow-callee">{hop.callee_qualified_name}</code>
        {hop.terminal_kind && <span className={`chip chip-${hop.terminal_kind}`}>{hop.terminal_kind}</span>}
        {hop.source_file && hop.source_line && (
          <span className="flow-loc">
            {hop.source_file}:{hop.source_line}
          </span>
        )}
        <span className="flow-confidence">{Math.round(hop.confidence * 100)}%</span>
      </div>
      {hop.note && <p className="flow-note">{hop.note}</p>}
      {hop.children.length > 0 && (
        <div className="flow-children">
          {hop.children.map((c, i) => (
            <FlowNode key={i} hop={c} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export function ExecutionFlowPanel({ repoId }: { repoId: string }) {
  const [entryPoints, setEntryPoints] = useState<EntryPoint[] | null>(null);
  const [selected, setSelected] = useState<EntryPoint | null>(null);
  const [report, setReport] = useState<ExecutionFlowReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"observed" | "proposed">("observed");

  useEffect(() => {
    api
      .getEntryPoints(repoId)
      .then(setEntryPoints)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to list entry points."));
  }, [repoId]);

  const runReconstruction = async (entry: EntryPoint) => {
    setSelected(entry);
    setReport(null);
    setError(null);
    setLoading(true);
    setTab("observed");
    try {
      const r = await api.reconstructFlow(repoId, entry.uid);
      setReport(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reconstruct execution flow.");
    } finally {
      setLoading(false);
    }
  };

  if (error) return <p className="form-error">{error}</p>;
  if (!entryPoints) return <p className="hint">Detecting API entry points…</p>;
  if (entryPoints.length === 0) {
    return <p className="hint">No API entry points (route-decorated functions/methods) were detected in this repository.</p>;
  }

  return (
    <div className="flow-panel">
      <p className="arch-intro">
        Statically reconstructed from resolved call relationships — this does not execute the repository.
      </p>

      <div className="flow-entry-points">
        {entryPoints.map((e) => (
          <button
            key={e.uid}
            className={`suggestion-chip ${selected?.uid === e.uid ? "suggestion-chip-active" : ""}`}
            onClick={() => runReconstruction(e)}
          >
            {e.route_hint ?? e.qualified_name}
          </button>
        ))}
      </div>

      {loading && <p className="hint">Reconstructing flow…</p>}

      {report && (
        <div className="flow-report">
          {report.proposed && (
            <div className="tabs flow-subtabs">
              <button className={tab === "observed" ? "tab active" : "tab"} onClick={() => setTab("observed")}>
                Current (observed)
              </button>
              <button className={tab === "proposed" ? "tab active" : "tab"} onClick={() => setTab("proposed")}>
                Proposed
              </button>
            </div>
          )}
          <div className="flow-tree">
            <FlowNode hop={tab === "proposed" && report.proposed ? report.proposed : report.observed} depth={0} />
          </div>
          <ul className="detection-notes">
            {report.detection_notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
