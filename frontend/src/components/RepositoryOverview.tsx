import { ArrowRight, GitBranch } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type {
  ArchitectureModel,
  HistoryReport,
  OptimizationProposal,
  OptimizationReport,
  Repository,
  Severity,
  Smell,
} from "../api/types";
import { roleColorVar, roleIcon } from "@/components/architecture/roleStyle";
import { ConfidenceBadge } from "@/components/evidence/ConfidenceBadge";
import { RiskBadge } from "@/components/evidence/RiskBadge";
import { SectionLabel } from "@/components/evidence/SectionLabel";
import { aggregateExternalDependencies, classifyStructure, deriveLayers, summarize } from "@/lib/architectureModel";
import { confidenceLabel } from "@/lib/flowModel";
import { type FocusTarget, useInvestigation } from "@/lib/investigation";
import { NAV_GROUPS, type Tab } from "@/lib/navigation";
import { LANGUAGE_LABELS, NAV_ACTION_HINTS, SMELL_TYPE_LABELS } from "@/lib/labels";
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

function SeverityDot({ severity }: { severity: Severity }) {
  return (
    <span
      className={cn(
        "mt-1 size-1.5 shrink-0 rounded-full",
        severity === "HIGH" && "bg-(--bad)",
        severity === "MEDIUM" && "bg-(--warn)",
        severity === "LOW" && "bg-(--text-faint)",
      )}
    />
  );
}

const SEVERITY_ORDER: Record<Severity, number> = { HIGH: 2, MEDIUM: 1, LOW: 0 };
const RISK_ORDER = { LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3 } as const;

interface Recommendation {
  text: string;
  action: string;
  tab: Tab;
  focus?: FocusTarget;
}

export function RepositoryOverview({ repoId, repository }: { repoId: string; repository: Repository }) {
  const { navigate } = useInvestigation();
  const architecture = useEndpoint<ArchitectureModel>(() => api.getArchitecture(repoId), [repoId]);
  const smells = useEndpoint<Smell[]>(() => api.getSmells(repoId), [repoId]);
  const optimization = useEndpoint<OptimizationReport>(() => api.getOptimization(repoId), [repoId]);
  const history = useEndpoint<HistoryReport>(() => api.getHistory(repoId), [repoId]);

  // --- Reconstructed system: the same layer/structure derivation Architecture
  // uses, not a second implementation — Overview only summarizes it.
  const layers = architecture.data ? deriveLayers(architecture.data.components) : null;
  const supportingCount = architecture.data
    ? architecture.data.components.filter((c) => classifyStructure(c) === "supporting").length
    : 0;
  const archSummary =
    architecture.data && layers
      ? summarize(architecture.data, layers, aggregateExternalDependencies(architecture.data.components))
      : null;
  const overallConfidence = archSummary ? confidenceLabel(archSummary.averageConfidence) : null;

  const componentIdByFile = new Map<string, string>();
  const componentNameById = new Map<string, string>();
  for (const c of architecture.data?.components ?? []) {
    componentNameById.set(c.id, c.name);
    for (const f of c.files) componentIdByFile.set(f, c.id);
  }

  const languageEntries = Object.entries(repository.languages).sort((a, b) => b[1] - a[1]);
  const primaryLanguage = languageEntries[0]?.[0];

  const topFindings = smells.data
    ? [...smells.data].sort((a, b) => SEVERITY_ORDER[b.severity] - SEVERITY_ORDER[a.severity]).slice(0, 4)
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

  const riskiestProposal = (optimization.data?.proposals ?? []).reduce<OptimizationProposal | null>((max, p) => {
    if (!p.representative_impact) return max;
    if (!max) return p;
    return RISK_ORDER[p.risk_level] > RISK_ORDER[max.risk_level] ? p : max;
  }, null);

  const highestRisk = optimization.data?.proposals.length
    ? optimization.data.proposals.reduce(
        (max, p) => (RISK_ORDER[p.risk_level] > RISK_ORDER[max] ? p.risk_level : max),
        optimization.data.proposals[0].risk_level,
      )
    : null;

  // Deterministic prioritization (CLAUDE.md §14: no LLM guess stands in for
  // evidence-backed reasoning) — most urgent evidence first. Every trigger
  // here reads a real field already returned by an existing endpoint.
  const recommendations: Recommendation[] = [];
  if (highSmells > 0) {
    recommendations.push({
      text: `${highSmells} high-severity structural finding${highSmells === 1 ? "" : "s"} ${highSmells === 1 ? "was" : "were"} detected in the reconstructed architecture.`,
      action: "Investigate findings",
      tab: "smells",
    });
  }
  if (
    riskiestProposal?.representative_impact &&
    (riskiestProposal.risk_level === "HIGH" || riskiestProposal.risk_level === "CRITICAL")
  ) {
    const ri = riskiestProposal.representative_impact;
    recommendations.push({
      text: `${ri.symbol_qualified_name} carries ${riskiestProposal.risk_level.toLowerCase()} change risk — ${ri.direct_dependents} direct and ${ri.indirect_dependents} indirect dependents were traced from the resolved call graph.`,
      action: "Inspect impact",
      tab: "impact",
      focus: { qualifiedName: ri.symbol_qualified_name },
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
  if (recommendations.length === 0 && architecture.data && architecture.data.components.length > 0) {
    recommendations.push({
      text: "Start by exploring the reconstructed architecture to understand the major components of this system.",
      action: "Explore architecture",
      tab: "architecture",
    });
  }
  // Wait for every source a trigger above reads (not just the first to
  // settle) — otherwise the list would render, say, only the smells-based
  // recommendation while optimization is still in flight, then jump a beat
  // later once it resolves.
  const recommendationsPending = !(
    (architecture.data || architecture.error) &&
    (smells.data || smells.error) &&
    (optimization.data || optimization.error) &&
    (history.data || history.error)
  );

  const quickActions = NAV_GROUPS.flatMap((g) => g.items).filter((i) => i.tab !== "overview");

  return (
    <div className="flex flex-col gap-10">
      {/* --- A/B: Site identity + discovery summary --- */}
      <section>
        <SectionLabel index="01">Site summary</SectionLabel>

        <div className="mb-3 flex flex-wrap items-center gap-2">
          {primaryLanguage && (
            <span className="rounded-full border border-(--border) bg-(--bg-raised) px-2.5 py-1 font-mono text-xs font-medium text-(--text-soft)">
              {LANGUAGE_LABELS[primaryLanguage] ?? primaryLanguage}
              {languageEntries.length > 1 ? ` +${languageEntries.length - 1}` : ""}
            </span>
          )}
          {overallConfidence && (
            <span className="flex items-center gap-1">
              <ConfidenceBadge label={overallConfidence} />
              <span className="text-xs text-(--text-faint)">reconstruction confidence</span>
            </span>
          )}
          {repository.default_branch && repository.commit_sha && (
            <span className="flex items-center gap-1 font-mono text-xs text-(--text-faint)">
              <GitBranch className="size-3" strokeWidth={2} />
              {repository.default_branch}@{repository.commit_sha.slice(0, 7)}
            </span>
          )}
        </div>

        <p className="mb-5 max-w-2xl text-sm text-(--text-soft)">
          Reconstructed from {repository.file_count} files, {repository.symbol_count} symbols and{" "}
          {repository.relationship_count} structural relationships.
        </p>

        <div className="flex flex-wrap gap-x-8 gap-y-4">
          <StatBlock value={repository.file_count} label="Files" />
          <StatBlock value={repository.symbol_count} label="Symbols" />
          <StatBlock value={repository.relationship_count} label="Relationships" />
          <StatBlock value={architecture.data ? architecture.data.components.length : "—"} label="Components" />
          <StatBlock value={smells.data ? smells.data.length : "—"} label="Findings" />
          <StatBlock value={languageEntries.length} label="Languages" />
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

      {/* --- C: Reconstructed system --- */}
      <section>
        <SectionLabel index="02">Reconstructed system</SectionLabel>
        {architecture.error && <p className="text-sm text-(--bad)">{architecture.error}</p>}
        {!architecture.data && !architecture.error && (
          <div className="flex flex-col gap-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-14 animate-pulse rounded-md bg-(--bg-sunken)" />
            ))}
          </div>
        )}
        {architecture.data && architecture.data.components.length === 0 && (
          <p className="text-sm text-(--text-faint)">
            No architectural components could be reconstructed from this repository's structure.
          </p>
        )}
        {architecture.data && architecture.data.components.length > 0 && layers && (
          <>
            {layers.length === 0 ? (
              <p className="text-sm text-(--text-faint)">
                Every reconstructed component was classified as tests or supporting structure — no runtime layers
                were identified.
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                {layers.map((layer) => {
                  const Icon = roleIcon(layer.role);
                  const colorVar = roleColorVar(layer.role);
                  return (
                    <div
                      key={layer.id}
                      className="flex items-center gap-3 rounded-md border border-(--border) bg-(--bg-raised) px-3.5 py-2.5"
                    >
                      <span
                        className="flex size-6 shrink-0 items-center justify-center rounded"
                        style={{
                          backgroundColor: `color-mix(in oklab, var(${colorVar}) 16%, transparent)`,
                          color: `var(${colorVar})`,
                        }}
                      >
                        <Icon className="size-3.5" strokeWidth={2.25} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-medium text-(--text)">{layer.name}</span>
                        <span className="block truncate text-xs text-(--text-faint)">{layer.purpose}</span>
                      </span>
                      <span className="hidden shrink-0 text-xs text-(--text-faint) sm:inline">
                        {layer.componentIds.length} component{layer.componentIds.length === 1 ? "" : "s"}
                      </span>
                      <ConfidenceBadge label={confidenceLabel(layer.confidence)} />
                    </div>
                  );
                })}
              </div>
            )}
            {supportingCount > 0 && (
              <p className="mt-2.5 text-xs text-(--text-faint)">
                +{supportingCount} supporting component{supportingCount === 1 ? "" : "s"} (tests, tooling) —
                present in the repository, but not part of the running system.
              </p>
            )}
            <button
              onClick={() => navigate("architecture")}
              className="mt-2.5 flex items-center gap-1 self-start text-xs font-medium text-(--accent-text) hover:underline"
            >
              Explore architecture <ArrowRight className="size-3" />
            </button>
          </>
        )}
      </section>

      <div className="grid grid-cols-1 gap-10 lg:grid-cols-2">
        {/* --- D: Top discoveries --- */}
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
              {topFindings.map((s, i) => {
                const primary = s.affected[0];
                const componentId = primary ? (componentIdByFile.get(primary.file_path) ?? null) : null;
                const componentName = componentId ? componentNameById.get(componentId) : null;
                return (
                  <li key={i}>
                    <button
                      onClick={() => navigate("smells", { findingId: s.id })}
                      className="flex w-full items-start gap-2.5 rounded-md border border-(--border) bg-(--bg-raised) px-3.5 py-2.5 text-left transition-colors hover:border-(--accent)/40"
                    >
                      <SeverityDot severity={s.severity} />
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-medium text-(--text)">{s.title}</span>
                        <span className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs text-(--text-faint)">
                          <span>{SMELL_TYPE_LABELS[s.smell_type] ?? s.smell_type}</span>
                          {(componentName || primary) && <span aria-hidden>·</span>}
                          {componentName ? (
                            <code className="truncate text-(--text-soft)">{componentName}</code>
                          ) : primary ? (
                            <code className="truncate text-(--text-soft)">{primary.qualified_name}</code>
                          ) : null}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {/* --- E: Reconstruction confidence --- */}
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
                Confidence reflects the evidence supporting each reconstructed component — not a generic
                probability — across {confidenceTotal} component{confidenceTotal === 1 ? "" : "s"}.
              </p>
              <button
                onClick={() => navigate("architecture")}
                className="flex items-center gap-1 self-start text-xs font-medium text-(--accent-text) hover:underline"
              >
                View reconstruction <ArrowRight className="size-3" />
              </button>
            </div>
          ) : (
            <div className="h-16 animate-pulse rounded-md bg-(--bg-sunken)" />
          )}
        </section>
      </div>

      {/* --- F: Recommended next investigation --- */}
      <section>
        <SectionLabel index="05">Recommended next investigation</SectionLabel>
        {recommendationsPending && recommendations.length === 0 && (
          <div className="flex flex-col gap-2.5">
            {[0, 1].map((i) => (
              <div key={i} className="h-14 animate-pulse rounded-md bg-(--bg-sunken)" />
            ))}
          </div>
        )}
        {!recommendationsPending && recommendations.length === 0 && (
          <p className="text-sm text-(--text-faint)">
            No prioritized findings were detected — this repository shows no high-severity structural issues, risk
            flags, or notable activity to investigate first.
          </p>
        )}
        {recommendations.length > 0 && (
          <div className="flex flex-col gap-2.5">
            {recommendations.map((r, i) => (
              <div
                key={i}
                className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-(--border) bg-(--bg-raised) px-4 py-3"
              >
                <p className="max-w-xl text-sm text-(--text-soft)">{r.text}</p>
                <button
                  onClick={() => navigate(r.tab, r.focus)}
                  className="flex shrink-0 items-center gap-1 rounded-md bg-(--accent) px-3 py-1.5 text-xs font-semibold text-(--bg-raised) transition-opacity hover:opacity-90"
                >
                  {r.action} <ArrowRight className="size-3" />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* --- G: Quick investigation actions --- */}
      <section>
        <SectionLabel index="06">Quick investigation actions</SectionLabel>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {quickActions.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.tab}
                onClick={() => navigate(item.tab)}
                className="flex items-start gap-2.5 rounded-md border border-(--border) bg-(--bg-raised) px-3 py-2.5 text-left transition-colors hover:border-(--accent)/40"
              >
                <Icon className="mt-0.5 size-4 shrink-0 text-(--text-faint)" strokeWidth={2} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-(--text-soft)">{item.label}</span>
                  <span className="block text-xs text-(--text-faint)">{NAV_ACTION_HINTS[item.tab]}</span>
                </span>
              </button>
            );
          })}
        </div>
      </section>
    </div>
  );
}
