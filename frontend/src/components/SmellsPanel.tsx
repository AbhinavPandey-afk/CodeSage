import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { ArchitectureModel, Severity, Smell } from "../api/types";
import { FindingCard } from "@/components/analysis/FindingCard";
import { FindingInspector } from "@/components/analysis/FindingInspector";
import { confidenceTier, sortFindings, type ConfidenceTier as ConfidenceTierType } from "@/lib/analysisModel";
import { useInvestigation } from "@/lib/investigation";
import { SMELL_CATEGORY, SMELL_CATEGORY_LABELS, type SmellCategory } from "../lib/labels";
import { cn } from "@/lib/utils";

const DISPLAY_LIMIT = 40;
type ConfidenceFilter = ConfidenceTierType | "ALL";

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

function StatBlock({ value, label, valueClassName }: { value: number; label: string; valueClassName?: string }) {
  return (
    <div>
      <strong className={cn("font-mono text-xl tabular-nums", valueClassName ?? "text-(--text)")}>{value}</strong>
      <span className="block text-[0.65rem] font-medium tracking-wide text-(--text-faint) uppercase">{label}</span>
    </div>
  );
}

export function SmellsPanel({ repoId }: { repoId: string }) {
  const { focus } = useInvestigation();
  const consumedFocusRef = useRef(false);

  const [smells, setSmells] = useState<Smell[] | null>(null);
  const [architecture, setArchitecture] = useState<ArchitectureModel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<Severity | "ALL">("ALL");
  const [categoryFilter, setCategoryFilter] = useState<SmellCategory | "ALL">("ALL");
  const [confidenceFilter, setConfidenceFilter] = useState<ConfidenceFilter>("ALL");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    setSmells(null);
    setError(null);
    setSelectedId(null);
    setExpanded(false);
    consumedFocusRef.current = false;
    // Fetched once here, not re-fetched by any child — the inspector's
    // "Show on Architecture" / "View Evidence" actions and its component
    // context reuse this same response (CLAUDE.md V2 UI §28).
    api.getSmells(repoId).then(setSmells).catch((err) => setError(err.message));
    api.getArchitecture(repoId).then(setArchitecture).catch(() => setArchitecture(null));
  }, [repoId]);

  useEffect(() => {
    if (consumedFocusRef.current || !focus?.findingId || !smells) return;
    if (!smells.some((s) => s.id === focus.findingId)) return;
    consumedFocusRef.current = true;
    setSelectedId(focus.findingId);
  }, [focus, smells]);

  const findingsById = useMemo(() => new Map((smells ?? []).map((s) => [s.id, s])), [smells]);

  const counts = useMemo(() => {
    const severity = { HIGH: 0, MEDIUM: 0, LOW: 0 };
    const confidence: Record<ConfidenceTierType, number> = { High: 0, Medium: 0, Low: 0 };
    for (const s of smells ?? []) {
      severity[s.severity]++;
      confidence[confidenceTier(s.confidence)]++;
    }
    return { severity, confidence };
  }, [smells]);

  const filtered = useMemo(() => {
    if (!smells) return [];
    const matches = smells.filter((s) => {
      if (severityFilter !== "ALL" && s.severity !== severityFilter) return false;
      if (categoryFilter !== "ALL" && SMELL_CATEGORY[s.smell_type] !== categoryFilter) return false;
      if (confidenceFilter !== "ALL" && confidenceTier(s.confidence) !== confidenceFilter) return false;
      return true;
    });
    return sortFindings(matches);
  }, [smells, severityFilter, categoryFilter, confidenceFilter]);

  const visible = expanded ? filtered : filtered.slice(0, DISPLAY_LIMIT);
  const selected = selectedId ? (findingsById.get(selectedId) ?? null) : null;

  if (error) return <p className="text-sm text-(--bad)">{error}</p>;
  if (!smells)
    return (
      <div className="flex flex-col gap-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-24 animate-pulse rounded-lg bg-(--bg-sunken)" />
        ))}
      </div>
    );

  if (smells.length === 0) return <p className="text-sm text-(--text-faint)">No structural findings detected.</p>;

  return (
    <div className={cn("min-w-0", selected && "lg:pr-[400px]")}>
      <div className="mb-5 flex flex-wrap gap-x-8 gap-y-3">
        <StatBlock value={smells.length} label="Findings" />
        <StatBlock value={counts.severity.HIGH} label="High" valueClassName="text-(--bad)" />
        <StatBlock value={counts.severity.MEDIUM} label="Medium" valueClassName="text-(--warn)" />
        <StatBlock value={counts.severity.LOW} label="Low" valueClassName="text-(--text-faint)" />
        <div className="flex gap-4 border-l border-(--border) pl-8">
          <StatBlock value={counts.confidence.High} label="High confidence" valueClassName="text-(--ok)" />
          <StatBlock value={counts.confidence.Medium} label="Medium confidence" valueClassName="text-(--bronze)" />
          <StatBlock value={counts.confidence.Low} label="Low confidence" valueClassName="text-(--text-faint)" />
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
        <div className="flex flex-wrap gap-1.5">
          {(["ALL", "High", "Medium", "Low"] as const).map((c) => (
            <Chip key={c} active={confidenceFilter === c} onClick={() => setConfidenceFilter(c)}>
              {c === "ALL" ? "All confidence" : `${c} confidence`}
            </Chip>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <p className="text-sm text-(--text-faint)">No findings match the current filters.</p>
      ) : (
        <>
          <div className="flex flex-col gap-3">
            {visible.map((s) => (
              <FindingCard
                key={s.id}
                smell={s}
                selected={selectedId === s.id}
                onSelect={() => setSelectedId((cur) => (cur === s.id ? null : s.id))}
              />
            ))}
          </div>
          <p className="mt-3 text-xs text-(--text-faint)">
            {filtered.length} finding{filtered.length === 1 ? "" : "s"} · showing {visible.length}
            {!expanded && filtered.length > DISPLAY_LIMIT && (
              <>
                {" — "}
                <button onClick={() => setExpanded(true)} className="font-medium text-(--accent-text) hover:underline">
                  show all {filtered.length}
                </button>
              </>
            )}
          </p>
        </>
      )}

      <FindingInspector
        smell={selected}
        allFindingsById={findingsById}
        components={architecture?.components ?? []}
        onClose={() => setSelectedId(null)}
        onSelectFinding={setSelectedId}
      />
    </div>
  );
}
