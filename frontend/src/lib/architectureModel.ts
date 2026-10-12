/** Architecture is a reconstruction, not a second knowledge graph: this
 * module takes the existing ArchitectureModel (components + relationships,
 * already role-classified and evidence-backed by the backend) and derives a
 * higher-level model — layers, runtime-vs-supporting structure, and
 * aggregated external dependencies — purely from fields the backend already
 * returns. Nothing here queries Neo4j or invents new facts; every derived
 * field traces back to `component.role`, `component.id` (a real directory
 * path), or `component.third_party_dependencies`.
 */
import type { ArchitectureComponent, ArchitectureModel, ComponentRelationship, ComponentRole, ThirdPartyDependency } from "@/api/types";

export type StructureKind = "runtime" | "supporting";

interface LayerDef {
  name: string;
  purpose: string;
  order: number;
}

/** Generic, role-templated descriptions — not per-repository specifics, so
 * nothing here is invented beyond "what a component with this role
 * typically does", the same category of interpretation Execution Flow's
 * inspector already uses for its "why it matters" text. */
const LAYER_DEFS: Partial<Record<ComponentRole, LayerDef>> = {
  api: { name: "Presentation / API", purpose: "Receives incoming requests and routes them into the system.", order: 0 },
  service: { name: "Application / Service", purpose: "Coordinates business logic between the API and data access.", order: 1 },
  data_access: { name: "Data Access", purpose: "Reads and writes the system's persistent state.", order: 2 },
  external_integration: { name: "External Integration", purpose: "Bridges the system to services and libraries outside this repository.", order: 3 },
  model: { name: "Domain / Model", purpose: "Defines the data structures and schemas the system operates on.", order: 4 },
  other: { name: "Unclassified", purpose: "No decorator, naming, or import evidence matched a specific architectural role.", order: 5 },
};

export interface Layer {
  id: string;
  name: string;
  purpose: string;
  role: ComponentRole;
  /** Average confidence of member components — a layer is only as certain as the components in it. */
  confidence: number;
  componentIds: string[];
  evidence: string[];
}

/** role === "test" never becomes a layer — it's Supporting Structure,
 * handled separately (see classifyStructure). Everything else with at least
 * one component becomes one layer, ordered API -> Service -> Data ->
 * External -> Model -> Unclassified — an example ordering, not a forced
 * template: a repository with no "service"-role components simply has no
 * Application/Service layer, rather than an empty placeholder. */
export function deriveLayers(components: ArchitectureComponent[]): Layer[] {
  const byRole = new Map<ComponentRole, ArchitectureComponent[]>();
  for (const c of components) {
    if (c.role === "test") continue;
    if (!LAYER_DEFS[c.role]) continue;
    const list = byRole.get(c.role) ?? [];
    list.push(c);
    byRole.set(c.role, list);
  }

  const layers: Layer[] = [];
  for (const [role, members] of byRole) {
    const def = LAYER_DEFS[role]!;
    layers.push({
      id: `layer:${role}`,
      name: def.name,
      purpose: def.purpose,
      role,
      confidence: members.reduce((sum, c) => sum + c.confidence, 0) / members.length,
      componentIds: members.map((c) => c.id),
      evidence: [
        `${members.length} component${members.length === 1 ? "" : "s"} classified "${role}" — see each component's own evidence for the specific decorator, naming, or import signal that produced it.`,
      ],
    });
  }
  return layers.sort((a, b) => LAYER_DEFS[a.role]!.order - LAYER_DEFS[b.role]!.order);
}

// Exact directory-segment matches only — NOT substring containment. A
// substring check here (as CLAUDE.md's role-inference helper legitimately
// uses for things like "api"/"service", where "apis"/"services" should
// still match) is the wrong tool for this list: "script" as a substring
// matches inside "javascript", misclassifying a real examples/javascript
// component as scaffolding. Exact segment names avoid that collision.
const SUPPORTING_DIR_SEGMENTS = new Set([
  "doc", "docs", "documentation",
  "tool", "tools",
  "script", "scripts",
  "build",
  "benchmark", "benchmarks",
  ".github",
  "ci",
]);

/** role === "test" is always Supporting (already a deterministic backend
 * signal). Beyond that, only an unambiguous, exact directory-name match is
 * treated as Supporting — deliberately NOT "examples", since example apps
 * are often genuine runnable applications (and exactly what Execution Flow
 * traces), not scaffolding. Everything else defaults to Runtime rather than
 * guessing. */
export function classifyStructure(component: ArchitectureComponent): StructureKind {
  if (component.role === "test") return "supporting";
  const segments = component.id.toLowerCase().split("/");
  if (segments.some((seg) => SUPPORTING_DIR_SEGMENTS.has(seg))) return "supporting";
  return "runtime";
}

export interface AggregatedDependency extends ThirdPartyDependency {
  usedBy: string[];
}

/** Real package names, deduplicated across every component, with which
 * components import them. A self-referential name (matching this
 * repository's own package) can legitimately appear here — classify_import
 * has no way to know a dotted import refers to the very repo being
 * analyzed, a known, disclosed limitation, not a bug specific to this view. */
export function aggregateExternalDependencies(components: ArchitectureComponent[]): AggregatedDependency[] {
  const byName = new Map<string, AggregatedDependency>();
  for (const c of components) {
    const dependencies = Array.isArray(c.third_party_dependencies) ? c.third_party_dependencies : [];
    for (const dep of dependencies) {
      let entry = byName.get(dep.name);
      if (!entry) {
        entry = { name: dep.name, category: dep.category, usedBy: [] };
        byName.set(dep.name, entry);
      }
      entry.usedBy.push(c.id);
    }
  }
  return [...byName.values()].sort((a, b) => b.usedBy.length - a.usedBy.length);
}

export interface LayerTransition {
  sourceLayerId: string;
  targetLayerId: string;
  callCount: number;
}

/** Aggregates component-level relationships up to the layer they belong to,
 * so the diagram can show "12 calls" between two layer bands instead of
 * dozens of component-to-component lines — still built only from real
 * ComponentRelationship rows, just grouped one level higher. */
export function deriveLayerTransitions(layers: Layer[], relationships: ComponentRelationship[]): LayerTransition[] {
  const layerByComponentId = new Map<string, string>();
  for (const layer of layers) for (const id of layer.componentIds) layerByComponentId.set(id, layer.id);

  const totals = new Map<string, number>();
  for (const rel of relationships) {
    const sourceLayerId = layerByComponentId.get(rel.source_id);
    const targetLayerId = layerByComponentId.get(rel.target_id);
    if (!sourceLayerId || !targetLayerId || sourceLayerId === targetLayerId) continue;
    const key = `${sourceLayerId}->${targetLayerId}`;
    totals.set(key, (totals.get(key) ?? 0) + rel.call_count);
  }
  return [...totals.entries()].map(([key, callCount]) => {
    const [sourceLayerId, targetLayerId] = key.split("->");
    return { sourceLayerId, targetLayerId, callCount };
  });
}

export interface ArchitectureSummary {
  layerCount: number;
  runtimeComponentCount: number;
  supportingComponentCount: number;
  averageConfidence: number;
  externalDependencyCount: number;
}

export function summarize(model: ArchitectureModel, layers: Layer[], externalDeps: AggregatedDependency[]): ArchitectureSummary {
  const runtime = model.components.filter((c) => classifyStructure(c) === "runtime");
  const supporting = model.components.filter((c) => classifyStructure(c) === "supporting");
  const averageConfidence = model.components.length
    ? model.components.reduce((sum, c) => sum + c.confidence, 0) / model.components.length
    : 0;
  return {
    layerCount: layers.length,
    runtimeComponentCount: runtime.length,
    supportingComponentCount: supporting.length,
    averageConfidence,
    externalDependencyCount: externalDeps.length,
  };
}
