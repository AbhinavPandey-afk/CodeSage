import { useState } from "react";
import "./App.css";
import { api } from "./api/client";
import { AppShell } from "./components/layout/AppShell";
import { PageHeader } from "./components/layout/PageHeader";
import { ArchitecturePanel } from "./components/ArchitecturePanel";
import { AskPanel } from "./components/AskPanel";
import { ExecutionFlowPanel } from "./components/ExecutionFlowPanel";
import { GraphView } from "./components/GraphView";
import { HistoryPanel } from "./components/HistoryPanel";
import { ImpactPanel } from "./components/ImpactPanel";
import { OptimizationPanel } from "./components/OptimizationPanel";
import { PipelineProgress } from "./components/PipelineProgress";
import { RepositoryForm } from "./components/RepositoryForm";
import { RepositoryOverview } from "./components/RepositoryOverview";
import { SmellsPanel } from "./components/SmellsPanel";
import { useRepositoryPolling } from "./hooks/useRepositoryPolling";
import { InvestigationProvider } from "./lib/investigation";
import { NAV_GROUPS, type Tab } from "./lib/navigation";

const NAV_ITEMS = NAV_GROUPS.flatMap((g) => g.items);

function App() {
  const [repoId, setRepoId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
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

  const reset = () => setRepoId(null);
  const activeItem = NAV_ITEMS.find((i) => i.tab === tab);

  return (
    <AppShell repository={repository} tab={tab} onTabChange={setTab} onReset={reset}>
      {!repository && (
        <RepositoryForm onSubmit={handleSubmit} submitting={submitting} error={submitError} />
      )}

      {repository && repository.status !== "ready" && (
        <PipelineProgress repository={repository} onReset={repository.status === "failed" ? reset : undefined} />
      )}

      {repository && repository.status === "ready" && (
        <InvestigationProvider tab={tab} onTabChange={setTab}>
          <div className="mx-auto max-w-5xl px-5 py-8 sm:px-8">
            {activeItem && <PageHeader title={activeItem.label} question={activeItem.question} />}
            {tab === "overview" && <RepositoryOverview repoId={repository.id} repository={repository} />}
            {tab === "architecture" && <ArchitecturePanel repoId={repository.id} />}
            {tab === "flow" && <ExecutionFlowPanel repoId={repository.id} />}
            {tab === "graph" && <GraphView repoId={repository.id} />}
            {tab === "smells" && <SmellsPanel repoId={repository.id} />}
            {tab === "optimization" && <OptimizationPanel repoId={repository.id} />}
            {tab === "impact" && <ImpactPanel repoId={repository.id} />}
            {tab === "history" && <HistoryPanel repoId={repository.id} />}
            {tab === "ask" && <AskPanel repoId={repository.id} />}
          </div>
        </InvestigationProvider>
      )}
    </AppShell>
  );
}

export default App;
