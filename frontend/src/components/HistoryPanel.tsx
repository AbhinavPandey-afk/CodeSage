import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ComponentHistory, HistoryReport } from "../api/types";

function ComponentHistoryRow({ entry }: { entry: ComponentHistory }) {
  return (
    <div className="hist-component">
      <div className="hist-component-header">
        <span className="arch-role-pill">{entry.role}</span>
        <code>{entry.component_name}</code>
        <span className="hist-commit-count">
          {entry.commit_count} commit{entry.commit_count === 1 ? "" : "s"}
        </span>
      </div>
      <p className="hint hist-dates">
        First seen {new Date(entry.first_seen).toLocaleDateString()} — last changed{" "}
        {new Date(entry.last_changed).toLocaleDateString()}
      </p>
      <p className="hist-intro">
        Introduced in <code className="hist-sha">{entry.introduction_commit.short_sha}</code> "
        {entry.introduction_commit.subject}" by {entry.introduction_commit.author_name}
      </p>
      {entry.top_authors.length > 0 && (
        <div className="chips">
          {entry.top_authors.map(([name, count]) => (
            <span key={name} className="chip">
              {name} ({count})
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function HistoryPanel({ repoId }: { repoId: string }) {
  const [report, setReport] = useState<HistoryReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setReport(null);
    setError(null);
    api
      .getHistory(repoId)
      .then(setReport)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to reconstruct history."));
  }, [repoId]);

  if (error) return <p className="form-error">{error}</p>;
  if (!report) return <p className="hint">Analyzing commit history…</p>;

  return (
    <div className="hist-panel">
      <p className="arch-intro">
        Reconstructed from {report.commits_analyzed} commit{report.commits_analyzed === 1 ? "" : "s"} of this
        repository's own Git history.
      </p>

      {report.components.length > 0 && (
        <div className="hist-components">
          <h4>Most historically active components</h4>
          {report.components.slice(0, 10).map((c) => (
            <ComponentHistoryRow key={c.component_id} entry={c} />
          ))}
        </div>
      )}

      {report.recent_commits.length > 0 && (
        <div className="hist-recent">
          <h4>Recent commits</h4>
          <ul className="hist-commit-list">
            {report.recent_commits.map((c) => (
              <li key={c.sha}>
                <code className="hist-sha">{c.short_sha}</code>
                <span className="hist-subject">{c.subject}</span>
                <span className="hint">
                  {c.author_name} · {new Date(c.authored_date).toLocaleDateString()}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <ul className="detection-notes">
        {report.detection_notes.map((n, i) => (
          <li key={i}>{n}</li>
        ))}
      </ul>
    </div>
  );
}
