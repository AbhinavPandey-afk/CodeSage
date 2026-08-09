import cytoscape, { type Core } from "cytoscape";
import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { GraphNode } from "../api/types";

const EDGE_COLOR: Record<string, string> = {
  CONTAINS: "#7a8488",
  INHERITS: "#4f8ac1",
  USES: "#c1832f",
};

export function GraphView({ repoId }: { repoId: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [nodeCount, setNodeCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    api
      .getGraph(repoId, 150)
      .then((view) => {
        if (cancelled || !containerRef.current) return;
        setTruncated(view.truncated);
        setNodeCount(view.nodes.length);

        const nodesByUid = new Map(view.nodes.map((n) => [n.uid, n]));
        const elements = [
          ...view.nodes.map((n) => ({
            data: {
              id: n.uid,
              label: n.name,
              type: n.symbol_type,
              degree: n.degree,
            },
          })),
          ...view.edges.map((e, i) => ({
            data: {
              id: `e${i}`,
              source: e.source_uid,
              target: e.target_uid,
              type: e.relationship_type,
              weight: e.weight,
            },
          })),
        ];

        cyRef.current?.destroy();
        const cy = cytoscape({
          container: containerRef.current,
          elements,
          style: [
            {
              selector: "node",
              style: {
                label: "data(label)",
                "font-size": 9,
                color: "#aab3b7",
                "text-valign": "bottom",
                "text-margin-y": 4,
                width: "mapData(degree, 0, 40, 14, 44)",
                height: "mapData(degree, 0, 40, 14, 44)",
                "background-color": "#c1832f",
                "border-width": 1,
                "border-color": "#8a5a1d",
              },
            },
            {
              selector: "node[type = 'file']",
              style: { "background-color": "#4f8ac1", "border-color": "#2d5d8c", shape: "round-rectangle" },
            },
            {
              selector: "edge",
              style: {
                width: "mapData(weight, 1, 10, 1, 5)",
                "line-color": (ele: cytoscape.EdgeSingular) => EDGE_COLOR[ele.data("type")] ?? "#7a8488",
                "target-arrow-color": (ele: cytoscape.EdgeSingular) => EDGE_COLOR[ele.data("type")] ?? "#7a8488",
                "target-arrow-shape": "triangle",
                "curve-style": "bezier",
                opacity: 0.7,
              },
            },
            {
              selector: "node:selected",
              style: { "border-width": 3, "border-color": "#e3b473" },
            },
          ],
          layout: { name: "cose", animate: false, padding: 30 },
        });

        cy.on("tap", "node", (evt) => {
          const uid = evt.target.id();
          const node = nodesByUid.get(uid);
          if (node) setSelected(node);
        });
        cy.on("tap", (evt) => {
          if (evt.target === cy) setSelected(null);
        });

        cyRef.current = cy;
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load graph."));

    return () => {
      cancelled = true;
      cyRef.current?.destroy();
      cyRef.current = null;
    };
  }, [repoId]);

  if (error) return <p className="form-error">{error}</p>;

  return (
    <div className="graph-view">
      <div className="graph-legend">
        <span><i className="dot dot-file" /> File</span>
        <span><i className="dot dot-class" /> Class</span>
        <span><i className="line line-contains" /> Contains</span>
        <span><i className="line line-inherits" /> Inherits</span>
        <span><i className="line line-uses" /> Uses</span>
        {truncated && <span className="graph-truncated">Showing top {nodeCount} most-connected symbols</span>}
      </div>
      <div className="graph-canvas" ref={containerRef} />
      {selected && (
        <div className="graph-detail">
          <button className="graph-detail-close" onClick={() => setSelected(null)}>×</button>
          <span className="symbol-tag">{selected.symbol_type}</span>
          <code>{selected.qualified_name}</code>
          <div className="evidence-location">
            {selected.file_path}:{selected.start_line}-{selected.end_line}
          </div>
          <div className="graph-detail-degree">{selected.degree} connections</div>
        </div>
      )}
    </div>
  );
}
