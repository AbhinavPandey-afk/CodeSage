import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { AskResponse } from "../api/types";

const SUGGESTIONS = [
  "How does authentication work?",
  "What happens when the application starts?",
  "Where is the database accessed?",
];

export function AskPanel({ repoId }: { repoId: string }) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);

  const ask = async (q: string) => {
    if (!q.trim() || loading) return;
    setLoading(true);
    setError(null);
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

  return (
    <div className="ask-panel">
      <form onSubmit={handleSubmit} className="ask-form">
        <input
          type="text"
          placeholder="Ask a question about this repository…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={loading}
        />
        <button type="submit" disabled={loading || !question.trim()}>
          {loading ? "Thinking…" : "Ask"}
        </button>
      </form>

      <div className="ask-suggestions">
        {SUGGESTIONS.map((s) => (
          <button key={s} className="suggestion-chip" onClick={() => { setQuestion(s); ask(s); }}>
            {s}
          </button>
        ))}
      </div>

      {error && <p className="form-error">{error}</p>}

      {result && (
        <div className="ask-result">
          <div className="answer-block">
            <span className={`confidence-pill confidence-${result.confidence_label.toLowerCase()}`}>
              {result.confidence_label} · {(result.confidence_score * 100).toFixed(0)}%
            </span>
            <p>{result.answer}</p>
          </div>

          {result.evidence.length > 0 && (
            <div className="evidence-block">
              <h4>Evidence</h4>
              {result.evidence.map((e, i) => (
                <div key={i} className="evidence-item">
                  <div className="evidence-title">
                    <span className={`symbol-tag symbol-${e.symbol_type}`}>{e.symbol_type}</span>
                    <code>{e.qualified_name}</code>
                  </div>
                  <div className="evidence-location">
                    {e.file_path}:{e.start_line}-{e.end_line}
                  </div>
                  {e.related.length > 0 && (
                    <ul className="evidence-related">
                      {e.related.map((r, j) => (
                        <li key={j}>
                          {r.relationship_type} ({r.direction}) → {r.qualified_name}{" "}
                          <span className="conf">conf {r.confidence.toFixed(2)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
