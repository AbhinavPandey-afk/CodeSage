import { ChevronDown, Route, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { EntryPoint } from "@/api/types";
import { parseRouteHint } from "@/lib/routeHint";
import { cn } from "@/lib/utils";

const METHOD_COLOR: Record<string, string> = {
  GET: "text-(--ok)",
  POST: "text-(--accent-text)",
  PUT: "text-(--warn)",
  PATCH: "text-(--warn)",
  DELETE: "text-(--bad)",
};

function shortName(qualifiedName: string): string {
  const parts = qualifiedName.split(".");
  return parts[parts.length - 1] || qualifiedName;
}

function EntrySummary({ entry, compact = false }: { entry: EntryPoint; compact?: boolean }) {
  const { method, path } = parseRouteHint(entry.route_hint);
  return (
    <span className="flex min-w-0 items-center gap-2 font-mono text-sm">
      {method ? (
        <span className={cn("shrink-0 text-xs font-bold", METHOD_COLOR[method] ?? "text-(--text-faint)")}>
          {method}
        </span>
      ) : (
        <Route className="size-3.5 shrink-0 text-(--text-faint)" />
      )}
      <span className="min-w-0 truncate text-(--text)">{path ?? entry.route_hint ?? shortName(entry.qualified_name)}</span>
      {!compact && (
        <span className="min-w-0 truncate text-(--text-faint)">{shortName(entry.qualified_name)}()</span>
      )}
    </span>
  );
}

export function EntryPointSelector({
  entryPoints,
  selected,
  onSelect,
}: {
  entryPoints: EntryPoint[];
  selected: EntryPoint | null;
  onSelect: (entry: EntryPoint) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return entryPoints;
    return entryPoints.filter((e) => {
      const { path } = parseRouteHint(e.route_hint);
      return (
        e.qualified_name.toLowerCase().includes(q) ||
        e.file_path.toLowerCase().includes(q) ||
        (e.route_hint ?? "").toLowerCase().includes(q) ||
        (path ?? "").toLowerCase().includes(q)
      );
    });
  }, [entryPoints, query]);

  useEffect(() => {
    if (!open) return;
    function onMouseDown(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [open]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => setActiveIndex(0), [query]);

  useEffect(() => {
    listRef.current?.children[activeIndex]?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  const choose = (entry: EntryPoint) => {
    onSelect(entry);
    setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      const entry = filtered[activeIndex];
      if (entry) choose(entry);
    }
  };

  return (
    <div ref={rootRef} className="relative w-full max-w-md">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex h-11 w-full items-center gap-2.5 rounded-md border border-(--border) bg-(--bg-raised) px-3.5 text-left transition-colors hover:border-(--accent)/40 focus:border-(--accent) focus:outline-none"
      >
        {selected ? (
          <EntrySummary entry={selected} />
        ) : (
          <span className="flex items-center gap-2 text-sm text-(--text-faint)">
            <Route className="size-4" /> Select an entry point…
          </span>
        )}
        <ChevronDown className={cn("ml-auto size-4 shrink-0 text-(--text-faint) transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="absolute top-full left-0 z-30 mt-1.5 w-full min-w-[22rem] overflow-hidden rounded-lg border border-(--border) bg-(--bg-raised) shadow-xl">
          <div className="relative border-b border-(--border)">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-(--text-faint)" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Search routes, functions, or files…"
              aria-label="Search entry points"
              className="h-11 w-full bg-transparent pr-3 pl-10 text-sm text-(--text) placeholder:text-(--text-faint) focus:outline-none"
            />
          </div>

          {filtered.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-(--text-faint)">No entry points match “{query}”.</p>
          ) : (
            <ul ref={listRef} role="listbox" className="max-h-80 overflow-y-auto py-1">
              {filtered.map((entry, i) => {
                const isActive = i === activeIndex;
                const isSelected = selected?.uid === entry.uid;
                return (
                  <li key={entry.uid} role="option" aria-selected={isSelected}>
                    <button
                      type="button"
                      onClick={() => choose(entry)}
                      onMouseEnter={() => setActiveIndex(i)}
                      className={cn(
                        "flex w-full flex-col gap-0.5 px-3.5 py-2 text-left transition-colors",
                        isActive ? "bg-(--bg-sunken)" : "",
                        isSelected && "bg-(--accent-soft)",
                      )}
                    >
                      <EntrySummary entry={entry} compact />
                      <span className="truncate font-mono text-[0.7rem] text-(--text-faint)">
                        {entry.file_path}:{entry.start_line}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
