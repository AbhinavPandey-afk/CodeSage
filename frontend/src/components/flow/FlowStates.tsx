import { AlertTriangle, Compass, RotateCcw, Route } from "lucide-react";

const STEPS = ["Detecting entry point", "Following resolved calls", "Resolving components", "Building the trace", "Preparing evidence"];

export function TraceLoadingState() {
  return (
    <div className="flex h-[420px] flex-col items-center justify-center gap-4 rounded-lg border border-(--border) bg-(--bg-raised) px-6">
      <div className="flex items-center gap-2 text-sm font-medium text-(--text)">
        <span className="size-1.5 animate-pulse rounded-full bg-(--accent)" />
        Reconstructing trace…
      </div>
      <ol className="flex flex-col gap-1.5">
        {STEPS.map((step, i) => (
          <li
            key={step}
            className="flex items-center gap-2 text-xs text-(--text-faint)"
            style={{ animation: `flow-step-pulse 2.2s ease-in-out ${i * 0.25}s infinite` }}
          >
            <span className="font-mono tabular-nums">{i + 1}.</span>
            {step}
          </li>
        ))}
      </ol>
      <style>{`@keyframes flow-step-pulse { 0%, 100% { opacity: 0.45; } 50% { opacity: 1; } }`}</style>
    </div>
  );
}

export function NoEntryPointsState() {
  return (
    <div className="flex h-[280px] flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-(--border) px-6 text-center">
      <Route className="size-6 text-(--text-faint)" />
      <p className="text-sm font-medium text-(--text)">No API entry points were detected</p>
      <p className="max-w-sm text-xs text-(--text-faint)">
        Execution Flow starts from a route-decorated function or method (e.g. a Flask/Express/Spring route). This
        repository's parsed symbols don't include one the entry-point detector recognizes — it may not expose an
        HTTP API, or its routing style isn't covered by the current heuristic.
      </p>
    </div>
  );
}

export function EntryOnlyState() {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-(--border) px-6 py-10 text-center">
      <Compass className="size-6 text-(--text-faint)" />
      <p className="text-sm font-medium text-(--text)">Only the entry point was reconstructed</p>
      <p className="max-w-sm text-xs text-(--text-faint)">
        No further resolved CALLS relationships were available for this path — the function may call into code the
        resolver couldn't confidently attribute, or it genuinely does the rest of its work inline.
      </p>
    </div>
  );
}

export function TraceErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex h-[280px] flex-col items-center justify-center gap-3 rounded-lg border border-(--bad)/25 bg-(--bad)/5 px-6 text-center">
      <AlertTriangle className="size-6 text-(--bad)" />
      <div>
        <p className="text-sm font-medium text-(--text)">Trace reconstruction failed</p>
        <p className="mt-1 max-w-sm text-xs text-(--text-faint)">{message}</p>
      </div>
      <button
        onClick={onRetry}
        className="flex items-center gap-1.5 rounded-md border border-(--border) bg-(--bg-raised) px-3 py-1.5 text-xs font-medium text-(--text-soft) hover:border-(--accent)/40 hover:text-(--text)"
      >
        <RotateCcw className="size-3.5" /> Retry
      </button>
    </div>
  );
}
