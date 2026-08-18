import type {
  AskResponse,
  GraphViewResponse,
  ImpactReport,
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

  searchSymbols: (id: string, q: string) =>
    request<SymbolSearchResult[]>(`/api/repositories/${id}/symbols?q=${encodeURIComponent(q)}`),

  getSymbolSuggestions: (id: string) =>
    request<SymbolSearchResult[]>(`/api/repositories/${id}/symbols/suggestions`),

  getImpact: (id: string, symbolUid: string) =>
    request<ImpactReport>(`/api/repositories/${id}/impact`, {
      method: "POST",
      body: JSON.stringify({ symbol_uid: symbolUid }),
    }),
};
