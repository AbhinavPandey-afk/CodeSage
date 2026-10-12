import type {
  ArchitectureComponent,
  ArchitectureModel,
  AskResponse,
  EntryPoint,
  ExecutionFlowReport,
  GraphViewResponse,
  HistoryReport,
  ImpactReport,
  OptimizationReport,
  RelationshipResponse,
  Repository,
  Smell,
  SymbolSearchResult,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

/** `third_party_dependencies` was added to ArchitectureComponent after this
 * endpoint shipped; a repository analyzed (or a backend process started)
 * before that additive change can still omit the key or send it as
 * null/undefined. Normalize to [] at the API boundary so every consumer
 * (aggregateExternalDependencies, ArchitectureList, ComponentCard,
 * ComponentInspector) can rely on the type it's already declared as. */
function normalizeArchitectureModel(model: ArchitectureModel): ArchitectureModel {
  return {
    ...model,
    components: model.components.map(
      (c): ArchitectureComponent => ({
        ...c,
        third_party_dependencies: Array.isArray(c.third_party_dependencies) ? c.third_party_dependencies : [],
      }),
    ),
  };
}

export const api = {
  createRepository: (url: string) =>
    request<Repository>("/api/repositories", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  getRepository: (id: string) => request<Repository>(`/api/repositories/${id}`),

  listRepositories: () => request<Repository[]>("/api/repositories"),

  ask: (id: string, question: string) =>
    request<AskResponse>(`/api/repositories/${id}/ask`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),

  getSmells: (id: string) => request<Smell[]>(`/api/repositories/${id}/smells`),

  getGraph: (id: string, granularity: "files" | "classes" = "files") =>
    request<GraphViewResponse>(`/api/repositories/${id}/graph?granularity=${granularity}`),

  getRelationship: (id: string, sourceUid: string, targetUid: string) =>
    request<RelationshipResponse>(`/api/repositories/${id}/graph/relationship`, {
      method: "POST",
      body: JSON.stringify({ source_uid: sourceUid, target_uid: targetUid }),
    }),

  searchSymbols: (id: string, q: string) =>
    request<SymbolSearchResult[]>(`/api/repositories/${id}/symbols?q=${encodeURIComponent(q)}`),

  getSymbolSuggestions: (id: string) =>
    request<SymbolSearchResult[]>(`/api/repositories/${id}/symbols/suggestions`),

  getImpact: (id: string, symbolUid: string) =>
    request<ImpactReport>(`/api/repositories/${id}/impact`, {
      method: "POST",
      body: JSON.stringify({ symbol_uid: symbolUid }),
    }),

  getArchitecture: (id: string) =>
    request<ArchitectureModel>(`/api/repositories/${id}/architecture`).then(normalizeArchitectureModel),

  getOptimization: (id: string) => request<OptimizationReport>(`/api/repositories/${id}/optimization`),

  getEntryPoints: (id: string) => request<EntryPoint[]>(`/api/repositories/${id}/flows`),

  reconstructFlow: (id: string, entryUid: string) =>
    request<ExecutionFlowReport>(`/api/repositories/${id}/flows/reconstruct`, {
      method: "POST",
      body: JSON.stringify({ entry_uid: entryUid }),
    }),

  getHistory: (id: string) => request<HistoryReport>(`/api/repositories/${id}/history`),
};
