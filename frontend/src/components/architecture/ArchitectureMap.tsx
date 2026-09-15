import cytoscape, { type Core } from "cytoscape";
import { useEffect, useRef } from "react";
import type { ArchitectureModel, ComponentRole } from "@/api/types";

const ROLE_VAR: Partial<Record<ComponentRole, string>> = {
  api: "--accent",
  service: "--slate",
  data_access: "--bronze",
  external_integration: "--sage",
};
const DEFAULT_ROLE_VAR = "--text-faint";

export const ROLE_LEGEND: { role: ComponentRole; color: string }[] = [
  { role: "api", color: `var(${ROLE_VAR.api})` },
  { role: "service", color: `var(${ROLE_VAR.service})` },
  { role: "data_access", color: `var(${ROLE_VAR.data_access})` },
  { role: "external_integration", color: `var(${ROLE_VAR.external_integration})` },
];

/** Cytoscape's own style engine doesn't understand CSS `var(...)` syntax —
 * that's a browser/DOM feature, not something its stylesheet parser
 * implements — so tokens must be resolved to concrete colors first. */
function resolveVar(el: Element, name: string): string {
  return getComputedStyle(el).getPropertyValue(name).trim() || "#999";
}

export function ArchitectureMap({
  model,
  onSelect,
}: {
  model: ArchitectureModel;
  onSelect: (componentId: string | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const c = (name: string) => resolveVar(container, name);
    const roleColor = (role: ComponentRole) => c(ROLE_VAR[role] ?? DEFAULT_ROLE_VAR);

    const nameById = new Map(model.components.map((c) => [c.id, c.name]));
    const elements = [
      ...model.components.map((comp) => ({
        data: {
          id: comp.id,
          label: comp.name.length > 22 ? `…${comp.name.slice(-20)}` : comp.name,
          role: comp.role,
          symbolCount: comp.symbol_count,
        },
      })),
      ...model.relationships
        .filter((r) => nameById.has(r.source_id) && nameById.has(r.target_id))
        .map((r, i) => ({
          data: {
            id: `e${i}`,
            source: r.source_id,
            target: r.target_id,
            callCount: r.call_count,
            confidence: r.confidence_label,
          },
        })),
    ];

    const cy = cytoscape({
      container,
      elements,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "font-size": 11,
            "font-family": c("--mono"),
            color: c("--text-soft"),
            "text-valign": "bottom",
            "text-margin-y": 6,
            width: "mapData(symbolCount, 1, 80, 26, 64)",
            height: "mapData(symbolCount, 1, 80, 26, 64)",
            "background-color": c(DEFAULT_ROLE_VAR),
            "border-width": 2,
            "border-color": c("--bg"),
          },
        },
        ...(Object.keys(ROLE_VAR) as ComponentRole[]).map((role) => ({
          selector: `node[role = "${role}"]`,
          style: { "background-color": roleColor(role) },
        })),
        {
          selector: "edge",
          style: {
            width: "mapData(callCount, 1, 20, 1, 5)",
            "line-color": c("--text-faint"),
            "target-arrow-color": c("--text-faint"),
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.9,
            "curve-style": "bezier",
            opacity: 0.5,
          },
        },
        {
          selector: ".faded",
          style: { opacity: 0.12 },
        },
        {
          selector: "node:selected",
          style: { "border-width": 3, "border-color": c("--accent-text") },
        },
      ],
      layout: (() => {
        const roots = model.components.filter((comp) => comp.role === "api").map((comp) => comp.id);
        return roots.length > 0
          ? ({ name: "breadthfirst", directed: true, roots, spacingFactor: 1.5, padding: 30 } as cytoscape.LayoutOptions)
          : ({ name: "cose", animate: false, padding: 30, nodeRepulsion: () => 14000, idealEdgeLength: () => 100 } as cytoscape.LayoutOptions);
      })(),
    });

    cy.on("tap", "node", (evt) => {
      const id = evt.target.id();
      onSelect(id);
      const neighborhood = evt.target.closedNeighborhood();
      cy.elements().addClass("faded");
      neighborhood.removeClass("faded");
    });

    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        onSelect(null);
        cy.elements().removeClass("faded");
      }
    });

    cyRef.current = cy;

    const resizeObserver = new ResizeObserver(() => {
      cy.resize();
      cy.fit(undefined, 30);
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      cy.destroy();
      cyRef.current = null;
    };
  }, [model, onSelect]);

  return <div ref={containerRef} className="h-full w-full" />;
}
