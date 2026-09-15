import cytoscape, { type Core } from "cytoscape";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { GraphNode, RelationshipResponse } from "../api/types";
import { GraphToolbar } from "@/components/graph/GraphToolbar";
import { NodeInspector } from "@/components/graph/NodeInspector";
import { RelationshipTrail } from "@/components/graph/RelationshipTrail";
import { useInvestigation } from "@/lib/investigation";

type Granularity = "files" | "classes";

function resolveVar(el: Element, name: string): string {
  return getComputedStyle(el).getPropertyValue(name).trim() || "#999";
}

const TYPE_VAR: Record<string, string> = {
  CONTAINS: "--text-faint",
  INHERITS: "--slate",
  USES: "--accent",
  IMPORTS: "--bronze",
  CALLS: "--accent",
};

export function GraphView({ repoId }: { repoId: string }) {
  const { focus } = useInvestigation();
  // GraphView remounts whenever the user navigates to this tab (App.tsx only
  // renders it while active), so the focus value at first render is exactly
  // whatever navigate() carried in — safe to capture once and never re-apply.
  const initialFocusRef = useRef(focus);

  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const selectedRef = useRef<GraphNode | null>(null);
  const nodesRef = useRef<GraphNode[]>([]);
  const uidByNameRef = useRef<Map<string, string>>(new Map());

  const [granularity, setGranularity] = useState<Granularity>("files");
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [nodeCount, setNodeCount] = useState(0);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [relationshipTypes, setRelationshipTypes] = useState<string[]>([]);
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());
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

  const applyFocus = useCallback((cy: Core, centerId: string) => {
    const center = cy.getElementById(centerId);
    if (center.empty()) return;
    const neighborhood = center.closedNeighborhood();
    cy.elements().addClass("faded");
    neighborhood.removeClass("faded");
  }, []);

  const highlightPath = useCallback((cy: Core, uids: string[]) => {
    const nodesToKeep = cy.collection();
    for (const uid of uids) nodesToKeep.merge(cy.getElementById(uid));
    const edgesToKeep = nodesToKeep.edgesWith(nodesToKeep);
    cy.elements().addClass("faded");
    nodesToKeep.union(edgesToKeep).removeClass("faded");
  }, []);

  const compareNodes = useCallback(
    async (a: GraphNode, b: GraphNode) => {
      selectedRef.current = null;
      setSelected(null);
      setRelationshipLoading(true);
      setRelationshipError(null);
      try {
        const res = await api.getRelationship(repoId, a.uid, b.uid);
        setRelationship(res);
        if (cyRef.current) {
          if (res.connected) {
            const uids = new Set<string>([a.uid, b.uid]);
            for (const step of res.steps) {
              const fromUid = uidByNameRef.current.get(step.from_qualified_name);
              const toUid = uidByNameRef.current.get(step.to_qualified_name);
              if (fromUid) uids.add(fromUid);
              if (toUid) uids.add(toUid);
            }
            highlightPath(cyRef.current, [...uids]);
          } else {
            cyRef.current.elements().removeClass("faded");
          }
        }
      } catch (err) {
        setRelationshipError(err instanceof Error ? err.message : "Failed to load relationship.");
      } finally {
        setRelationshipLoading(false);
      }
    },
    [repoId, highlightPath],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    selectNode(null);
    setHiddenTypes(new Set());

    api
      .getGraph(repoId, granularity)
      .then((view) => {
        if (cancelled || !containerRef.current) return;
        const container = containerRef.current;
        setTruncated(view.truncated);
        setNodeCount(view.nodes.length);
        setNodes(view.nodes);
        nodesRef.current = view.nodes;
        uidByNameRef.current = new Map(view.nodes.map((n) => [n.qualified_name, n.uid]));
        setRelationshipTypes([...new Set(view.edges.map((e) => e.relationship_type))].sort());
        setLoading(false);

        const nodesByUid = new Map(view.nodes.map((n) => [n.uid, n]));
        const c = (name: string) => resolveVar(container, name);

        const elements = [
          ...view.nodes.map((n) => ({
            data: { id: n.uid, label: n.name, type: n.symbol_type, degree: n.degree },
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
          container,
          elements,
          style: [
            {
              selector: "node",
              style: {
                label: "data(label)",
                "font-size": 10,
                color: c("--text-soft"),
                "text-valign": "bottom",
                "text-margin-y": 5,
                width: "mapData(degree, 0, 20, 18, 50)",
                height: "mapData(degree, 0, 20, 18, 50)",
                "background-color": c("--accent"),
                "border-width": 1,
                "border-color": c("--accent-text"),
              },
            },
            {
              selector: "node[type = 'file']",
              style: { "background-color": c("--slate"), "border-color": c("--slate"), shape: "round-rectangle" },
            },
            {
              selector: "edge",
              style: {
                width: "mapData(weight, 1, 10, 1, 5)",
                "line-color": (ele) => c(TYPE_VAR[ele.data("type")] ?? "--text-faint"),
                "target-arrow-color": (ele) => c(TYPE_VAR[ele.data("type")] ?? "--text-faint"),
                "target-arrow-shape": "triangle",
                "arrow-scale": 0.8,
                "curve-style": "bezier",
                opacity: 0.55,
              },
            },
            { selector: ".faded", style: { opacity: 0.08 } },
            { selector: "node:selected", style: { "border-width": 3, "border-color": c("--accent-text") } },
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
            applyFocus(cy, node.uid);
          }
        });
        cy.on("tap", (evt) => {
          if (evt.target === cy) {
            selectNode(null);
            cy.elements().removeClass("faded");
          }
        });

        cyRef.current = cy;

        const wantedName = initialFocusRef.current?.qualifiedName;
        if (wantedName) {
          const match = view.nodes.find((n) => n.qualified_name === wantedName);
          if (match) {
            selectNode(match);
            applyFocus(cy, match.uid);
            cy.animate({ center: { eles: cy.getElementById(match.uid) }, zoom: 1.4 }, { duration: 300 });
          }
        }

        const resizeObserver = new ResizeObserver(() => {
          cy.resize();
        });
        resizeObserver.observe(container);
        cy.one("destroy", () => resizeObserver.disconnect());
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
  }, [repoId, granularity, compareNodes, applyFocus]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.edges().forEach((e) => {
      e.style("display", hiddenTypes.has(e.data("type")) ? "none" : "element");
    });
  }, [hiddenTypes]);

  const toggleType = (type: string) => {
    setHiddenTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const jumpToNode = useCallback(
    (uid: string) => {
      const cy = cyRef.current;
      const node = nodesRef.current.find((n) => n.uid === uid);
      if (!cy || !node) return;
      const ele = cy.getElementById(uid);
      if (ele.empty()) return;
      selectNode(node);
      applyFocus(cy, uid);
      cy.animate({ center: { eles: ele }, zoom: Math.max(cy.zoom(), 1.4) }, { duration: 300 });
    },
    [applyFocus],
  );

  const legendTypes = useMemo(() => relationshipTypes, [relationshipTypes]);

  if (error) return <p className="text-sm text-(--bad)">{error}</p>;

  return (
    <div>
      <p className="mb-4 max-w-2xl text-sm text-(--text-soft)">
        {granularity === "files"
          ? "Each node is a file; an edge means a function in one calls a function in the other. Isolated files with no cross-file calls are hidden."
          : "Files and the classes they define, with containment, inheritance, and aggregated call relationships between classes."}
        {truncated && ` Showing the ${nodeCount} most-connected symbols.`} Select a node to focus its
        neighborhood, then Ctrl/Cmd-click a second node to investigate how they're connected.
      </p>

      <GraphToolbar
        granularity={granularity}
        onGranularityChange={setGranularity}
        nodes={nodes}
        onJumpToNode={jumpToNode}
        relationshipTypes={legendTypes}
        hiddenTypes={hiddenTypes}
        onToggleType={toggleType}
      />

      <div className="relative">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center rounded-lg border border-(--border) bg-(--bg-raised) text-sm text-(--text-faint)">
            Loading graph…
          </div>
        )}
        <div ref={containerRef} className="h-[520px] rounded-lg border border-(--border) bg-(--bg-raised)" />

        {selected && !relationship && !relationshipLoading && (
          <NodeInspector node={selected} onClose={() => selectNode(null)} />
        )}

        {relationshipLoading && (
          <div className="absolute top-3 right-3 z-10 rounded-lg border border-(--border) bg-(--bg-raised) px-4 py-3 text-sm text-(--text-faint) shadow-lg">
            Investigating relationship…
          </div>
        )}

        {relationshipError && (
          <div className="absolute top-3 right-3 z-10 w-64 rounded-lg border border-(--bad)/30 bg-(--bg-raised) px-4 py-3 shadow-lg">
            <p className="text-sm text-(--bad)">{relationshipError}</p>
          </div>
        )}

        {relationship && (
          <RelationshipTrail
            relationship={relationship}
            onClose={() => {
              setRelationship(null);
              cyRef.current?.elements().removeClass("faded");
            }}
          />
        )}
      </div>
    </div>
  );
}
