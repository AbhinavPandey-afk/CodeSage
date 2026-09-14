import { cn } from "@/lib/utils";
import type { RepositoryStatus } from "@/api/types";

const LABELS: Record<RepositoryStatus, string> = {
  pending: "Pending",
  cloning: "Cloning",
  cloned: "Cloned",
  parsing: "Parsing",
  building_graph: "Building graph",
  embedding: "Embedding",
  ready: "Ready",
  failed: "Failed",
};

export function StatusPill({ status, className }: { status: RepositoryStatus; className?: string }) {
  const tone =
    status === "ready" ? "ok" : status === "failed" ? "bad" : ("active" as const);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[0.68rem] font-semibold tracking-wide uppercase",
        tone === "ok" && "text-(--ok) bg-(--ok)/12 border-(--ok)/25",
        tone === "bad" && "text-(--bad) bg-(--bad)/12 border-(--bad)/25",
        tone === "active" && "text-(--accent-text) bg-(--accent-soft) border-(--accent)/30",
        className,
      )}
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          tone === "ok" && "bg-(--ok)",
          tone === "bad" && "bg-(--bad)",
          tone === "active" && "animate-pulse bg-(--accent)",
        )}
      />
      {LABELS[status]}
    </span>
  );
}
