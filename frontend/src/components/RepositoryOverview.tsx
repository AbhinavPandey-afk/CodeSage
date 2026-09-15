import { ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type {
  ArchitectureModel,
  HistoryReport,
  OptimizationReport,
  Repository,
  Smell,
} from "../api/types";
import { ConfidenceBadge } from "@/components/evidence/ConfidenceBadge";
import { RiskBadge } from "@/components/evidence/RiskBadge";
import { SectionLabel } from "@/components/evidence/SectionLabel";
import { useInvestigation } from "@/lib/investigation";
import { NAV_GROUPS, type Tab } from "@/lib/navigation";
import { ROLE_LABELS, SMELL_TYPE_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";

function useEndpoint<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    fn()
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : "Request failed."));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error };
}

function StatBlock({ value, label }: { value: number | string; label: string }) {
  return (
    <div className="flex flex-col">
      <strong className="font-mono text-xl text-(--text) tabular-nums">{value}</strong>
      <span className="text-[0.68rem] font-medium tracking-wide text-(--text-faint) uppercase">{label}</span>
    </div>
  );
}

function SeverityDot({ severity }: { severity: "HIGH" | "MEDIUM" | "LOW" }) {
  return (
    <span
      className={cn(
        "size-1.5 shrink-0 rounded-full",
        severity === "HIGH" && "bg-(--bad)",
        severity === "MEDIUM" && "bg-(--warn)",
        severity === "LOW" && "bg-(--text-faint)",
      )}
    />
  );
}

export function RepositoryOverview({ repoId, repository }: { repoId: string; repository: Repository }) {
  const { navigate } = useInvestigation();
  const architecture = useEndpoint<ArchitectureModel>(() => api.getArchitecture(repoId), [repoId]);
  const smells = useEndpoint<Smell[]>(() => api.getSmells(repoId), [repoId]);
  const optimization = useEndpoint<OptimizationReport>(() => api.getOptimization(repoId), [repoId]);
  const history = useEndpoint<HistoryReport>(() => api.getHistory(repoId), [repoId]);

  const topComponents = architecture.data
    ? [...architecture.data.components].sort((a, b) => b.file_count - a.file_count).slice(0, 5)
    : null;

  const topFindings = smells.data
    ? [...smells.data]
        .sort((a, b) => (a.severity === b.severity ? 0 : a.severity === "HIGH" ? -1 : b.severity === "HIGH" ? 1 : a.severity === "MEDIUM" ? -1 : 1))
        .slice(0, 4)
    : null;

  const confidenceCounts = architecture.data
    ? architecture.data.components.reduce(
        (acc, c) => {
          acc[c.confidence_label] += 1;
          return acc;
        },
        { Confirmed: 0, Inferred: 0, Uncertain: 0 },
      )
    : null;
  const confidenceTotal = confidenceCounts
    ? confidenceCounts.Confirmed + confidenceCounts.Inferred + confidenceCounts.Uncertain
    : 0;

  const mostActiveComponent = history.data?.components.length
    ? [...history.data.components].sort((a, b) => b.commit_count - a.commit_count)[0]
    : null;

  const highSmells = smells.data?.filter((s) => s.severity === "HIGH").length ?? 0;

  const RISK_ORDER = { LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3 } as const;
  const highestRisk = optimization.data?.proposals.length
    ? optimization.data.proposals.reduce(
        (max, p) => (RISK_ORDER[p.risk_level] > RISK_ORDER[max] ? p.risk_level : max),
        optimization.data.proposals[0].risk_level,
      )
    : null;

  const recommendations: { text: string; action: string; tab: Tab }[] = [];
  if (highSmells > 0) {
    recommendations.push({
      text: `${highSmells} high-severity structural finding${highSmells === 1 ? "" : "s"} ${highSmells === 1 ? "was" : "were"} detected in the reconstructed architecture.`,
      action: "Investigate findings",
      tab: "smells",
    });
  }
  if (optimization.data && optimization.data.proposals.length > 0) {
    const n = optimization.data.proposals.length;
    recommendations.push({
      text: `${n} restoration proposal${n === 1 ? "" : "s"} ${n === 1 ? "is" : "are"} available for the violations found above.`,
      action: "Review optimization",
      tab: "optimization",
    });
  }
  if (mostActiveComponent) {
    recommendations.push({
      text: `${mostActiveComponent.component_name} is the most historically active component, with ${mostActiveComponent.commit_count} commits touching it.`,
      action: "View history",
      tab: "history",
    });
  }
  if (recommendations.length === 0 && architecture.data) {
    recommendations.push({
      text: "Start by exploring the reconstructed architecture to understand the major components of this system.",
      action: "Explore architecture",
      tab: "architecture",
    });
  }

  const quickActions = NAV_GROUPS.flatMap((g) => g.items).filter((i) => i.tab !== "overview");

  return (
    <div className="flex flex-col gap-10">
      {/* --- Site summary --- */}
      <section>
        <SectionLabel index="01">Site summary</SectionLabel>
        <div className="flex flex-wrap gap-x-8 gap-y-4">
          <StatBlock value={repository.file_count} label="Files" />
          <StatBlock value={repository.symbol_count} label="Symbols" />
          <StatBlock value={repository.relationship_count} label="Relationships" />
          <StatBlock value={architecture.data ? architecture.data.components.length : "—"} label="Components" />
          <StatBlock value={smells.data ? smells.data.length : "—"} label="Findings" />
          <StatBlock value={Object.keys(repository.languages).length} label="Languages" />
          {highestRisk && (
            <div className="flex flex-col">
              <RiskBadge level={highestRisk} className="w-fit" />
              <span className="mt-1 text-[0.68rem] font-medium tracking-wide text-(--text-faint) uppercase">
                Highest proposal risk
              </span>
            </div>
          )}
        </div>
      </section>

      {/* --- Architecture preview --- */}
      <section>
        <SectionLabel index="02">Reconstructed architecture</SectionLabel>
        {architecture.error && <p className="text-sm text-(--bad)">{architecture.error}</p>}
        {!architecture.data && !architecture.error && (
          <div className="flex flex-col gap-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded-md bg-(--bg-sunken)" />
            ))}
          </div>
        )}
        {topComponents && topComponents.length === 0 && (
          <p className="text-sm text-(--text-faint)">
            No architectural components could be reconstructed from this repository's structure.
          </p>
        )}
        {topComponents && topComponents.length > 0 && (
          <div className="flex flex-col gap-2">
            {topComponents.map((c) => (
              <button
                key={c.id}
                onClick={() => navigate("architecture", { componentId: c.id })}
                className="flex items-center gap-3 rounded-md border border-(--border) bg-(--bg-raised) px-3.5 py-2.5 text-left transition-colors hover:border-(--accent)/40"
              >
                <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                  {ROLE_LABELS[c.role] ?? c.role}
                </span>
                <code className="min-w-0 flex-1 truncate text-sm text-(--text)">{c.name}</code>
                <span className="hidden shrink-0 text-xs text-(--text-faint) sm:inline">
                  {c.file_count} file{c.file_count === 1 ? "" : "s"}
                </span>
                <ConfidenceBadge label={c.confidence_label} />
              </button>
            ))}
            {architecture.data && architecture.data.components.length > topComponents.length && (
              <button
                onClick={() => navigate("architecture")}
                className="mt-1 flex items-center gap-1 self-start text-xs font-medium text-(--accent-text) hover:underline"
              >
                View all {architecture.data.components.length} components <ArrowRight className="size-3" />
              </button>
            )}
          </div>
        )}
      </section>

      <div className="grid grid-cols-1 gap-10 lg:grid-cols-2">
        {/* --- Top discoveries --- */}
        <section>
          <SectionLabel index="03">Top discoveries</SectionLabel>
          {smells.error && <p className="text-sm text-(--bad)">{smells.error}</p>}
          {!smells.data && !smells.error && (
            <div className="flex flex-col gap-2">
              {[0, 1].map((i) => (
                <div key={i} className="h-14 animate-pulse rounded-md bg-(--bg-sunken)" />
              ))}
            </div>
          )}
          {topFindings && topFindings.length === 0 && (
            <p className="text-sm text-(--text-faint)">
              No structural findings were identified against the current thresholds.
            </p>
          )}
          {topFindings && topFindings.length > 0 && (
            <ul className="flex flex-col gap-2">
              {topFindings.map((s, i) => (
                <li key={i}>
                  <button
                    onClick={() => navigate("smells")}
                    className="flex w-full items-start gap-2.5 rounded-md border border-(--border) bg-(--bg-raised) px-3.5 py-2.5 text-left transition-colors hover:border-(--accent)/40"
                  >
                    <SeverityDot severity={s.severity} />
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium text-(--text)">{s.title}</span>
                      <span className="text-xs text-(--text-faint)">
                        {SMELL_TYPE_LABELS[s.smell_type] ?? s.smell_type}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* --- Confidence --- */}
        <section>
          <SectionLabel index="04">Reconstruction confidence</SectionLabel>
          {confidenceCounts && confidenceTotal > 0 ? (
            <div className="flex flex-col gap-3">
              <div className="flex h-2 overflow-hidden rounded-full bg-(--bg-sunken)">
                {(["Confirmed", "Inferred", "Uncertain"] as const).map((label) => {
                  const pct = (confidenceCounts[label] / confidenceTotal) * 100;
                  if (pct === 0) return null;
                  return (
                    <div
                      key={label}
                      style={{ width: `${pct}%` }}
                      className={cn(
                        label === "Confirmed" && "bg-(--ok)",
                        label === "Inferred" && "bg-(--bronze)",
                        label === "Uncertain" && "bg-(--border-strong)",
                      )}
                    />
                  );
                })}
              </div>
              <div className="flex flex-wrap gap-x-5 gap-y-2">
                {(["Confirmed", "Inferred", "Uncertain"] as const).map((label) => (
                  <div key={label} className="flex items-center gap-1.5">
                    <ConfidenceBadge label={label} />
                    <span className="font-mono text-xs text-(--text-faint) tabular-nums">
                      {confidenceCounts[label]}
                    </span>
                  </div>
                ))}
              </div>
              <p className="text-xs text-(--text-faint)">
                Across {confidenceTotal} reconstructed component{confidenceTotal === 1 ? "" : "s"}, labeled from
                the evidence that produced each classification.
              </p>
            </div>
          ) : (
            <div className="h-16 animate-pulse rounded-md bg-(--bg-sunken)" />
          )}
        </section>
      </div>

      {/* --- Recommended next investigation --- */}
      <section>
        <SectionLabel index="05">Recommended next investigation</SectionLabel>
        <div className="flex flex-col gap-2.5">
          {recommendations.map((r, i) => (
            <div
              key={i}
              className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-(--border) bg-(--bg-raised) px-4 py-3"
            >
              <p className="max-w-xl text-sm text-(--text-soft)">{r.text}</p>
              <button
                onClick={() => navigate(r.tab)}
                className="flex shrink-0 items-center gap-1 rounded-md bg-(--accent) px-3 py-1.5 text-xs font-semibold text-(--bg-raised) transition-opacity hover:opacity-90"
              >
                {r.action} <ArrowRight className="size-3" />
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* --- Quick actions --- */}
      <section>
        <SectionLabel index="06">Quick actions</SectionLabel>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {quickActions.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.tab}
                onClick={() => navigate(item.tab)}
                className="flex items-center gap-2 rounded-md border border-(--border) bg-(--bg-raised) px-3 py-2.5 text-left text-sm font-medium text-(--text-soft) transition-colors hover:border-(--accent)/40 hover:text-(--text)"
              >
                <Icon className="size-4 shrink-0" strokeWidth={2} />
                <span className="truncate">{item.label}</span>
              </button>
            );
          })}
        </div>
      </section>
    </div>
  );
}
