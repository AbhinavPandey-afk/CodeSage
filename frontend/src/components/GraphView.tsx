import cytoscape, { type Core } from "cytoscape";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { GraphNode, RelationshipResponse } from "../api/types";

type Granularity = "files" | "classes";

const EDGE_COLOR: Record<string, string> = {
  CONTAINS: "#7a8488",
  INHERITS: "#4f8ac1",
  USES: "#c1832f",
};

export function GraphView({ repoId }: { repoId: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const selectedRef = useRef<GraphNode | null>(null);
  const [granularity, setGranularity] = useState<Granularity>("files");
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [nodeCount, setNodeCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [relationship, setRelationship] = useState<RelationshipResponse | null>(null);
  const [relationshipLoading, setRelationshipLoading] = useState(false);
  const [relationshipError, setRelationshipError] = useState<string | null>(null);

  function selectNode(node: GraphNode | null) {
    selectedRef.current = node;
    setSelected(node);
    setRelationship(null);
    setRelationshipError(null);
  }

  const compareNodes = useCallback(
    async (a: GraphNode, b: GraphNode) => {
      selectNode(null);
      setRelationshipLoading(true);
      setRelationshipError(null);
      try {
        const res = await api.getRelationship(repoId, a.uid, b.uid);
        setRelationship(res);
      } catch (err) {
        setRelationshipError(err instanceof Error ? err.message : "Failed to load relationship.");
      } finally {
        setRelationshipLoading(false);
      }
    },
    [repoId],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    selectNode(null);

    api
      .getGraph(repoId, granularity)
      .then((view) => {
        if (cancelled || !containerRef.current) return;
        setTruncated(view.truncated);
        setNodeCount(view.nodes.length);
        setLoading(false);

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
                "font-size": 10,
                color: "#aab3b7",
                "text-valign": "bottom",
                "text-margin-y": 5,
                width: "mapData(degree, 0, 20, 18, 50)",
                height: "mapData(degree, 0, 20, 18, 50)",
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
                "arrow-scale": 0.8,
                "curve-style": "bezier",
                opacity: 0.55,
              },
            },
            {
              selector: "node:selected",
              style: { "border-width": 3, "border-color": "#e3b473" },
            },
          ],
          layout: {
            name: "cose",
            animate: false,
            padding: 40,
            nodeRepulsion: () => 12000,
            idealEdgeLength: () => 90,
            componentSpacing: 80,
            nodeOverlap: 16,
          } as cytoscape.LayoutOptions,
        });

        cy.on("tap", "node", (evt) => {
          const uid = evt.target.id();
          const node = nodesByUid.get(uid);
          if (!node) return;

          const original = evt.originalEvent as MouseEvent | undefined;
          const isCompareClick = original?.ctrlKey || original?.metaKey;
          const current = selectedRef.current;

          if (isCompareClick && current && current.uid !== node.uid) {
            void compareNodes(current, node);
          } else {
            selectNode(node);
          }
        });
        cy.on("tap", (evt) => {
          if (evt.target === cy) {
            selectNode(null);
          }
        });

        cyRef.current = cy;
      })
      .catch((err) => {
        setLoading(false);
        setError(err instanceof Error ? err.message : "Failed to load graph.");
      });

    return () => {
      cancelled = true;
      cyRef.current?.destroy();
      cyRef.current = null;
    };
  }, [repoId, granularity, compareNodes]);

  if (error) return <p className="form-error">{error}</p>;

  return (
    <div className="graph-view">
      <div className="graph-toolbar">
        <div className="granularity-toggle">
          <button
            className={granularity === "files" ? "gtoggle active" : "gtoggle"}
            onClick={() => setGranularity("files")}
          >
            Files
          </button>
          <button
            className={granularity === "classes" ? "gtoggle active" : "gtoggle"}
            onClick={() => setGranularity("classes")}
          >
            Files + classes
          </button>
        </div>
        <div className="graph-legend">
          {granularity === "classes" && (
            <>
              <span><i className="dot dot-file" /> File</span>
              <span><i className="dot dot-class" /> Class</span>
              <span><i className="line line-contains" /> Contains</span>
              <span><i className="line line-inherits" /> Inherits</span>
            </>
          )}
          {granularity === "files" && <span><i className="dot dot-file" /> File</span>}
          <span><i className="line line-uses" /> Uses</span>
        </div>
      </div>

      <p className="graph-caption">
        {granularity === "files"
          ? "Each node is a file; a line means a function in one calls a function in the other. Isolated files with no cross-file calls are hidden."
          : "Files and the classes they define, with containment, inheritance, and aggregated call relationships between classes."}
        {truncated && ` Showing the ${nodeCount} most-connected symbols.`}
        {" "}Select a node, then Ctrl/Cmd-click a second node to explain how they're connected.
      </p>

      <div className="graph-canvas-wrap">
        {loading && <div className="graph-loading">Loading graph…</div>}
        <div className="graph-canvas" ref={containerRef} />
      </div>

      {selected && (
        <div className="graph-detail">
          <button className="graph-detail-close" onClick={() => selectNode(null)}>×</button>
          <span className="symbol-tag">{selected.symbol_type}</span>
          <code>{selected.qualified_name}</code>
          <div className="evidence-location">
            {selected.file_path}:{selected.start_line}-{selected.end_line}
          </div>
          <div className="graph-detail-degree">{selected.degree} connections</div>
        </div>
      )}

      {relationshipLoading && (
        <div className="graph-detail">
          <p className="graph-relationship-status">Explaining relationship…</p>
        </div>
      )}

      {relationshipError && (
        <div className="graph-detail">
          <button className="graph-detail-close" onClick={() => setRelationshipError(null)}>×</button>
          <p className="form-error">{relationshipError}</p>
        </div>
      )}

      {relationship && (
        <div className="graph-detail graph-relationship">
          <button className="graph-detail-close" onClick={() => setRelationship(null)}>×</button>
          <div className="relationship-pair">
            <code>{relationship.source.qualified_name}</code>
            <span className="relationship-arrow">↔</span>
            <code>{relationship.target.qualified_name}</code>
          </div>
          <p className="relationship-explanation">{relationship.explanation}</p>
          {relationship.connected && relationship.steps.length > 0 && (
            <ul className="relationship-steps">
              {relationship.steps.map((step, i) => (
                <li key={i}>
                  <code>{step.from_qualified_name}</code>
                  <span className="relationship-rel-type">{step.relationship_type}</span>
                  <code>{step.to_qualified_name}</code>
                  {step.source_file && (
                    <div className="evidence-location">
                      {step.source_file}
                      {step.source_line ? `:${step.source_line}` : ""}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
