import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Repository, RepositoryStatus } from "@/api/types";

const STAGES: { key: RepositoryStatus; label: string; detail: string }[] = [
  { key: "cloning", label: "Repository excavated", detail: "Workspace cloned, sandboxed and size-checked" },
  { key: "cloned", label: "Languages detected", detail: "Python / JavaScript / TypeScript / Java / C++" },
  { key: "parsing", label: "Syntax parsed", detail: "Symbols and relationships extracted via Tree-sitter" },
  { key: "building_graph", label: "Knowledge graph built", detail: "Cross-file resolution loaded into Neo4j" },
  { key: "embedding", label: "Evidence index prepared", detail: "Vector retrieval index generated" },
  { key: "ready", label: "Site ready", detail: "Repository is ready for investigation" },
];

function stageState(stageKey: RepositoryStatus, current: RepositoryStatus): "done" | "active" | "pending" {
  const order = STAGES.map((s) => s.key);
  const currentIdx = order.indexOf(current);
  const stageIdx = order.indexOf(stageKey);
  if (current === "failed") return stageIdx <= currentIdx ? "done" : "pending";
  if (stageIdx < currentIdx) return "done";
  if (stageIdx === currentIdx) return "active";
  return "pending";
}

const STATS: { key: keyof Pick<Repository, "file_count" | "symbol_count" | "relationship_count">; label: string }[] = [
  { key: "file_count", label: "Files" },
  { key: "symbol_count", label: "Symbols" },
  { key: "relationship_count", label: "Relationships" },
];

export function PipelineProgress({ repository, onReset }: { repository: Repository; onReset?: () => void }) {
  return (
    <div className="mx-auto max-w-2xl px-6 py-10">
      <div className="mb-6 flex items-baseline justify-between gap-3">
        <span className="font-mono text-sm font-semibold text-(--text)">
          {repository.owner}/{repository.name}
        </span>
        <span className="font-mono text-xs text-(--text-faint) uppercase">Excavation log</span>
      </div>

      {repository.status === "failed" ? (
        <div className="rounded-lg border border-(--bad)/30 bg-(--bad)/8 p-5">
          <p className="text-sm font-medium text-(--bad)">Excavation failed</p>
          <p className="mt-1.5 text-sm text-(--text-soft)">{repository.error}</p>
          {onReset && (
            <Button variant="outline" size="sm" className="mt-4" onClick={onReset}>
              Try another repository
            </Button>
          )}
        </div>
      ) : (
        <ol className="flex flex-col">
          {STAGES.map((stage, i) => {
            const state = stageState(stage.key, repository.status);
            return (
              <li key={stage.key} className="relative flex gap-3.5 pb-6 last:pb-0">
                {i < STAGES.length - 1 && (
                  <span
                    className={cn(
                      "absolute top-5 left-[9px] h-full w-px",
                      state === "done" ? "bg-(--ok)/40" : "bg-(--border)",
                    )}
                  />
                )}
                <span className="relative z-10 flex size-[18px] shrink-0 items-center justify-center pt-0.5">
                  {state === "done" && <CheckCircle2 className="size-[18px] text-(--ok)" strokeWidth={2} />}
                  {state === "active" && (
                    <Loader2 className="size-[18px] animate-spin text-(--accent)" strokeWidth={2} />
                  )}
                  {state === "pending" && <Circle className="size-[18px] text-(--border-strong)" strokeWidth={2} />}
                </span>
                <div>
                  <p
                    className={cn(
                      "text-sm font-medium",
                      state === "pending" ? "text-(--text-faint)" : "text-(--text)",
                    )}
                  >
                    {stage.label}
                  </p>
                  <p className="mt-0.5 text-xs text-(--text-faint)">{stage.detail}</p>
                </div>
              </li>
            );
          })}
        </ol>
      )}

      {repository.status === "ready" && (
        <div className="mt-2 flex gap-6 border-t border-(--border) pt-5">
          {STATS.map((stat) => (
            <div key={stat.key} className="flex flex-col">
              <strong className="font-mono text-lg text-(--text) tabular-nums">{repository[stat.key]}</strong>
              <span className="text-[0.68rem] font-medium tracking-wide text-(--text-faint) uppercase">
                {stat.label}
              </span>
            </div>
          ))}
          <div className="flex flex-col">
            <strong className="font-mono text-lg text-(--text) tabular-nums">
              {Object.keys(repository.languages).length}
            </strong>
            <span className="text-[0.68rem] font-medium tracking-wide text-(--text-faint) uppercase">
              Languages
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
