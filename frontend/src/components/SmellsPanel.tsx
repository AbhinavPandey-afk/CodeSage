import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { ArchitectureModel, Severity, Smell } from "../api/types";
import { FindingCard } from "@/components/analysis/FindingCard";
import { SMELL_CATEGORY, SMELL_CATEGORY_LABELS, type SmellCategory } from "../lib/labels";
import { cn } from "@/lib/utils";

const DISPLAY_LIMIT = 40;

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-full border px-2.5 py-1 text-xs font-medium whitespace-nowrap transition-colors",
        active
          ? "border-(--accent)/40 bg-(--accent-soft) text-(--accent-text)"
          : "border-(--border) bg-(--bg-raised) text-(--text-faint) hover:text-(--text-soft)",
      )}
    >
      {children}
    </button>
  );
}

export function SmellsPanel({ repoId }: { repoId: string }) {
  const [smells, setSmells] = useState<Smell[] | null>(null);
  const [architecture, setArchitecture] = useState<ArchitectureModel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<Severity | "ALL">("ALL");
  const [categoryFilter, setCategoryFilter] = useState<SmellCategory | "ALL">("ALL");

  useEffect(() => {
    setSmells(null);
    setError(null);
    api.getSmells(repoId).then(setSmells).catch((err) => setError(err.message));
    api.getArchitecture(repoId).then(setArchitecture).catch(() => setArchitecture(null));
  }, [repoId]);

  const componentIdByFile = useMemo(() => {
    const map = new Map<string, string>();
    for (const c of architecture?.components ?? []) {
      for (const f of c.files) map.set(f, c.id);
    }
    return map;
  }, [architecture]);

  const counts = useMemo(() => {
    const c = { HIGH: 0, MEDIUM: 0, LOW: 0 };
    for (const s of smells ?? []) c[s.severity]++;
    return c;
  }, [smells]);

  const filtered = useMemo(() => {
    if (!smells) return [];
    return smells.filter((s) => {
      if (severityFilter !== "ALL" && s.severity !== severityFilter) return false;
      if (categoryFilter !== "ALL" && SMELL_CATEGORY[s.smell_type] !== categoryFilter) return false;
      return true;
    });
  }, [smells, severityFilter, categoryFilter]);

  if (error) return <p className="text-sm text-(--bad)">{error}</p>;
  if (!smells)
    return (
      <div className="flex flex-col gap-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-24 animate-pulse rounded-lg bg-(--bg-sunken)" />
        ))}
      </div>
    );

  if (smells.length === 0)
    return (
      <p className="text-sm text-(--text-faint)">
        No structural findings were identified against the current thresholds.
      </p>
    );

  return (
    <div>
      <div className="mb-5 flex flex-wrap gap-x-8 gap-y-3">
        <div>
          <strong className="font-mono text-xl text-(--text) tabular-nums">{smells.length}</strong>
          <span className="block text-[0.65rem] font-medium tracking-wide text-(--text-faint) uppercase">
            Findings
          </span>
        </div>
        <div>
          <strong className="font-mono text-xl text-(--bad) tabular-nums">{counts.HIGH}</strong>
          <span className="block text-[0.65rem] font-medium tracking-wide text-(--text-faint) uppercase">High</span>
        </div>
        <div>
          <strong className="font-mono text-xl text-(--warn) tabular-nums">{counts.MEDIUM}</strong>
          <span className="block text-[0.65rem] font-medium tracking-wide text-(--text-faint) uppercase">
            Medium
          </span>
        </div>
        <div>
          <strong className="font-mono text-xl text-(--text-faint) tabular-nums">{counts.LOW}</strong>
          <span className="block text-[0.65rem] font-medium tracking-wide text-(--text-faint) uppercase">Low</span>
        </div>
      </div>

      <div className="mb-5 flex flex-col gap-2">
        <div className="flex flex-wrap gap-1.5">
          {(["ALL", "HIGH", "MEDIUM", "LOW"] as const).map((s) => (
            <Chip key={s} active={severityFilter === s} onClick={() => setSeverityFilter(s)}>
              {s === "ALL" ? "All severities" : s}
            </Chip>
          ))}
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Chip active={categoryFilter === "ALL"} onClick={() => setCategoryFilter("ALL")}>
            All types
          </Chip>
          {(Object.keys(SMELL_CATEGORY_LABELS) as SmellCategory[]).map((cat) => (
            <Chip key={cat} active={categoryFilter === cat} onClick={() => setCategoryFilter(cat)}>
              {SMELL_CATEGORY_LABELS[cat]}
            </Chip>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <p className="text-sm text-(--text-faint)">No findings match the current filters.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.slice(0, DISPLAY_LIMIT).map((s, i) => {
            const file = s.affected[0]?.file_path;
            const componentId = file ? (componentIdByFile.get(file) ?? null) : null;
            return <FindingCard key={i} smell={s} componentId={componentId} />;
          })}
          {filtered.length > DISPLAY_LIMIT && (
            <p className="text-xs text-(--text-faint) italic">
              {filtered.length - DISPLAY_LIMIT} more finding{filtered.length - DISPLAY_LIMIT === 1 ? "" : "s"} match
              the current filters but {"aren't"} shown — narrow the filters to see them.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
