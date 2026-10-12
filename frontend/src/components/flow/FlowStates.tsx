import { AlertTriangle, Compass, Network, Radar, RotateCcw, Route } from "lucide-react";
import { ConfidenceBadge } from "@/components/evidence/ConfidenceBadge";
import type { EntryPoint, FlowHop } from "@/api/types";
import { confidenceLabel } from "@/lib/flowModel";
import { useInvestigation } from "@/lib/investigation";
import { ROLE_LABELS } from "@/lib/labels";
import { isTerminalReason, TERMINAL_REASON_EXPLANATION } from "@/lib/terminalReasons";

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

function ActionButton({ icon: Icon, label, onClick }: { icon: typeof Network; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1.5 rounded-md border border-(--border) bg-(--bg) px-2.5 py-1.5 text-xs font-medium text-(--text-soft) transition-colors hover:border-(--accent)/40 hover:text-(--text) focus-visible:ring-2 focus-visible:ring-(--accent) focus-visible:outline-none"
    >
      <Icon className="size-3.5" strokeWidth={2} />
      {label}
    </button>
  );
}

/** Shown when the reconstructed trace has no downstream calls at all — per
 * spec, never a lonely node in a big empty canvas. Explains *why*, using
 * only fields the backend actually returned for this entry (component,
 * terminal boundary, confidence), plus actions that route the user to
 * somewhere they can keep investigating instead of a dead end. */
export function LimitedTraceState({ entry, entryHop }: { entry: EntryPoint; entryHop: FlowHop }) {
  const { navigate } = useInvestigation();
  const conf = confidenceLabel(entryHop.confidence);
  const terminalReason = isTerminalReason(entryHop.terminal_reason) ? entryHop.terminal_reason : null;

  return (
    <div className="rounded-lg border border-dashed border-(--border) px-6 py-8">
      <div className="mb-4 flex flex-col items-center gap-2 text-center">
        <Compass className="size-6 text-(--text-faint)" />
        <p className="text-xs font-semibold tracking-wide text-(--text-faint) uppercase">Limited trace</p>
        <p className="text-sm font-medium text-(--text)">1 source-backed step reconstructed</p>
      </div>

      <div className="mx-auto max-w-lg">
        <h4 className="mb-1 text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
          Why the trace ends
        </h4>
        <p className="mb-4 text-sm text-(--text-soft)">
          {terminalReason
            ? TERMINAL_REASON_EXPLANATION[terminalReason]
            : "No resolved CALLS relationships were found leading out of this function — it may call into code the resolver couldn't confidently attribute, dispatch dynamically, or genuinely do the rest of its work inline."}
        </p>

        <h4 className="mb-1 text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">Evidence</h4>
        <dl className="mb-4 grid grid-cols-1 gap-x-6 gap-y-2 rounded-md border border-(--border) bg-(--bg-raised) p-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">Entry point</dt>
            <dd className="truncate font-mono text-xs text-(--text)">{entry.qualified_name}</dd>
          </div>
          <div>
            <dt className="text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">Source</dt>
            <dd className="truncate font-mono text-xs text-(--text-soft)">
              {entry.file_path}:{entry.start_line}
            </dd>
          </div>
          {entryHop.component_name && (
            <div>
              <dt className="text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">Component</dt>
              <dd className="text-xs text-(--text-soft)">
                {entryHop.component_name}
                {entryHop.component_role ? ` (${ROLE_LABELS[entryHop.component_role]})` : ""}
              </dd>
            </div>
          )}
          <div>
            <dt className="text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">Confidence</dt>
            <dd>
              <ConfidenceBadge label={conf} />
            </dd>
          </div>
        </dl>

        <div className="flex flex-wrap justify-center gap-1.5">
          <ActionButton icon={Network} label="View Evidence" onClick={() => navigate("graph", { qualifiedName: entry.qualified_name })} />
          {entryHop.component_id && (
            <ActionButton icon={Compass} label="View Architecture" onClick={() => navigate("architecture", { componentId: entryHop.component_id! })} />
          )}
          <ActionButton icon={Radar} label="Explore Related Symbols" onClick={() => navigate("graph")} />
        </div>
      </div>
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
        className="flex items-center gap-1.5 rounded-md border border-(--border) bg-(--bg-raised) px-3 py-1.5 text-xs font-medium text-(--text-soft) hover:border-(--accent)/40 hover:text-(--text) focus-visible:ring-2 focus-visible:ring-(--accent) focus-visible:outline-none"
      >
        <RotateCcw className="size-3.5" /> Retry
      </button>
    </div>
  );
}
