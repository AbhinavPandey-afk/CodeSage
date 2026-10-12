import cytoscape, { type Core } from "cytoscape";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { ArchitectureModel, GraphEdge, GraphNode, RelationshipResponse, Smell } from "../api/types";
import { GraphToolbar } from "@/components/graph/GraphToolbar";
import { NodeInspector } from "@/components/graph/NodeInspector";
import { RelationshipInvestigation } from "@/components/graph/RelationshipInvestigation";
import { SelectionStateBar } from "@/components/graph/SelectionStateBar";
import { componentForFile, findingsForFile } from "@/lib/evidenceExplorer";
import { useInvestigation } from "@/lib/investigation";
import { cn } from "@/lib/utils";

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

/** Evidence Explorer (CLAUDE.md §24 Interactive Evidence Explorer, PART 2):
 * EXPLORE (browse the graph, inspect one entity) and INVESTIGATE (two
 * entities selected, relationship evidence) are the same page, distinguished
 * by state rather than a literal tab — `primary`/`secondary` below are that
 * state. The graph itself, its layout/styling, and the relationship
 * resolver are untouched; this component only adds the surrounding
 * investigation surface (inspector, relationship panel, search-compare,
 * visible selection state). */
export function GraphView({ repoId }: { repoId: string }) {
  const { focus } = useInvestigation();
  // GraphView remounts whenever the user navigates to this tab (App.tsx only
  // renders it while active), so the focus value at first render is exactly
  // whatever navigate() carried in — safe to capture once and never re-apply.
  const initialFocusRef = useRef(focus);

  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const primaryRef = useRef<GraphNode | null>(null);
  const nodesRef = useRef<GraphNode[]>([]);
  const uidByNameRef = useRef<Map<string, string>>(new Map());

  const [granularity, setGranularity] = useState<Granularity>("files");
  const [primary, setPrimaryState] = useState<GraphNode | null>(null);
  const [secondary, setSecondary] = useState<GraphNode | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [nodeCount, setNodeCount] = useState(0);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [relationshipTypes, setRelationshipTypes] = useState<string[]>([]);
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [relationship, setRelationship] = useState<RelationshipResponse | null>(null);
  const [relationshipLoading, setRelationshipLoading] = useState(false);
  const [relationshipError, setRelationshipError] = useState<string | null>(null);

  // Reconstruction context for the inspector/investigation panels (PART 3/15) —
  // reused as-is from their own existing endpoints, not recomputed here.
  const [architecture, setArchitecture] = useState<ArchitectureModel | null>(null);
  const [smells, setSmells] = useState<Smell[]>([]);

  useEffect(() => {
    let cancelled = false;
    api
      .getArchitecture(repoId)
      .then((a) => !cancelled && setArchitecture(a))
      .catch(() => !cancelled && setArchitecture(null));
    api
      .getSmells(repoId)
      .then((s) => !cancelled && setSmells(s))
      .catch(() => !cancelled && setSmells([]));
    return () => {
      cancelled = true;
    };
  }, [repoId]);

  function setPrimary(node: GraphNode | null) {
    primaryRef.current = node;
    setPrimaryState(node);
  }

  /** Explore a single node — clears any active investigation. */
  function selectPrimary(node: GraphNode | null) {
    setPrimary(node);
    setSecondary(null);
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
      setPrimary(a);
      setSecondary(b);
      setRelationship(null);
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

  /** Exit INVESTIGATE, back to EXPLORE on whichever node was the source —
   * preserves context instead of resetting the whole page (PART 2/17). */
  const clearInvestigation = useCallback(() => {
    setSecondary(null);
    setRelationship(null);
    setRelationshipError(null);
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("faded");
    if (primaryRef.current) applyFocus(cy, primaryRef.current.uid);
  }, [applyFocus]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    selectPrimary(null);
    setHiddenTypes(new Set());

    api
      .getGraph(repoId, granularity)
      .then((view) => {
        if (cancelled || !containerRef.current) return;
        const container = containerRef.current;
        setTruncated(view.truncated);
        setNodeCount(view.nodes.length);
        setNodes(view.nodes);
        setEdges(view.edges);
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
          const current = primaryRef.current;

          if (isCompareClick && current && current.uid !== node.uid) {
            void compareNodes(current, node);
          } else {
            selectPrimary(node);
            applyFocus(cy, node.uid);
          }
        });
        cy.on("tap", (evt) => {
          if (evt.target === cy) {
            selectPrimary(null);
            cy.elements().removeClass("faded");
          }
        });

        cyRef.current = cy;

        const wantedName = initialFocusRef.current?.qualifiedName;
        const wantedComponentId = initialFocusRef.current?.componentId;
        if (wantedName) {
          const match = view.nodes.find((n) => n.qualified_name === wantedName);
          if (match) {
            selectPrimary(match);
            applyFocus(cy, match.uid);
            cy.animate({ center: { eles: cy.getElementById(match.uid) }, zoom: 1.4 }, { duration: 300 });
          }
        } else if (wantedComponentId) {
          // component_id IS a directory prefix (analysis/reconstruction/grouping.py's
          // group_key), so a component's member nodes can be matched directly by
          // file_path without a second API call back to the architecture endpoint.
          const matches = view.nodes.filter(
            (n) => n.file_path === wantedComponentId || n.file_path.startsWith(`${wantedComponentId}/`),
          );
          if (matches.length > 0) {
            const uids = matches.map((n) => n.uid);
            let collection = cy.collection();
            for (const uid of uids) collection = collection.union(cy.getElementById(uid));
            highlightPath(cy, uids);
            cy.animate({ fit: { eles: collection, padding: 40 } }, { duration: 300 });
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repoId, granularity, compareNodes, applyFocus, highlightPath]);

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

  /** Select-and-recenter — used by search "jump to", and by clicking a
   * neighbor in the inspector's incoming/outgoing lists. Starts a fresh
   * EXPLORE on that node (exits any active investigation). */
  const jumpToNode = useCallback(
    (uid: string) => {
      const cy = cyRef.current;
      const node = nodesRef.current.find((n) => n.uid === uid);
      if (!cy || !node) return;
      const ele = cy.getElementById(uid);
      if (ele.empty()) return;
      selectPrimary(node);
      applyFocus(cy, uid);
      cy.animate({ center: { eles: ele }, zoom: Math.max(cy.zoom(), 1.4) }, { duration: 300 });
    },
    [applyFocus],
  );

  /** Recenter on an intermediate path hop without leaving the investigation
   * (PART 9/10) — the path highlight stays exactly as the resolver returned
   * it; this only moves the camera. */
  const focusPathNode = useCallback((uid: string) => {
    const cy = cyRef.current;
    if (!cy) return;
    const ele = cy.getElementById(uid);
    if (ele.empty()) return;
    cy.animate({ center: { eles: ele }, zoom: Math.max(cy.zoom(), 1.4) }, { duration: 300 });
  }, []);

  const resolveUid = useCallback(
    (qualifiedName: string): string | null => {
      if (relationship?.source.qualified_name === qualifiedName) return relationship.source.uid;
      if (relationship?.target.qualified_name === qualifiedName) return relationship.target.uid;
      return uidByNameRef.current.get(qualifiedName) ?? null;
    },
    [relationship],
  );

  const handleCompareFromSearch = useCallback(
    (node: GraphNode) => {
      if (!primaryRef.current || primaryRef.current.uid === node.uid) return;
      void compareNodes(primaryRef.current, node);
    },
    [compareNodes],
  );

  const nodesByUid = useMemo(() => new Map(nodes.map((n) => [n.uid, n])), [nodes]);
  const primaryComponent = useMemo(
    () => (primary && architecture ? componentForFile(architecture.components, primary.file_path) : null),
    [primary, architecture],
  );
  const primaryFindings = useMemo(() => (primary ? findingsForFile(smells, primary.file_path) : []), [primary, smells]);

  const investigating = secondary !== null || relationshipLoading || relationship !== null || relationshipError !== null;
  const showInspector = primary !== null && !investigating;

  const legendTypes = useMemo(() => relationshipTypes, [relationshipTypes]);

  if (error) return <p className="text-sm text-(--bad)">{error}</p>;

  return (
    <div>
      <p className="mb-4 max-w-2xl text-sm text-(--text-soft)">
        {granularity === "files"
          ? "Each node is a file; an edge means a function in one calls a function in the other. Isolated files with no cross-file calls are hidden."
          : "Files and the classes they define, with containment, inheritance, and aggregated call relationships between classes."}
        {truncated && ` Showing the ${nodeCount} most-connected symbols.`}
      </p>

      <GraphToolbar
        granularity={granularity}
        onGranularityChange={setGranularity}
        nodes={nodes}
        onJumpToNode={jumpToNode}
        relationshipTypes={legendTypes}
        hiddenTypes={hiddenTypes}
        onToggleType={toggleType}
        selectedNode={primary}
        onCompare={handleCompareFromSearch}
      />

      <SelectionStateBar primary={primary} secondary={secondary} investigating={investigating} onClear={clearInvestigation} />

      <div className={cn("grid gap-4", showInspector ? "lg:grid-cols-[1fr_320px]" : "grid-cols-1")}>
        <div className="relative min-w-0">
          {loading && (
            <div className="absolute inset-0 z-10 flex items-center justify-center rounded-lg border border-(--border) bg-(--bg-raised) text-sm text-(--text-faint)">
              Loading graph…
            </div>
          )}
          <div ref={containerRef} className="h-[520px] rounded-lg border border-(--border) bg-(--bg-raised)" />
        </div>

        {showInspector && primary && (
          <div className="h-[520px]">
            <NodeInspector
              node={primary}
              edges={edges}
              nodesByUid={nodesByUid}
              component={primaryComponent}
              findings={primaryFindings}
              onClose={() => selectPrimary(null)}
              onJumpToNode={jumpToNode}
            />
          </div>
        )}
      </div>

      {relationshipLoading && (
        <div className="mt-4 rounded-lg border border-(--border) bg-(--bg-raised) px-4 py-3 text-sm text-(--text-faint)">
          Investigating relationship…
        </div>
      )}

      {relationshipError && (
        <div className="mt-4 rounded-lg border border-(--bad)/30 bg-(--bg-raised) px-4 py-3">
          <p className="text-sm text-(--bad)">{relationshipError}</p>
        </div>
      )}

      {relationship && (
        <div className="mt-4">
          <RelationshipInvestigation
            relationship={relationship}
            components={architecture?.components ?? []}
            smells={smells}
            resolveUid={resolveUid}
            onFocusNode={focusPathNode}
            onClose={clearInvestigation}
          />
        </div>
      )}
    </div>
  );
}
