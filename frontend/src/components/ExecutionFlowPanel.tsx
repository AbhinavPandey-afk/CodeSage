import cytoscape, { type Core } from "cytoscape";
import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { EntryPoint, ExecutionFlowReport, FlowHop, FlowLabel } from "../api/types";

interface FlowNodeDatum {
  id: string;
  label: string;
  qualifiedName: string;
  terminalKind: "database" | "external_service" | null;
  isEntry: boolean;
}

interface FlowEdgeDatum {
  id: string;
  source: string;
  target: string;
  confidence: number;
  label: FlowLabel;
  relationshipType: string;
  sourceFile: string | null;
  sourceLine: number | null;
  note: string | null;
}

type FlowSelection =
  | { kind: "node"; data: FlowNodeDatum }
  | { kind: "edge"; data: FlowEdgeDatum };

function shortName(qualifiedName: string): string {
  const parts = qualifiedName.split(".");
  return parts[parts.length - 1] || qualifiedName;
}

// A FlowHop is really an edge (caller -> callee); nested `children` are
// further hops made from that callee. Flattening into distinct nodes lets a
// symbol called from two branches collapse into the same diagram node,
// exactly like the resolved-call graph it was derived from.
function flattenFlow(root: FlowHop): { nodes: FlowNodeDatum[]; edges: FlowEdgeDatum[]; rootId: string } {
  const nodes = new Map<string, FlowNodeDatum>();
  const edges: FlowEdgeDatum[] = [];
  let counter = 0;

  function ensureNode(qualifiedName: string, terminalKind: FlowNodeDatum["terminalKind"] = null, isEntry = false) {
    const existing = nodes.get(qualifiedName);
    if (existing) {
      if (terminalKind) existing.terminalKind = terminalKind;
      if (isEntry) existing.isEntry = true;
      return;
    }
    nodes.set(qualifiedName, {
      id: qualifiedName,
      label: shortName(qualifiedName),
      qualifiedName,
      terminalKind,
      isEntry,
    });
  }

  function visit(hop: FlowHop) {
    ensureNode(hop.caller_qualified_name);
    ensureNode(hop.callee_qualified_name, hop.terminal_kind);
    edges.push({
      id: `e${counter++}`,
      source: hop.caller_qualified_name,
      target: hop.callee_qualified_name,
      confidence: hop.confidence,
      label: hop.label,
      relationshipType: hop.relationship_type,
      sourceFile: hop.source_file,
      sourceLine: hop.source_line,
      note: hop.note,
    });
    hop.children.forEach(visit);
  }

  // The root hop's caller_qualified_name is "" -- a sentinel meaning "nothing
  // calls the entry point, it IS the start" (see execution_flow/engine.py's
  // observed_root). Its callee is the actual entry point, so seed that as
  // the root node directly and only walk children as real caller->callee
  // edges, rather than drawing a bogus "" -> entry edge (which also crashes
  // Cytoscape, since "" is not a valid element id).
  ensureNode(root.callee_qualified_name, root.terminal_kind, true);
  root.children.forEach(visit);
  return { nodes: [...nodes.values()], edges, rootId: root.callee_qualified_name };
}

export function ExecutionFlowPanel({ repoId }: { repoId: string }) {
  const [entryPoints, setEntryPoints] = useState<EntryPoint[] | null>(null);
  const [selected, setSelected] = useState<EntryPoint | null>(null);
  const [report, setReport] = useState<ExecutionFlowReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"observed" | "proposed">("observed");
  const [flowSelection, setFlowSelection] = useState<FlowSelection | null>(null);

  const flowContainerRef = useRef<HTMLDivElement>(null);
  const flowCyRef = useRef<Core | null>(null);

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
    setFlowSelection(null);
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

  useEffect(() => {
    if (!report || !flowContainerRef.current) return;
    setFlowSelection(null);

    const activeHop = tab === "proposed" && report.proposed ? report.proposed : report.observed;
    const { nodes, edges, rootId } = flattenFlow(activeHop);
    const nodesById = new Map(nodes.map((n) => [n.id, n]));
    const edgesById = new Map(edges.map((e) => [e.id, e]));

    const elements = [
      ...nodes.map((n) => ({
        data: {
          id: n.id,
          label: n.label,
          isEntry: n.isEntry,
          terminalKind: n.terminalKind ?? "",
        },
      })),
      ...edges.map((e) => ({
        data: { id: e.id, source: e.source, target: e.target, label: e.label },
      })),
    ];

    flowCyRef.current?.destroy();
    const cy = cytoscape({
      container: flowContainerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "font-size": 10,
            color: "#aab3b7",
            "text-valign": "bottom",
            "text-margin-y": 6,
            "text-wrap": "wrap",
            "text-max-width": "90px",
            width: 34,
            height: 34,
            "background-color": "#4f8ac1",
            "border-width": 1,
            "border-color": "#2d5d8c",
          },
        },
        {
          selector: "node[?isEntry]",
          style: { "background-color": "#3f8a5c", "border-color": "#2c6142", shape: "round-diamond" },
        },
        {
          selector: "node[terminalKind = 'database']",
          style: { "background-color": "#5b8a8a", "border-color": "#3d5f5f", shape: "barrel" },
        },
        {
          selector: "node[terminalKind = 'external_service']",
          style: { "background-color": "#b98a1f", "border-color": "#8a6717", shape: "round-rectangle" },
        },
        {
          selector: "edge",
          style: {
            width: 2,
            "line-color": "#7a8488",
            "target-arrow-color": "#7a8488",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.9,
            "curve-style": "taxi",
            "taxi-direction": "downward",
            opacity: 0.75,
          },
        },
        {
          selector: "edge[label = 'PROPOSED']",
          style: {
            "line-color": "#e3b473",
            "target-arrow-color": "#e3b473",
            "line-style": "dashed",
            opacity: 0.95,
          },
        },
        {
          selector: "node:selected, edge:selected",
          style: { "border-width": 3, "border-color": "#e3b473", "line-color": "#e3b473", "target-arrow-color": "#e3b473" },
        },
      ],
      layout: {
        name: "breadthfirst",
        directed: true,
        roots: [rootId],
        spacingFactor: 1.3,
        padding: 30,
      } as cytoscape.LayoutOptions,
    });

    cy.on("tap", "node", (evt) => {
      const n = nodesById.get(evt.target.id());
      if (n) setFlowSelection({ kind: "node", data: n });
    });
    cy.on("tap", "edge", (evt) => {
      const e = edgesById.get(evt.target.id());
      if (e) setFlowSelection({ kind: "edge", data: e });
    });
    cy.on("tap", (evt) => {
      if (evt.target === cy) setFlowSelection(null);
    });

    flowCyRef.current = cy;

    return () => {
      cy.destroy();
      flowCyRef.current = null;
    };
  }, [report, tab]);

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

          <div className="graph-legend flow-legend">
            <span><i className="dot" style={{ background: "#3f8a5c" }} /> Entry point</span>
            <span><i className="dot" style={{ background: "#4f8ac1" }} /> Call step</span>
            <span><i className="dot" style={{ background: "#5b8a8a" }} /> Database</span>
            <span><i className="dot" style={{ background: "#b98a1f" }} /> External service</span>
            {tab === "proposed" && (
              <span>
                <i className="line" style={{ background: "repeating-linear-gradient(90deg, #e3b473 0 4px, transparent 4px 7px)" }} />
                Proposed hop
              </span>
            )}
            {" "}Click a node or arrow for evidence.
          </div>

          <div className="flow-canvas-wrap">
            <div className="flow-canvas" ref={flowContainerRef} />

            {flowSelection?.kind === "node" && (
              <div className="graph-detail">
                <button className="graph-detail-close" onClick={() => setFlowSelection(null)}>×</button>
                {flowSelection.data.isEntry && <span className="symbol-tag">entry point</span>}
                {flowSelection.data.terminalKind && (
                  <span className={`chip chip-${flowSelection.data.terminalKind}`}>{flowSelection.data.terminalKind}</span>
                )}
                <code>{flowSelection.data.qualifiedName}</code>
              </div>
            )}

            {flowSelection?.kind === "edge" && (
              <div className="graph-detail">
                <button className="graph-detail-close" onClick={() => setFlowSelection(null)}>×</button>
                <span className={`flow-label-pill flow-label-${flowSelection.data.label.toLowerCase()}`}>
                  {flowSelection.data.label}
                </span>
                <div className="graph-detail-degree">{flowSelection.data.relationshipType}</div>
                <div className="graph-detail-degree">confidence {Math.round(flowSelection.data.confidence * 100)}%</div>
                {flowSelection.data.sourceFile && flowSelection.data.sourceLine && (
                  <div className="evidence-location">
                    {flowSelection.data.sourceFile}:{flowSelection.data.sourceLine}
                  </div>
                )}
                {flowSelection.data.note && <p className="flow-note">{flowSelection.data.note}</p>}
              </div>
            )}
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
