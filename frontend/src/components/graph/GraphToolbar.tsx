import { GitCompareArrows, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import type { GraphNode } from "@/api/types";
import { cn } from "@/lib/utils";

type Granularity = "files" | "classes";

export function GraphToolbar({
  granularity,
  onGranularityChange,
  nodes,
  onJumpToNode,
  relationshipTypes,
  hiddenTypes,
  onToggleType,
  selectedNode,
  onCompare,
}: {
  granularity: Granularity;
  onGranularityChange: (g: Granularity) => void;
  nodes: GraphNode[];
  onJumpToNode: (uid: string) => void;
  relationshipTypes: string[];
  hiddenTypes: Set<string>;
  onToggleType: (type: string) => void;
  /** When set, search results offer "Compare" as well as "jump to" — the
   * keyboard/pointer-friendly alternative to Ctrl/Cmd-click (PART 16/23). */
  selectedNode: GraphNode | null;
  onCompare: (node: GraphNode) => void;
}) {
  const [query, setQuery] = useState("");

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return nodes.filter((n) => n.qualified_name.toLowerCase().includes(q) || n.name.toLowerCase().includes(q)).slice(0, 8);
  }, [query, nodes]);

  return (
    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-2.5">
        <div className="inline-flex overflow-hidden rounded-md border border-(--border)">
          <button
            onClick={() => onGranularityChange("files")}
            aria-pressed={granularity === "files"}
            className={cn(
              "px-2.5 py-1.5 text-xs font-medium",
              granularity === "files" ? "bg-(--accent-soft) text-(--accent-text)" : "bg-(--bg-raised) text-(--text-faint)",
            )}
          >
            Files
          </button>
          <button
            onClick={() => onGranularityChange("classes")}
            aria-pressed={granularity === "classes"}
            className={cn(
              "border-l border-(--border) px-2.5 py-1.5 text-xs font-medium",
              granularity === "classes" ? "bg-(--accent-soft) text-(--accent-text)" : "bg-(--bg-raised) text-(--text-faint)",
            )}
          >
            Files + classes
          </button>
        </div>

        {relationshipTypes.length > 0 && (
          <div className="flex flex-wrap items-center gap-1">
            {relationshipTypes.map((t) => (
              <button
                key={t}
                onClick={() => onToggleType(t)}
                aria-pressed={!hiddenTypes.has(t)}
                className={cn(
                  "rounded-full border px-2 py-0.5 font-mono text-[0.65rem] font-medium tracking-wide uppercase transition-colors",
                  hiddenTypes.has(t)
                    ? "border-(--border) text-(--text-faint) opacity-50"
                    : "border-(--accent)/30 bg-(--accent-soft) text-(--accent-text)",
                )}
              >
                {t}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="relative w-full sm:w-56">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-(--text-faint)" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search files, classes, symbols…"
          className="h-8 w-full rounded-md border border-(--border) bg-(--bg-raised) pr-7 pl-8 text-xs text-(--text) placeholder:text-(--text-faint) focus:border-(--accent) focus:outline-none"
        />
        {query && (
          <button
            onClick={() => setQuery("")}
            aria-label="Clear search"
            className="absolute top-1/2 right-2 -translate-y-1/2 text-(--text-faint) hover:text-(--text)"
          >
            <X className="size-3.5" />
          </button>
        )}
        {results.length > 0 && (
          <ul className="absolute top-full right-0 left-0 z-20 mt-1 max-h-60 overflow-y-auto rounded-md border border-(--border) bg-(--bg-raised) py-1 shadow-lg">
            {results.map((n) => {
              const canCompare = selectedNode && selectedNode.uid !== n.uid;
              return (
                <li key={n.uid} className="flex items-center gap-1 px-1">
                  <button
                    onClick={() => {
                      onJumpToNode(n.uid);
                      setQuery("");
                    }}
                    className="flex min-w-0 flex-1 items-center gap-1.5 rounded px-1.5 py-1.5 text-left text-xs hover:bg-(--bg-sunken)"
                  >
                    <span className="shrink-0 rounded bg-(--bg-sunken) px-1 py-0.5 font-mono text-[0.6rem] text-(--text-faint) uppercase">
                      {n.symbol_type}
                    </span>
                    <code className="min-w-0 truncate text-(--text)">{n.qualified_name}</code>
                  </button>
                  {canCompare && (
                    <button
                      onClick={() => {
                        onCompare(n);
                        setQuery("");
                      }}
                      title="Compare with the selected node"
                      className="flex shrink-0 items-center gap-1 rounded-md border border-(--accent)/30 bg-(--accent-soft) px-1.5 py-1 font-mono text-[0.6rem] font-semibold tracking-wide text-(--accent-text) uppercase hover:bg-(--accent)/20"
                    >
                      <GitCompareArrows className="size-3" /> Compare
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
