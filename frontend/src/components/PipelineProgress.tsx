import type { Repository, RepositoryStatus } from "../api/types";

const STAGES: { key: RepositoryStatus; label: string }[] = [
  { key: "cloning", label: "Cloning repository" },
  { key: "cloned", label: "Detecting languages" },
  { key: "parsing", label: "Parsing source files" },
  { key: "building_graph", label: "Building knowledge graph" },
  { key: "embedding", label: "Generating embeddings" },
  { key: "ready", label: "Repository ready" },
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

export function PipelineProgress({ repository }: { repository: Repository }) {
  return (
    <div className="pipeline">
      <div className="pipeline-header">
        <span className="repo-name">
          {repository.owner}/{repository.name}
        </span>
        <span className={`status-pill status-${repository.status}`}>{repository.status}</span>
      </div>

      {repository.status === "failed" ? (
        <p className="pipeline-error">{repository.error}</p>
      ) : (
        <ul className="pipeline-stages">
          {STAGES.map((stage) => (
            <li key={stage.key} className={`stage stage-${stageState(stage.key, repository.status)}`}>
              <span className="stage-dot" />
              {stage.label}
            </li>
          ))}
        </ul>
      )}

      {repository.status === "ready" && (
        <div className="pipeline-stats">
          <div>
            <strong>{repository.file_count}</strong>
            <span>files</span>
          </div>
          <div>
            <strong>{repository.symbol_count}</strong>
            <span>symbols</span>
          </div>
          <div>
            <strong>{repository.relationship_count}</strong>
            <span>relationships</span>
          </div>
          <div>
            <strong>{Object.keys(repository.languages).length}</strong>
            <span>languages</span>
          </div>
        </div>
      )}
    </div>
  );
}
