import { ArrowDown, X } from "lucide-react";
import type { RelationshipResponse } from "@/api/types";

function ConfidenceMeter({ value }: { value: number | null }) {
  if (value === null) return null;
  return (
    <span className="inline-flex items-center gap-1 font-mono text-[0.65rem] text-(--text-faint)">
      <span className="h-1 w-8 overflow-hidden rounded-full bg-(--bg-sunken)">
        <span className="block h-full bg-(--accent)" style={{ width: `${Math.round(value * 100)}%` }} />
      </span>
      {Math.round(value * 100)}%
    </span>
  );
}

export function RelationshipTrail({
  relationship,
  onClose,
}: {
  relationship: RelationshipResponse;
  onClose: () => void;
}) {
  return (
    <div className="absolute top-3 right-3 z-10 w-80 max-w-[calc(100%-1.5rem)] rounded-lg border border-(--border) bg-(--bg-raised) shadow-lg">
      <div className="flex items-start justify-between gap-2 border-b border-(--border) px-3.5 py-2.5">
        <span className="text-[0.65rem] font-semibold tracking-wide text-(--text-faint) uppercase">
          Relationship investigation
        </span>
        <button onClick={onClose} aria-label="Close" className="shrink-0 text-(--text-faint) hover:text-(--text)">
          <X className="size-3.5" />
        </button>
      </div>

      <div className="max-h-96 overflow-y-auto px-3.5 py-3">
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <code className="min-w-0 break-words text-(--text)">{relationship.source.qualified_name}</code>
          <span className="text-(--text-faint)">↔</span>
          <code className="min-w-0 break-words text-(--text)">{relationship.target.qualified_name}</code>
        </div>

        <p className="mt-2.5 text-xs leading-relaxed text-(--text-soft)">{relationship.explanation}</p>

        {relationship.connected && relationship.steps.length > 0 ? (
          <ol className="mt-3 flex flex-col gap-0 border-t border-(--border) pt-3">
            {relationship.steps.map((step, i) => (
              <li key={i}>
                {i > 0 && <ArrowDown className="my-1 size-3 text-(--text-faint)" />}
                <div className="rounded-md border border-(--border) bg-(--bg) px-2.5 py-2">
                  <div className="flex flex-wrap items-center gap-1.5 text-[0.72rem]">
                    <code className="min-w-0 truncate text-(--text)">{step.from_qualified_name}</code>
                    <span className="rounded bg-(--bg-sunken) px-1 py-0.5 font-mono text-[0.6rem] font-semibold tracking-wide text-(--accent-text) uppercase">
                      {step.relationship_type}
                    </span>
                    <code className="min-w-0 truncate text-(--text)">{step.to_qualified_name}</code>
                  </div>
                  <div className="mt-1 flex items-center justify-between gap-2">
                    {step.source_file && (
                      <span className="font-mono text-[0.65rem] text-(--text-faint)">
                        {step.source_file}
                        {step.source_line ? `:${step.source_line}` : ""}
                      </span>
                    )}
                    <ConfidenceMeter value={step.confidence} />
                  </div>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          !relationship.connected && (
            <p className="mt-3 border-t border-(--border) pt-3 text-xs text-(--text-faint)">
              No verified relationship was found between these nodes.
            </p>
          )
        )}
      </div>
    </div>
  );
}
