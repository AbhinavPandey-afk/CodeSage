import type { ReactNode } from "react";
import type { EntryPoint, FlowHop } from "@/api/types";
import { ConfidenceBadge } from "@/components/evidence/ConfidenceBadge";
import { confidenceLabel } from "@/lib/flowModel";
import { ROLE_LABELS } from "@/lib/labels";
import { parseRouteHint } from "@/lib/routeHint";

function Field({ label, value }: { label: string; value: ReactNode }) {
  if (!value) return null;
  return (
    <div className="min-w-0">
      <dt className="text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">{label}</dt>
      <dd className="truncate text-sm text-(--text)">{value}</dd>
    </div>
  );
}

function shortName(qualifiedName: string): string {
  const parts = qualifiedName.split(".");
  return parts[parts.length - 1] || qualifiedName;
}

/** "TRACE CONTEXT" — a quick-read summary of what's currently selected,
 * showing only fields the backend actually provided (CLAUDE.md §9: "only
 * show fields actually available"). Reads the raw entry hop directly rather
 * than a level-specific TraceNode, so it stays identical across Understand,
 * Components, and Symbols instead of depending on which view built it. */
export function TraceContext({ entry, entryHop, language }: { entry: EntryPoint; entryHop: FlowHop; language: string | null }) {
  const { method, path } = parseRouteHint(entry.route_hint);
  const operation = method && path ? `${method} ${path}` : (entry.route_hint ?? null);

  return (
    <dl className="mb-5 grid grid-cols-2 gap-x-6 gap-y-3 rounded-lg border border-(--border) bg-(--bg-raised) p-4 sm:grid-cols-3 lg:grid-cols-6">
      <Field label="Operation" value={operation ? <code className="font-mono">{operation}</code> : null} />
      <Field label="Entry point" value={<code className="font-mono">{shortName(entry.qualified_name)}()</code>} />
      <Field
        label="Component"
        value={entryHop.component_name ? `${entryHop.component_name}${entryHop.component_role ? ` (${ROLE_LABELS[entryHop.component_role]})` : ""}` : null}
      />
      <Field label="Language" value={language} />
      <Field label="Reconstruction" value="Static" />
      <Field label="Confidence" value={<ConfidenceBadge label={confidenceLabel(entryHop.confidence)} />} />
    </dl>
  );
}
