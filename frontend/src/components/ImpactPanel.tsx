import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Dependent, ImpactReport, SymbolSearchResult } from "../api/types";

function DependentList({ items, limit = 8 }: { items: Dependent[]; limit?: number }) {
  if (items.length === 0) return <p className="hint">None found.</p>;
  return (
    <ul className="dependent-list">
      {items.slice(0, limit).map((d) => (
        <li key={d.uid}>
          <code>{d.qualified_name}</code>
          <span className="dependent-loc">{d.file_path}:{d.start_line}</span>
        </li>
      ))}
      {items.length > limit && <li className="dependent-more">…and {items.length - limit} more</li>}
    </ul>
  );
}

export function ImpactPanel({ repoId }: { repoId: string }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SymbolSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState<SymbolSearchResult | null>(null);
  const [report, setReport] = useState<ImpactReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!query.trim() || selected?.qualified_name === query) {
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
  }, [query, repoId, selected]);

  const runAnalysis = async (symbol: SymbolSearchResult) => {
    setSelected(symbol);
    setQuery(symbol.qualified_name);
    setResults([]);
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

  return (
    <div className="impact-panel">
      <div className="impact-search">
        <input
          type="text"
          placeholder="Search a function, method, or class — e.g. PaymentService.process"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setSelected(null);
          }}
        />
        {searching && <span className="impact-search-spinner">searching…</span>}
        {results.length > 0 && (
          <ul className="impact-results">
            {results.map((r) => (
              <li key={r.uid} onClick={() => runAnalysis(r)}>
                <span className="symbol-tag">{r.symbol_type}</span>
                <code>{r.qualified_name}</code>
              </li>
            ))}
          </ul>
        )}
      </div>

      {loading && <p className="hint">Analyzing impact…</p>}
      {error && <p className="form-error">{error}</p>}

      {report && (
        <div className="impact-report">
          <div className="impact-header">
            <div>
              <span className="symbol-tag">{report.target_symbol_type}</span>
              <code className="impact-target-name">{report.target_qualified_name}</code>
            </div>
            <span className={`risk-pill risk-${report.risk_level.toLowerCase()}`}>
              {report.risk_level} RISK
            </span>
          </div>

          <p className="impact-explanation">{report.explanation}</p>

          <div className="risk-signals">
            {report.risk_signals.map((s, i) => (
              <div key={i} className="risk-signal">
                <span className="rs-name">{s.name}</span>
                <span className="rs-value">{s.value}</span>
                <span className="rs-points">+{s.points}</span>
              </div>
            ))}
          </div>

          <div className="impact-grid">
            <div className="impact-cell">
              <h4>Direct dependents ({report.direct_dependents.length})</h4>
              <DependentList items={report.direct_dependents} />
            </div>
            <div className="impact-cell">
              <h4>Indirect dependents ({report.indirect_dependents.length})</h4>
              <DependentList items={report.indirect_dependents} />
            </div>
            <div className="impact-cell">
              <h4>Affected API endpoints ({report.affected_apis.length})</h4>
              <DependentList items={report.affected_apis} />
            </div>
            <div className="impact-cell">
              <h4>Affected service components ({report.affected_services.length})</h4>
              <DependentList items={report.affected_services} />
            </div>
            <div className="impact-cell">
              <h4>Affected tests ({report.affected_tests.length})</h4>
              <DependentList items={report.affected_tests} />
            </div>
            <div className="impact-cell">
              <h4>External dependencies ({report.external_dependencies.length})</h4>
              {report.external_dependencies.length === 0 ? (
                <p className="hint">None found.</p>
              ) : (
                <div className="chips">
                  {report.external_dependencies.map((d, i) => (
                    <span key={i} className={`chip chip-${d.category}`}>{d.name}</span>
                  ))}
                </div>
              )}
            </div>
          </div>

          <ul className="detection-notes">
            {report.detection_notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
