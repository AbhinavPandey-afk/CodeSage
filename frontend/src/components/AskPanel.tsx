import { ArrowRight, ScrollText } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { AskResponse } from "../api/types";
import { EvidenceCitation } from "@/components/ask/EvidenceCitation";
import { ConfidenceBadge } from "@/components/evidence/ConfidenceBadge";
import { useInvestigation } from "@/lib/investigation";

const SUGGESTIONS = [
  "How does authentication work?",
  "What happens when the application starts?",
  "Where is the database accessed?",
];

export function AskPanel({ repoId }: { repoId: string }) {
  const { focus } = useInvestigation();
  const consumedFocusRef = useRef(false);

  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);

  const ask = async (q: string) => {
    if (!q.trim() || loading) return;
    setLoading(true);
    setError(null);
    setAsked(q);
    try {
      setResult(await api.ask(repoId, q));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    ask(question);
  };

  useEffect(() => {
    if (consumedFocusRef.current || !focus?.presetQuestion) return;
    consumedFocusRef.current = true;
    setQuestion(focus.presetQuestion);
    void ask(focus.presetQuestion);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus]);

  return (
    <div>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          placeholder="Ask a question about this repository's reconstructed system…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={loading}
          className="h-11 flex-1 rounded-md border border-(--border) bg-(--bg-raised) px-4 text-sm text-(--text) placeholder:text-(--text-faint) focus:border-(--accent) focus:outline-none"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="flex h-11 shrink-0 items-center gap-1.5 rounded-md bg-(--accent) px-4 text-sm font-semibold text-(--bg-raised) transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "Investigating…" : "Ask"}
          {!loading && <ArrowRight className="size-4" />}
        </button>
      </form>

      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
        <span className="text-xs text-(--text-faint)">Try:</span>
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => {
              setQuestion(s);
              ask(s);
            }}
            className="rounded-full border border-(--border) bg-(--bg-raised) px-2.5 py-1 text-xs text-(--text-soft) hover:border-(--accent)/40 hover:text-(--accent-text)"
          >
            {s}
          </button>
        ))}
      </div>

      {error && <p className="mt-4 text-sm text-(--bad)">{error}</p>}

      {loading && (
        <div className="mt-6 flex flex-col gap-2">
          <div className="h-20 animate-pulse rounded-lg bg-(--bg-sunken)" />
          <div className="h-32 animate-pulse rounded-lg bg-(--bg-sunken)" />
        </div>
      )}

      {result && !loading && (
        <div className="mt-6">
          {asked && (
            <p className="mb-3 flex items-center gap-2 text-xs text-(--text-faint)">
              <ScrollText className="size-3.5" />
              {asked}
            </p>
          )}

          <div className="mb-5 rounded-lg border border-(--border) bg-(--bg-raised) p-5">
            <div className="mb-3 flex items-center gap-2">
              <ConfidenceBadge label={result.confidence_label} />
              <span className="font-mono text-xs text-(--text-faint)">
                {(result.confidence_score * 100).toFixed(0)}%
              </span>
            </div>
            <p className="text-sm leading-relaxed whitespace-pre-wrap text-(--text)">{result.answer}</p>
          </div>

          {result.evidence.length > 0 && (
            <div>
              <p className="mb-2.5 text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                Evidence ({result.evidence.length})
              </p>
              <div className="flex flex-col gap-3">
                {result.evidence.map((e, i) => (
                  <EvidenceCitation key={i} evidence={e} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
