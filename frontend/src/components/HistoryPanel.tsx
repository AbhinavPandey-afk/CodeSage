import { LayoutGrid } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ComponentHistory, HistoryReport } from "../api/types";
import { useInvestigation } from "@/lib/investigation";
import { ROLE_LABELS } from "../lib/labels";
import { cn } from "@/lib/utils";

const DISPLAY_LIMIT = 12;

function fmt(date: string) {
  return new Date(date).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function ComponentHistoryRow({
  entry,
  expanded,
  onToggle,
  isLast,
}: {
  entry: ComponentHistory;
  expanded: boolean;
  onToggle: () => void;
  isLast: boolean;
}) {
  const { navigate } = useInvestigation();
  return (
    <li className="relative flex gap-3.5 pb-5 last:pb-0">
      {!isLast && <span className="absolute top-5 left-[9px] h-full w-px bg-(--border)" />}
      <span className="relative z-10 mt-1.5 size-[18px] shrink-0 rounded-full border-2 border-(--accent) bg-(--bg-raised)" />

      <div className="min-w-0 flex-1">
        <button onClick={onToggle} className="flex w-full flex-wrap items-center gap-2 text-left">
          <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.62rem] font-semibold tracking-wide text-(--text-faint) uppercase">
            {ROLE_LABELS[entry.role] ?? entry.role}
          </span>
          <code className="text-sm font-medium text-(--text)">{entry.component_name}</code>
          <span className="ml-auto font-mono text-xs text-(--text-faint)">
            {entry.commit_count} commit{entry.commit_count === 1 ? "" : "s"}
          </span>
        </button>
        <p className="mt-1 text-xs text-(--text-faint)">
          Introduced {fmt(entry.introduction_commit.authored_date)} — last changed {fmt(entry.last_changed)}
        </p>

        {expanded && (
          <div className="mt-3 rounded-md border border-(--border) bg-(--bg-raised) p-3.5">
            <p className="text-xs text-(--text-soft)">
              Introduced in{" "}
              <code className="text-(--accent-text)">{entry.introduction_commit.short_sha}</code> "
              {entry.introduction_commit.subject}" by {entry.introduction_commit.author_name}
            </p>
            {entry.top_authors.length > 0 && (
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {entry.top_authors.map(([name, count]) => (
                  <span
                    key={name}
                    className="rounded-full border border-(--border) bg-(--bg-sunken) px-2 py-0.5 font-mono text-xs text-(--text-soft)"
                  >
                    {name} ({count})
                  </span>
                ))}
              </div>
            )}
            <button
              onClick={() => navigate("architecture", { componentId: entry.component_id })}
              className="mt-3 flex items-center gap-1.5 rounded-md border border-(--border) bg-(--bg) px-2.5 py-1.5 text-xs font-medium text-(--text-soft) transition-colors hover:border-(--accent)/40 hover:text-(--text)"
            >
              <LayoutGrid className="size-3.5" strokeWidth={2} />
              Show on Architecture
            </button>
          </div>
        )}
      </div>
    </li>
  );
}

export function HistoryPanel({ repoId }: { repoId: string }) {
  const [report, setReport] = useState<HistoryReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    setReport(null);
    setError(null);
    api
      .getHistory(repoId)
      .then(setReport)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to reconstruct history."));
  }, [repoId]);

  if (error) return <p className="text-sm text-(--bad)">{error}</p>;
  if (!report)
    return (
      <div className="flex flex-col gap-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-16 animate-pulse rounded-md bg-(--bg-sunken)" />
        ))}
      </div>
    );

  const timeline = [...report.components]
    .sort((a, b) => new Date(a.introduction_commit.authored_date).getTime() - new Date(b.introduction_commit.authored_date).getTime())
    .slice(0, DISPLAY_LIMIT);

  return (
    <div>
      <p className="mb-5 max-w-2xl text-sm text-(--text-soft)">
        Reconstructed from {report.commits_analyzed} commit{report.commits_analyzed === 1 ? "" : "s"} of this
        repository's own Git history
        {report.history_truncated && " — the full history may be deeper than what was analyzed"}.
      </p>

      {timeline.length > 0 && (
        <div className="mb-8">
          <p className="mb-3 text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
            Component activity, by introduction date
          </p>
          <ol>
            {timeline.map((c, i) => (
              <ComponentHistoryRow
                key={c.component_id}
                entry={c}
                expanded={expandedId === c.component_id}
                onToggle={() => setExpandedId(expandedId === c.component_id ? null : c.component_id)}
                isLast={i === timeline.length - 1}
              />
            ))}
          </ol>
          {report.components.length > DISPLAY_LIMIT && (
            <p className="mt-2 text-xs text-(--text-faint) italic">
              {report.components.length - DISPLAY_LIMIT} more component{report.components.length - DISPLAY_LIMIT === 1 ? "" : "s"} not
              shown.
            </p>
          )}
        </div>
      )}

      {report.recent_commits.length > 0 && (
        <div>
          <p className="mb-3 text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
            Recent commits
          </p>
          <ul className="flex flex-col gap-1.5">
            {report.recent_commits.map((c) => (
              <li
                key={c.sha}
                className="flex flex-wrap items-center gap-2.5 rounded-md border border-(--border) bg-(--bg-raised) px-3 py-2 text-sm"
              >
                <code className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-xs text-(--accent-text)">
                  {c.short_sha}
                </code>
                <span className={cn("flex-1 truncate text-(--text-soft)")}>{c.subject}</span>
                <span className="shrink-0 text-xs text-(--text-faint)">
                  {c.author_name} · {fmt(c.authored_date)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.detection_notes.length > 0 && (
        <ul className="mt-6 flex flex-col gap-1 border-t border-(--border) pt-4">
          {report.detection_notes.map((n, i) => (
            <li key={i} className="text-xs text-(--text-faint) italic">
              {n}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
