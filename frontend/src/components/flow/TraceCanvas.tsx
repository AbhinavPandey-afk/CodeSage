import { ChevronsDownUp, ChevronsUpDown, Maximize2, Minus, Plus, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { defaultCollapsedIds, pathAround, type TraceNode } from "@/lib/flowModel";
import { cn } from "@/lib/utils";
import { TraceNodeCard, type CardVisualState } from "./TraceNodeCard";

const MIN_ZOOM = 0.55;
const MAX_ZOOM = 1.4;
const AUTO_COLLAPSE_DEPTH = 3;
const AUTO_COLLAPSE_THRESHOLD = 22;

function collectAllParentIds(node: TraceNode, out: string[] = []): string[] {
  if (node.children.length > 0) out.push(node.id);
  node.children.forEach((c) => collectAllParentIds(c, out));
  return out;
}

function TraceBranch({
  node,
  collapsedIds,
  onToggleCollapse,
  selectedId,
  highlightSet,
  onSelect,
}: {
  node: TraceNode;
  collapsedIds: Set<string>;
  onToggleCollapse: (id: string) => void;
  selectedId: string | null;
  highlightSet: Set<string> | null;
  onSelect: (id: string) => void;
}) {
  const isCollapsed = collapsedIds.has(node.id);
  const showChildren = !isCollapsed && node.children.length > 0;
  const state: CardVisualState = selectedId === node.id ? "selected" : highlightSet && !highlightSet.has(node.id) ? "faded" : "normal";

  return (
    <div id={`trace-node-${node.id}`} className="flex flex-col items-center">
      <TraceNodeCard
        node={node}
        state={state}
        collapsed={isCollapsed}
        onToggleCollapse={node.children.length > 0 ? () => onToggleCollapse(node.id) : null}
        onSelect={() => onSelect(node.id)}
      />

      {showChildren && (
        <>
          <div className="h-6 w-px bg-(--border-strong)" />
          <div className="flex flex-col items-stretch gap-6 sm:flex-row sm:items-start sm:gap-4">
            {node.children.map((child) => (
              <div
                key={child.id}
                className={cn(
                  "relative shrink-0 pt-6",
                  "after:absolute after:top-0 after:left-1/2 after:h-6 after:w-px after:-translate-x-1/2 after:bg-(--border-strong)",
                  "sm:before:absolute sm:before:top-0 sm:before:right-0 sm:before:left-0 sm:before:h-px sm:before:bg-(--border-strong)",
                  "sm:first:before:left-1/2 sm:last:before:right-1/2",
                )}
              >
                <TraceBranch
                  node={child}
                  collapsedIds={collapsedIds}
                  onToggleCollapse={onToggleCollapse}
                  selectedId={selectedId}
                  highlightSet={highlightSet}
                  onSelect={onSelect}
                />
              </div>
            ))}
          </div>
        </>
      )}

      {isCollapsed && node.children.length > 0 && (
        <p className="mt-2 text-[0.65rem] text-(--text-faint) italic">
          {node.children.length} step{node.children.length === 1 ? "" : "s"} hidden — click to expand
        </p>
      )}
    </div>
  );
}

export function TraceCanvas({
  tree,
  selectedId,
  onSelect,
}: {
  tree: TraceNode;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());
  const [zoom, setZoom] = useState(1);
  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const totalParents = collectAllParentIds(tree).length;
    setCollapsedIds(totalParents > 0 ? defaultCollapsedIds(tree, AUTO_COLLAPSE_DEPTH) : new Set());
    setZoom(1);
    // A fresh tree (new level/mode/entry point) resets the view rather than
    // carrying over collapse state that may no longer correspond to anything.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tree]);

  const highlightSet = useMemo(() => (selectedId ? pathAround(tree, selectedId) : null), [tree, selectedId]);
  const allParentIds = useMemo(() => collectAllParentIds(tree), [tree]);
  const isLarge = allParentIds.length > AUTO_COLLAPSE_THRESHOLD;

  const toggleCollapse = (id: string) => {
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const fitToView = () => {
    const scroll = scrollRef.current;
    const content = contentRef.current;
    if (!scroll || !content) return;
    // content.scrollWidth is measured on the transformed element itself, so
    // it already reflects its untransformed (natural, zoom=1) layout width —
    // CSS transforms don't change an element's own content-box size.
    const naturalWidth = content.scrollWidth;
    const nextZoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, (scroll.clientWidth - 32) / naturalWidth));
    setZoom(Number.isFinite(nextZoom) && nextZoom > 0 ? nextZoom : 1);
    scroll.scrollTo({ left: 0, top: 0 });
  };

  return (
    <div className="relative">
      <div className="absolute top-3 right-3 z-20 flex items-center gap-1 rounded-md border border-(--border) bg-(--bg-raised)/95 p-1 shadow-sm backdrop-blur-sm">
        <button
          type="button"
          onClick={() => setCollapsedIds(collapsedIds.size > 0 ? new Set() : new Set(allParentIds))}
          aria-label={collapsedIds.size > 0 ? "Expand all steps" : "Collapse all steps"}
          title={collapsedIds.size > 0 ? "Expand all" : "Collapse all"}
          className="flex size-7 items-center justify-center rounded text-(--text-faint) hover:bg-(--bg-sunken) hover:text-(--text)"
        >
          {collapsedIds.size > 0 ? <ChevronsUpDown className="size-3.5" /> : <ChevronsDownUp className="size-3.5" />}
        </button>
        <span className="h-4 w-px bg-(--border)" />
        <button
          type="button"
          onClick={() => setZoom((z) => Math.max(MIN_ZOOM, z - 0.15))}
          aria-label="Zoom out"
          title="Zoom out"
          className="flex size-7 items-center justify-center rounded text-(--text-faint) hover:bg-(--bg-sunken) hover:text-(--text)"
        >
          <Minus className="size-3.5" />
        </button>
        <span className="w-9 text-center font-mono text-[0.65rem] text-(--text-faint) tabular-nums">
          {Math.round(zoom * 100)}%
        </span>
        <button
          type="button"
          onClick={() => setZoom((z) => Math.min(MAX_ZOOM, z + 0.15))}
          aria-label="Zoom in"
          title="Zoom in"
          className="flex size-7 items-center justify-center rounded text-(--text-faint) hover:bg-(--bg-sunken) hover:text-(--text)"
        >
          <Plus className="size-3.5" />
        </button>
        <button
          type="button"
          onClick={fitToView}
          aria-label="Fit to view"
          title="Fit to view"
          className="flex size-7 items-center justify-center rounded text-(--text-faint) hover:bg-(--bg-sunken) hover:text-(--text)"
        >
          <Maximize2 className="size-3.5" />
        </button>
        <button
          type="button"
          onClick={() => {
            setZoom(1);
            scrollRef.current?.scrollTo({ left: 0, top: 0 });
          }}
          aria-label="Reset view"
          title="Reset view"
          className="flex size-7 items-center justify-center rounded text-(--text-faint) hover:bg-(--bg-sunken) hover:text-(--text)"
        >
          <RotateCcw className="size-3.5" />
        </button>
      </div>

      {isLarge && collapsedIds.size > 0 && (
        <p className="absolute top-3 left-3 z-20 max-w-[60%] rounded-md border border-(--border) bg-(--bg-raised)/95 px-2.5 py-1.5 text-[0.68rem] text-(--text-faint) backdrop-blur-sm">
          This trace has {allParentIds.length}+ steps — some branches start collapsed for readability.
        </p>
      )}

      <div
        ref={scrollRef}
        className="h-[560px] overflow-auto rounded-lg border border-(--border) bg-(--bg-inset) [background-image:radial-gradient(var(--border)_1px,transparent_1px)] [background-size:20px_20px]"
      >
        <div
          ref={contentRef}
          style={{ transform: `scale(${zoom})`, transformOrigin: "top center" }}
          className="flex min-w-full justify-center px-10 py-10"
        >
          <TraceBranch
            node={tree}
            collapsedIds={collapsedIds}
            onToggleCollapse={toggleCollapse}
            selectedId={selectedId}
            highlightSet={highlightSet}
            onSelect={onSelect}
          />
        </div>
      </div>
    </div>
  );
}
