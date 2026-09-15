import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/api/client";
import type { SymbolSearchResult } from "@/api/types";

export function SymbolSearch({
  repoId,
  value,
  onSelect,
}: {
  repoId: string;
  value: string;
  onSelect: (symbol: SymbolSearchResult) => void;
}) {
  const [query, setQuery] = useState(value);
  const [results, setResults] = useState<SymbolSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [suggestions, setSuggestions] = useState<SymbolSearchResult[]>([]);

  useEffect(() => {
    api.getSymbolSuggestions(repoId).then(setSuggestions).catch(() => setSuggestions([]));
  }, [repoId]);

  useEffect(() => {
    if (!query.trim() || query === value) {
      setResults([]);
      return;
    }
    setSearching(true);
    const handle = setTimeout(() => {
      api
        .searchSymbols(repoId, query)
        .then(setResults)
        .catch(() => setResults([]))
        .finally(() => setSearching(false));
    }, 250);
    return () => clearTimeout(handle);
  }, [query, repoId, value]);

  const choose = (s: SymbolSearchResult) => {
    setQuery(s.qualified_name);
    setResults([]);
    onSelect(s);
  };

  return (
    <div>
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-(--text-faint)" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search a function, method, or class in this repository…"
          className="h-11 w-full rounded-md border border-(--border) bg-(--bg-raised) pr-4 pl-10 text-sm text-(--text) placeholder:text-(--text-faint) focus:border-(--accent) focus:outline-none"
        />
        {searching && (
          <span className="absolute top-1/2 right-3 -translate-y-1/2 text-xs text-(--text-faint)">searching…</span>
        )}
        {results.length > 0 && (
          <ul className="absolute top-full right-0 left-0 z-20 mt-1 max-h-72 overflow-y-auto rounded-md border border-(--border) bg-(--bg-raised) py-1 shadow-lg">
            {results.map((r) => (
              <li key={r.uid}>
                <button
                  onClick={() => choose(r)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-(--bg-sunken)"
                >
                  <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.62rem] text-(--text-faint) uppercase">
                    {r.symbol_type}
                  </span>
                  <code className="min-w-0 truncate text-(--text)">{r.qualified_name}</code>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {suggestions.length > 0 && (
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-(--text-faint)">Try:</span>
          {suggestions.map((s) => (
            <button
              key={s.uid}
              onClick={() => choose(s)}
              className="rounded-full border border-(--border) bg-(--bg-raised) px-2.5 py-1 font-mono text-xs text-(--text-soft) hover:border-(--accent)/40 hover:text-(--accent-text)"
            >
              {s.qualified_name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
