import { useState } from "react";
import "./App.css";
import { api } from "./api/client";
import { ArchitecturePanel } from "./components/ArchitecturePanel";
import { AskPanel } from "./components/AskPanel";
import { ExecutionFlowPanel } from "./components/ExecutionFlowPanel";
import { GraphView } from "./components/GraphView";
import { ImpactPanel } from "./components/ImpactPanel";
import { OptimizationPanel } from "./components/OptimizationPanel";
import { PipelineProgress } from "./components/PipelineProgress";
import { RepositoryForm } from "./components/RepositoryForm";
import { SmellsPanel } from "./components/SmellsPanel";
import { useRepositoryPolling } from "./hooks/useRepositoryPolling";

type Tab = "architecture" | "flow" | "graph" | "smells" | "optimization" | "impact" | "ask";

function App() {
  const [repoId, setRepoId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("architecture");
  const repository = useRepositoryPolling(repoId);

  const handleSubmit = async (url: string) => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const repo = await api.createRepository(url);
      setRepoId(repo.id);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to submit repository.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <span className="brand">CodeBase Archeologist</span>
        <span className="tagline">Evidence-driven software architecture reconstruction</span>
      </header>

      <main className="app-main">
        {!repository && (
          <RepositoryForm onSubmit={handleSubmit} submitting={submitting} error={submitError} />
        )}

        {repository && (
          <>
            <PipelineProgress repository={repository} />

            {repository.status === "ready" && (
              <>
                <div className="tabs">
                  <button
                    className={tab === "architecture" ? "tab active" : "tab"}
                    onClick={() => setTab("architecture")}
                  >
                    Architecture
                  </button>
                  <button className={tab === "flow" ? "tab active" : "tab"} onClick={() => setTab("flow")}>
                    Execution flow
                  </button>
                  <button className={tab === "graph" ? "tab active" : "tab"} onClick={() => setTab("graph")}>
                    Evidence explorer
                  </button>
                  <button className={tab === "smells" ? "tab active" : "tab"} onClick={() => setTab("smells")}>
                    Architecture analysis
                  </button>
                  <button
                    className={tab === "optimization" ? "tab active" : "tab"}
                    onClick={() => setTab("optimization")}
                  >
                    Optimization
                  </button>
                  <button className={tab === "impact" ? "tab active" : "tab"} onClick={() => setTab("impact")}>
                    Impact &amp; risk
                  </button>
                  <button className={tab === "ask" ? "tab active" : "tab"} onClick={() => setTab("ask")}>
                    Ask the Archeologist
                  </button>
                </div>
                {tab === "architecture" && <ArchitecturePanel repoId={repository.id} />}
                {tab === "flow" && <ExecutionFlowPanel repoId={repository.id} />}
                {tab === "graph" && <GraphView repoId={repository.id} />}
                {tab === "smells" && <SmellsPanel repoId={repository.id} />}
                {tab === "optimization" && <OptimizationPanel repoId={repository.id} />}
                {tab === "impact" && <ImpactPanel repoId={repository.id} />}
                {tab === "ask" && <AskPanel repoId={repository.id} />}
              </>
            )}

            {repository.status !== "ready" && repository.status !== "failed" && (
              <p className="hint">Analysis in progress — this page updates automatically.</p>
            )}
            {repository.status === "failed" && (
              <button className="retry-button" onClick={() => setRepoId(null)}>
                Try another repository
              </button>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default App;
