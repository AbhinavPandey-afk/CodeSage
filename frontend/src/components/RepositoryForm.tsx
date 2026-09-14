import { ArrowRight } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";

interface Props {
  onSubmit: (url: string) => void;
  submitting: boolean;
  error: string | null;
}

const STAGES = ["Excavate", "Parse", "Resolve", "Map", "Reconstruct", "Analyze"];

export function RepositoryForm({ onSubmit, submitting, error }: Props) {
  const [url, setUrl] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (url.trim()) onSubmit(url.trim());
  };

  return (
    <div className="mx-auto flex min-h-[calc(100vh-3.5rem)] max-w-xl flex-col items-center justify-center px-6 py-16 text-center">
      <span className="font-mono text-xs font-semibold tracking-[0.2em] text-(--accent-text) uppercase">
        Site Survey
      </span>
      <h1 className="font-display mt-3 text-4xl font-medium tracking-tight text-(--text) sm:text-[2.75rem]">
        Excavate a repository.
      </h1>
      <p className="mt-3 max-w-md text-[0.95rem] leading-relaxed text-(--text-soft)">
        Point CodeBase Archeologist at a public GitHub repository. It reconstructs the
        architecture from structural evidence — the graph provides the facts, the LLM only
        explains them.
      </p>

      <form onSubmit={handleSubmit} className="mt-9 flex w-full flex-col gap-2.5 sm:flex-row">
        <input
          type="text"
          placeholder="https://github.com/owner/repository"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={submitting}
          className="h-11 flex-1 rounded-md border border-(--border) bg-(--bg-raised) px-3.5 font-mono text-sm text-(--text) placeholder:text-(--text-faint) focus:border-(--accent) focus:outline-none"
        />
        <Button
          type="submit"
          disabled={submitting || !url.trim()}
          size="lg"
          className="h-11 gap-1.5 bg-(--accent) text-(--bg-raised) hover:bg-(--accent)/88"
        >
          {submitting ? "Beginning excavation…" : "Begin excavation"}
          {!submitting && <ArrowRight className="size-4" />}
        </Button>
      </form>
      {error && <p className="mt-3 text-sm text-(--bad)">{error}</p>}

      <div className="mt-14 grid w-full grid-cols-3 gap-x-2 gap-y-6 sm:flex sm:items-start sm:gap-0">
        {STAGES.map((stage, i) => (
          <div key={stage} className="flex items-start sm:flex-1 sm:last:flex-none">
            <div className="flex flex-col items-center gap-1.5">
              <span className="font-mono text-[0.65rem] text-(--text-faint) tabular-nums">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="text-xs font-medium whitespace-nowrap text-(--text-soft)">{stage}</span>
            </div>
            {i < STAGES.length - 1 && (
              <span className="stratum-rule mt-[9px] ml-1.5 hidden flex-1 sm:ml-2 sm:block" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
