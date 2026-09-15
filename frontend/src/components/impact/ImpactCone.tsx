import cytoscape from "cytoscape";
import { useEffect, useRef } from "react";
import type { Dependent } from "@/api/types";

const MAX_NODES = 60;

function resolveVar(el: Element, name: string): string {
  return getComputedStyle(el).getPropertyValue(name).trim() || "#999";
}

/**
 * Direct dependents connect to the target with a real edge (the backend
 * resolved that call). Indirect dependents only carry a `depth` number, not
 * which direct dependent they route through, so they're positioned by ring
 * distance only — drawing a specific connecting edge for them would invent
 * a path the graph never actually gave us.
 */
export function ImpactCone({
  targetName,
  direct,
  indirect,
}: {
  targetName: string;
  direct: Dependent[];
  indirect: Dependent[];
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  const combined = [...direct, ...indirect];
  const shown = combined.slice(0, MAX_NODES);
  const truncated = combined.length > MAX_NODES;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const c = (name: string) => resolveVar(container, name);
    const directUids = new Set(direct.map((d) => d.uid));

    const elements = [
      { data: { id: "__target__", label: targetName.split(".").pop() ?? targetName, ring: 0 } },
      ...shown.map((d) => ({
        data: { id: d.uid, label: d.name, ring: Math.max(1, d.depth) },
      })),
      ...shown.filter((d) => directUids.has(d.uid)).map((d) => ({ data: { id: `e-${d.uid}`, source: "__target__", target: d.uid } })),
    ];

    // Cytoscape's built-in concentric layout sizes ring radii mainly off
    // node count, not the actual (much larger) center node + its label —
    // that left ring-1 nodes overlapping the center's label. Positioning
    // explicitly guarantees real clearance regardless of node/label size.
    const RING_RADIUS = 110;
    const byRing = new Map<number, string[]>();
    for (const d of shown) {
      const ring = Math.max(1, d.depth);
      if (!byRing.has(ring)) byRing.set(ring, []);
      byRing.get(ring)!.push(d.uid);
    }
    const positions = new Map<string, { x: number; y: number }>([["__target__", { x: 0, y: 0 }]]);
    for (const [ring, uids] of byRing) {
      const radius = ring * RING_RADIUS;
      uids.forEach((uid, i) => {
        const angle = (2 * Math.PI * i) / uids.length - Math.PI / 2;
        positions.set(uid, { x: radius * Math.cos(angle), y: radius * Math.sin(angle) });
      });
    }

    const cy = cytoscape({
      container,
      elements,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "font-size": 9,
            color: c("--text-faint"),
            "text-valign": "bottom",
            "text-margin-y": 4,
            "text-wrap": "wrap",
            "text-max-width": "70px",
            width: 16,
            height: 16,
            "background-color": c("--slate"),
            "border-width": 1,
            "border-color": c("--bg-raised"),
          },
        },
        {
          selector: "#__target__",
          style: {
            "background-color": c("--accent"),
            width: 40,
            height: 40,
            "font-size": 11,
            "font-weight": 700,
            color: c("--text"),
          },
        },
        {
          selector: "edge",
          style: {
            width: 1,
            "line-color": c("--border-strong"),
            "curve-style": "straight",
            opacity: 0.6,
          },
        },
      ],
      layout: {
        name: "preset",
        positions: (node: cytoscape.NodeSingular) => positions.get(node.id()) ?? { x: 0, y: 0 },
        fit: true,
        padding: 30,
      } as cytoscape.LayoutOptions,
    });

    const resizeObserver = new ResizeObserver(() => {
      cy.resize();
      cy.fit(undefined, 20);
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      cy.destroy();
    };
  }, [targetName, direct, indirect, shown]);

  return (
    <div>
      <div ref={containerRef} className="h-[340px] rounded-lg border border-(--border) bg-(--bg-raised)" />
      <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-(--text-faint)">
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full bg-(--accent)" /> Selected symbol
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-(--slate)" /> Dependent (ring distance = call depth)
        </span>
        {truncated && <span>Showing the {MAX_NODES} nearest of {combined.length} dependents.</span>}
      </div>
    </div>
  );
}
