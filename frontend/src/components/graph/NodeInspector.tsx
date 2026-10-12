import { ArrowDownLeft, ArrowUpRight, X } from "lucide-react";
import type { ArchitectureComponent, GraphEdge, GraphNode, Smell } from "@/api/types";
import { ConfidenceBadge } from "@/components/evidence/ConfidenceBadge";
import { EntityActions } from "@/components/graph/EntityActions";
import { structuralSummary } from "@/lib/evidenceExplorer";
import { ROLE_LABELS, SMELL_TYPE_LABELS } from "@/lib/labels";
import { useInvestigation } from "@/lib/investigation";

const RELATIONSHIP_LIST_LIMIT = 6;

function StatBlock({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex flex-col">
      <strong className="font-mono text-lg text-(--text) tabular-nums">{value}</strong>
      <span className="text-[0.6rem] font-medium tracking-wide text-(--text-faint) uppercase">{label}</span>
    </div>
  );
}

function EdgeRow({
  edge,
  neighborName,
  onJump,
}: {
  edge: GraphEdge;
  neighborName: string;
  onJump: () => void;
}) {
  return (
    <li>
      <button
        onClick={onJump}
        className="flex w-full items-center gap-1.5 rounded px-1.5 py-1 text-left text-xs hover:bg-(--bg-sunken)"
      >
        <span className="shrink-0 rounded bg-(--bg-sunken) px-1 py-0.5 font-mono text-[0.6rem] font-semibold tracking-wide text-(--accent-text) uppercase">
          {edge.relationship_type}
        </span>
        <code className="min-w-0 truncate text-(--text-soft)">{neighborName}</code>
      </button>
    </li>
  );
}

/** Evidence-style detail panel for a selected graph node (PART 3): identity,
 * reconstruction context, structural summary, incoming/outgoing
 * relationships, related findings, and contextual actions — no LLM anywhere
 * in this component, every field traces back to a real API response. */
export function NodeInspector({
  node,
  edges,
  nodesByUid,
  component,
  findings,
  onClose,
  onJumpToNode,
}: {
  node: GraphNode;
  edges: GraphEdge[];
  nodesByUid: Map<string, GraphNode>;
  component: ArchitectureComponent | null;
  findings: Smell[];
  onClose: () => void;
  onJumpToNode: (uid: string) => void;
}) {
  const { navigate } = useInvestigation();
  const summary = structuralSummary(edges, node.uid);
  const incoming = edges.filter((e) => e.target_uid === node.uid);
  const outgoing = edges.filter((e) => e.source_uid === node.uid);

  return (
    <div className="flex h-full flex-col rounded-lg border border-(--border) bg-(--bg-raised) shadow-sm">
      <div className="flex shrink-0 items-start justify-between gap-2 border-b border-(--border) px-3.5 py-2.5">
        <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.62rem] font-semibold tracking-wide text-(--text-faint) uppercase">
          {node.symbol_type}
        </span>
        <button onClick={onClose} aria-label="Close inspector" className="shrink-0 text-(--text-faint) hover:text-(--text)">
          <X className="size-3.5" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3.5 py-3">
        {/* IDENTITY */}
        <code className="block text-sm break-words text-(--text)">{node.qualified_name}</code>
        <dl className="mt-2.5 flex flex-col gap-1.5">
          <div>
            <dt className="text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">File</dt>
            <dd className="font-mono text-xs break-all text-(--text-soft)">{node.file_path}</dd>
          </div>
          <div>
            <dt className="text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">Lines</dt>
            <dd className="font-mono text-xs text-(--text-soft)">
              {node.start_line}–{node.end_line}
            </dd>
          </div>
        </dl>

        {/* RECONSTRUCTION CONTEXT */}
        {component && (
          <div className="mt-3.5 border-t border-(--border) pt-3">
            <h3 className="mb-1.5 text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">
              Reconstruction context
            </h3>
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <code className="text-(--text-soft)">{component.name}</code>
              <span className="rounded bg-(--bg-sunken) px-1.5 py-0.5 font-mono text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                {ROLE_LABELS[component.role] ?? component.role}
              </span>
              <ConfidenceBadge label={component.confidence_label} />
            </div>
          </div>
        )}

        {/* STRUCTURAL SUMMARY */}
        <div className="mt-3.5 border-t border-(--border) pt-3">
          <h3 className="mb-1.5 text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">
            Structural summary
          </h3>
          <div className="flex gap-5">
            <StatBlock value={summary.total} label="Total" />
            <StatBlock value={summary.incoming} label="Incoming" />
            <StatBlock value={summary.outgoing} label="Outgoing" />
          </div>
        </div>

        {/* RELATIONSHIPS */}
        {(incoming.length > 0 || outgoing.length > 0) && (
          <div className="mt-3.5 border-t border-(--border) pt-3">
            <h3 className="mb-1.5 text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">
              Relationships
            </h3>
            {incoming.length > 0 && (
              <div className="mb-2">
                <p className="mb-1 flex items-center gap-1 text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                  <ArrowDownLeft className="size-3" /> Incoming ({incoming.length})
                </p>
                <ul className="flex flex-col gap-0.5">
                  {incoming.slice(0, RELATIONSHIP_LIST_LIMIT).map((e, i) => (
                    <EdgeRow
                      key={i}
                      edge={e}
                      neighborName={nodesByUid.get(e.source_uid)?.name ?? e.source_uid}
                      onJump={() => onJumpToNode(e.source_uid)}
                    />
                  ))}
                </ul>
                {incoming.length > RELATIONSHIP_LIST_LIMIT && (
                  <p className="mt-0.5 text-[0.65rem] text-(--text-faint) italic">
                    …and {incoming.length - RELATIONSHIP_LIST_LIMIT} more
                  </p>
                )}
              </div>
            )}
            {outgoing.length > 0 && (
              <div>
                <p className="mb-1 flex items-center gap-1 text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">
                  <ArrowUpRight className="size-3" /> Outgoing ({outgoing.length})
                </p>
                <ul className="flex flex-col gap-0.5">
                  {outgoing.slice(0, RELATIONSHIP_LIST_LIMIT).map((e, i) => (
                    <EdgeRow
                      key={i}
                      edge={e}
                      neighborName={nodesByUid.get(e.target_uid)?.name ?? e.target_uid}
                      onJump={() => onJumpToNode(e.target_uid)}
                    />
                  ))}
                </ul>
                {outgoing.length > RELATIONSHIP_LIST_LIMIT && (
                  <p className="mt-0.5 text-[0.65rem] text-(--text-faint) italic">
                    …and {outgoing.length - RELATIONSHIP_LIST_LIMIT} more
                  </p>
                )}
              </div>
            )}
            <p className="mt-1.5 text-[0.65rem] text-(--text-faint) italic">
              Edges shown are limited to the entities currently loaded in this graph view.
            </p>
          </div>
        )}

        {/* RELATED FINDINGS */}
        {findings.length > 0 && (
          <div className="mt-3.5 border-t border-(--border) pt-3">
            <h3 className="mb-1.5 text-[0.6rem] font-semibold tracking-wide text-(--text-faint) uppercase">
              Related findings ({findings.length})
            </h3>
            <ul className="flex flex-col gap-1">
              {findings.slice(0, 3).map((s, i) => (
                <li key={i}>
                  <button
                    onClick={() => navigate("smells")}
                    className="block w-full truncate rounded px-1.5 py-1 text-left text-xs text-(--text-soft) hover:bg-(--bg-sunken)"
                    title={s.title}
                  >
                    <span
                      className={
                        s.severity === "HIGH"
                          ? "text-(--bad)"
                          : s.severity === "MEDIUM"
                            ? "text-(--warn)"
                            : "text-(--text-faint)"
                      }
                    >
                      ●
                    </span>{" "}
                    {s.title}
                    <span className="ml-1 text-(--text-faint)">
                      · {SMELL_TYPE_LABELS[s.smell_type] ?? s.smell_type}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* ACTIONS */}
        <div className="mt-3.5 border-t border-(--border) pt-3">
          <EntityActions
            qualifiedName={node.qualified_name}
            componentId={component?.id ?? null}
            findingsCount={findings.length}
          />
        </div>

        <p className="mt-3 text-[0.7rem] text-(--text-faint) italic">
          Ctrl/Cmd-click a second node, or use search, to investigate the relationship between them.
        </p>
      </div>
    </div>
  );
}
