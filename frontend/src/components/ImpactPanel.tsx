import { useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { Dependent, ImpactReport, SymbolSearchResult } from "../api/types";
import { ImpactCone } from "@/components/impact/ImpactCone";
import { SymbolSearch } from "@/components/impact/SymbolSearch";
import { RiskBadge } from "@/components/evidence/RiskBadge";
import { useInvestigation } from "@/lib/investigation";
import { cn } from "@/lib/utils";

function DependentList({ items, limit = 8 }: { items: Dependent[]; limit?: number }) {
  if (items.length === 0) return <p className="text-xs text-(--text-faint)">None found.</p>;
  return (
    <ul className="flex flex-col gap-1">
      {items.slice(0, limit).map((d) => (
        <li key={d.uid} className="text-xs">
          <code className="block truncate text-(--text-soft)">{d.qualified_name}</code>
          <span className="text-(--text-faint)">
            {d.file_path}:{d.start_line}
          </span>
        </li>
      ))}
      {items.length > limit && <li className="text-xs text-(--text-faint) italic">…and {items.length - limit} more</li>}
    </ul>
  );
}

function Section({ title, count, children }: { title: string; count: number; children: ReactNode }) {
  return (
    <div className="rounded-md border border-(--border) bg-(--bg-raised) p-3.5">
      <h4 className="mb-2 text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
        {title} ({count})
      </h4>
      {children}
    </div>
  );
}

export function ImpactPanel({ repoId }: { repoId: string }) {
  const { focus } = useInvestigation();
  const consumedFocusRef = useRef(false);

  const [query, setQuery] = useState("");
  const [report, setReport] = useState<ImpactReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runAnalysis = async (symbol: SymbolSearchResult) => {
    setQuery(symbol.qualified_name);
    setError(null);
    setLoading(true);
    setReport(null);
    try {
      const r = await api.getImpact(repoId, symbol.uid);
      setReport(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to analyze impact.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (consumedFocusRef.current || !focus?.qualifiedName) return;
    consumedFocusRef.current = true;
    api
      .searchSymbols(repoId, focus.qualifiedName)
      .then((results) => {
        const match = results.find((r) => r.qualified_name === focus.qualifiedName) ?? results[0];
        if (match) void runAnalysis(match);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repoId, focus]);

  return (
    <div>
      <div className="mb-6 max-w-xl">
        <SymbolSearch repoId={repoId} value={query} onSelect={runAnalysis} />
      </div>

      {loading && (
        <div className="flex flex-col gap-3">
          <div className="h-24 animate-pulse rounded-lg bg-(--bg-sunken)" />
          <div className="h-64 animate-pulse rounded-lg bg-(--bg-sunken)" />
        </div>
      )}
      {error && <p className="text-sm text-(--bad)">{error}</p>}

      {report && (
        <div>
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3 rounded-lg border border-(--border) bg-(--bg-raised) p-4">
            <div className="min-w-0">
              <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.62rem] text-(--text-faint) uppercase">
                {report.target_symbol_type}
              </span>
              <code className="mt-1.5 block truncate text-base font-medium text-(--text)">
                {report.target_qualified_name}
              </code>
            </div>
            <RiskBadge level={report.risk_level} />
          </div>

          <p className="mb-4 text-sm leading-relaxed text-(--text-soft)">{report.explanation}</p>

          {report.risk_signals.length > 0 && (
            <div className="mb-5 flex flex-col gap-1.5 rounded-md border border-(--border) bg-(--bg-raised) p-3.5">
              <p className="mb-1 text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                Risk signals
              </p>
              {report.risk_signals.map((s, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <span className="flex-1 text-(--text-soft)">{s.name}</span>
                  <span className="font-mono text-xs text-(--text-faint)">{s.value}</span>
                  <span className="w-8 text-right font-mono text-xs text-(--accent-text)">+{s.points}</span>
                </div>
              ))}
            </div>
          )}

          {(report.direct_dependents.length > 0 || report.indirect_dependents.length > 0) && (
            <div className="mb-5">
              <p className="mb-2 text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                Impact cone
              </p>
              <ImpactCone
                targetName={report.target_qualified_name}
                direct={report.direct_dependents}
                indirect={report.indirect_dependents}
              />
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Section title="Direct dependents" count={report.direct_dependents.length}>
              <DependentList items={report.direct_dependents} />
            </Section>
            <Section title="Indirect dependents" count={report.indirect_dependents.length}>
              <DependentList items={report.indirect_dependents} />
            </Section>
            <Section title="Affected API endpoints" count={report.affected_apis.length}>
              <DependentList items={report.affected_apis} />
            </Section>
            <Section title="Affected service components" count={report.affected_services.length}>
              <DependentList items={report.affected_services} />
            </Section>
            <Section title="Affected tests" count={report.affected_tests.length}>
              <DependentList items={report.affected_tests} />
            </Section>
            <Section title="External dependencies" count={report.external_dependencies.length}>
              {report.external_dependencies.length === 0 ? (
                <p className="text-xs text-(--text-faint)">None found.</p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {report.external_dependencies.map((d, i) => (
                    <span
                      key={i}
                      className={cn(
                        "rounded-full border px-2 py-0.5 font-mono text-xs",
                        d.category === "database"
                          ? "border-(--slate)/40 text-(--slate)"
                          : "border-(--border) text-(--text-soft)",
                      )}
                    >
                      {d.name}
                    </span>
                  ))}
                </div>
              )}
            </Section>
          </div>

          {report.detection_notes.length > 0 && (
            <ul className="mt-5 flex flex-col gap-1 border-t border-(--border) pt-4">
              {report.detection_notes.map((n, i) => (
                <li key={i} className="text-xs text-(--text-faint) italic">
                  {n}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
