import { useState } from "react";
import "./App.css";
import { api } from "./api/client";
import { AskPanel } from "./components/AskPanel";
import { GraphView } from "./components/GraphView";
import { ImpactPanel } from "./components/ImpactPanel";
import { PipelineProgress } from "./components/PipelineProgress";
import { RepositoryForm } from "./components/RepositoryForm";
import { SmellsPanel } from "./components/SmellsPanel";
import { useRepositoryPolling } from "./hooks/useRepositoryPolling";

type Tab = "graph" | "ask" | "smells" | "impact";

function App() {
  const [repoId, setRepoId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("graph");
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
        <span className="brand">CodeSage</span>
        <span className="tagline">AI software architecture intelligence</span>
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
                  <button className={tab === "graph" ? "tab active" : "tab"} onClick={() => setTab("graph")}>
                    Knowledge graph
                  </button>
                  <button className={tab === "ask" ? "tab active" : "tab"} onClick={() => setTab("ask")}>
                    Ask
                  </button>
                  <button className={tab === "smells" ? "tab active" : "tab"} onClick={() => setTab("smells")}>
                    Design issues
                  </button>
                  <button className={tab === "impact" ? "tab active" : "tab"} onClick={() => setTab("impact")}>
                    Impact analysis
                  </button>
                </div>
                {tab === "graph" && <GraphView repoId={repository.id} />}
                {tab === "ask" && <AskPanel repoId={repository.id} />}
                {tab === "smells" && <SmellsPanel repoId={repository.id} />}
                {tab === "impact" && <ImpactPanel repoId={repository.id} />}
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
