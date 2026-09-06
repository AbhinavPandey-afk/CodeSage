# CodeBase Archeologist

An evidence-driven software archaeology platform. Point it at a GitHub
repository and it excavates the codebase into a structural knowledge graph
(Tree-sitter → Neo4j), reconstructs the architecture that repository actually
implements, analyzes it for structural problems, and answers questions with
evidence (file/line citations) and a deterministic confidence score — never
an LLM guess presented as fact.

**Excavate → Reconstruct → Analyze → Improve → Explain.** CodeBase
Archeologist is not "ChatGPT for GitHub." The graph provides the evidence;
the LLM only explains and narrates evidence the graph and static analysis
already produced — it never invents structure, relationships, or an
architecture diagram.

Full product spec: [`CLAUDE.md`](CLAUDE.md). `docs/ROADMAP.md` predates the
rebrand described in `CLAUDE.md` and is kept only as delivery history for the
foundational phases below — treat `CLAUDE.md` as the current source of truth.

## Current status

All of CLAUDE.md's reconstruction/analysis phases (§34 Phases 1–5) are now
implemented — only Phase 6 (language expansion beyond Python) remains:

- GitHub ingestion → Python parsing → Neo4j knowledge graph
- **Architecture Reconstruction** — the existing graph's files are grouped
  into architectural components, each with an inferred role and
  Confirmed/Inferred/Uncertain confidence, plus inter-component relationships
- Architecture analysis: per-symbol smells (circular dependencies, god
  classes, large functions, dead-code candidates) plus per-component
  violations (layer skips, boundary violations, circular component
  dependencies, excessive coupling) reasoned over the reconstructed
  architecture
- **Architecture Optimization** — a proposed fix for every structural
  violation found above (problem, evidence, proposed change, expected
  benefit, potential risk, deterministic risk level), a recommendation only —
  nothing is applied automatically
- **Execution Flow Reconstruction** — a static call tree from a detected API
  entry point to where it terminates in a data-access or external-integration
  component, with a PROPOSED variant that reroutes any layer-skip through the
  service layer Architecture Optimization identified
- **Historical Reconstruction** — which architectural components change most
  and when they were likely introduced, derived from the repository's own
  Git commit history (never fabricated developer intent)
- Hybrid (graph + vector) evidence-backed Q&A ("Ask the Archeologist")
- Interactive Evidence Explorer (graph view + relationship explanations)
- Change impact & risk analysis with deterministic risk scoring

Only **Python** has a working parser today; JavaScript, TypeScript, Java, and
C++ are recognized during language detection but not yet parsed (Phase 6 —
see [Supported languages](#supported-languages) below and `CLAUDE.md` §34).

## Architecture

```
GitHub URL → clone (sandboxed) → Tree-sitter parse → normalized IR
    → Neo4j knowledge graph
    → TF-IDF vector index
    → hybrid retrieval + evidence fusion → Groq (via LLMProvider) → answer
```

- **Backend**: FastAPI, Python, Neo4j, Tree-sitter
- **Frontend**: React 19 + TypeScript (Vite), Tailwind CSS, shadcn/ui, Cytoscape.js for graph visualization
- **LLM**: Groq (`api.groq.com`), behind an `LLMProvider` abstraction —
  see the note in `backend/.env.example` about the CLAUDE.md/Grok naming.

## Features

### Repository ingestion
- Accepts a GitHub URL, validates it (`https://github.com/<owner>/<repo>` only —
  blocks `ext::` transports, `file://`, path traversal, and non-GitHub hosts).
- Clones into an isolated, size/file-count-limited workspace.
- Runs analysis as a background task; the frontend polls repository status
  (`pending → cloning → parsing → building_graph → ready`) and renders a live
  pipeline progress bar.

### Multi-language architecture, Python parser implemented
- Common `LanguageParser` interface and normalized Intermediate Representation
  (`Symbol` / `Relationship`) so the graph and analysis engines never depend on
  a specific language.
- The Python parser (Tree-sitter) extracts files, classes, functions, methods,
  imports, function/method calls, and decorators, with cross-file call and
  inheritance resolution.
- Language detection recognizes Python, JavaScript, TypeScript, Java, and C++
  file extensions, but only Python has a real parser wired up
  (`IMPLEMENTED_PARSERS` in `backend/app/core/languages.py`); other languages
  are the next milestones (§34 Phase 2 in `CLAUDE.md`).

### Knowledge graph (Neo4j)
- IR is loaded into Neo4j with `CONTAINS`, `IMPORTS`, `CALLS`, `INHERITS`,
  `USES` relationships, each carrying source file/line provenance.

### Architecture Reconstruction
- `backend/analysis/reconstruction/` groups the graph's files into
  architectural components by directory structure (up to two levels deep),
  entirely from evidence already in the graph — no LLM involved.
- Each component's role (`api` / `service` / `data_access` /
  `external_integration` / `model` / `test` / `other`) is inferred from the
  same deterministic signals impact analysis already uses: route decorators,
  class-naming conventions (`*Service`, `*Repository`, `*Client`, …), and
  import classification — reused directly from `analysis/impact/classifiers.py`.
- Every component carries a Confirmed/Inferred/Uncertain confidence label and
  the specific evidence that produced it (decorator counts, matched suffixes,
  matched directory names).
- Inter-component relationships are aggregated from resolved `CALLS` edges
  between symbols in different components (call count + average resolver
  confidence + example call sites); `IMPORTS` is intentionally excluded as too
  noisy to imply an architectural dependency on its own.
- `GET /api/repositories/{id}/architecture` returns the full structured model;
  the **Architecture** tab renders it with drill-down into each component's
  evidence and file list, and the **Evidence explorer** tab (below) remains
  available for the lower-level symbol graph.

### Interactive Evidence Explorer
- Interactive graph explorer (Cytoscape.js) with file-level and class-level
  granularity, node inspection, and truncation safeguards for large graphs.
- Click any two nodes to get an **evidence-based relationship explanation** —
  the graph finds the real connecting path (or proves there isn't one), and
  the LLM only narrates that path in plain English; it never guesses a
  relationship the graph doesn't support.

### Evidence-backed Q&A ("Ask the Archeologist")
- Hybrid retrieval: graph traversal + a vector index over embedded symbols.
- Every answer ships with cited evidence (symbol, file, line range) and
  related symbols with their relationship type and confidence.
- A deterministic confidence score/label (`Confirmed` / `Inferred` /
  `Uncertain`) is computed from evidence quality — never invented by the LLM.
- Strict prompt boundaries: repository content (code, comments, READMEs) is
  never treated as an instruction to the LLM (`backend/ai/prompts/qa_prompt.py`).

### Architecture analysis
Deterministic, threshold-based detectors over the graph — each finding is
fully auditable (no LLM judgment involved). Two granularities, both surfaced
in the same list per component and against symbol-level checks separately:

**Per-symbol:**
- **Circular dependencies** — strongly-connected components in the `CALLS` graph.
- **God classes** — classes with an excessive method count (severity-tiered thresholds).
- **Large functions** — functions/methods with an excessive line count.
- **Dead code candidates** — functions/methods with no recorded caller and no
  decorator, explicitly reported as a low-confidence heuristic (misses dynamic
  dispatch, reflection, and external entry points).

**Per-component** (`backend/analysis/smells/architecture_violations.py`, built
on the reconstructed `ArchitectureModel`):
- **Architecture boundary violations** — a lower-layer component (e.g.
  data-access) calling back into a higher layer (e.g. api/service), which
  breaks unidirectional layering.
- **Layer skips** — an api-role component calling a data-access/external
  component directly, bypassing a service layer that exists elsewhere in the
  repository.
- **Circular component dependencies** — two components that call each other,
  the component-level counterpart of a circular call dependency.
- **Excessive component coupling** — a component connected to an unusually
  high number of other components, a structural bottleneck.

Component-level findings explicitly disclose that roles are inferred
heuristically from directory/naming conventions, per CLAUDE.md §18's
"heuristic findings must disclose their limitations" rule.

Findings are surfaced in the UI ranked by severity (HIGH → MEDIUM → LOW) with
explanation, evidence, and affected symbols.

### Architecture Optimization
- `backend/analysis/optimization/` generates one proposal per structural
  violation found by Architecture Analysis — there is no free-standing
  "redesign this repository" step; every recommendation traces back to a
  specific finding.
- Each proposal states, per CLAUDE.md §38: the **problem** (observed
  violation), **evidence**, **proposed change** (explicitly labeled as a
  recommendation, never a fact), **expected benefit**, **potential risk**, a
  deterministic **risk level** (`LOW`/`MEDIUM`/`HIGH`/`CRITICAL`), and a
  Confirmed/Inferred/Uncertain confidence.
- Where possible, risk is grounded in a real `analyze_impact` run against the
  most-connected symbol in the affected component(s) — CLAUDE.md §26's
  "optimization should use existing impact analysis" — rather than only the
  violation's own severity.
- **Never modifies the repository.** This is a design recommendation surface
  only, per CLAUDE.md §19.
- `GET /api/repositories/{id}/optimization`; rendered in the **Optimization**
  tab.

### Execution Flow Reconstruction
- `backend/analysis/execution_flow/` detects API entry points (route-decorated
  functions/methods, reusing the same `is_api_endpoint` classifier as impact
  analysis) and reconstructs a bounded call tree from resolved `CALLS` edges —
  purely static, the repository is never executed.
- Each hop carries file/line evidence and resolver confidence; traversal stops
  at any symbol whose component (from Architecture Reconstruction) is
  `data_access` or `external_integration`, and is bounded in depth/branching
  so large repos don't produce an unreadable tree.
- A **PROPOSED** variant is derived by splicing a synthetic hop through the
  service-layer component wherever the flow crosses a `layer_skip` violation
  Architecture Optimization already found — every synthesized node is
  explicitly labeled `PROPOSED`, never presented as an observed call
  (CLAUDE.md §39).
- `GET /api/repositories/{id}/flows` (candidate entry points),
  `POST /api/repositories/{id}/flows/reconstruct`; rendered in the
  **Execution flow** tab with a current/proposed toggle.

### Historical Reconstruction
- `backend/analysis/history/` reads the repository's own Git commit history
  (via GitPython) and, for each architectural component, computes commit
  count, first/last-touched dates, top authors, and an **introduction
  commit** — real evidence answering "when was this component introduced?"
  (CLAUDE.md §27) without asking the LLM to guess.
- Repositories are cloned shallow (`depth=1`) for parsing speed, so this
  module best-effort widens the clone on demand (`git fetch --deepen`),
  bounded to a fixed number of extra commits — deliberately not changing the
  default ingestion clone depth for every repository just for this feature.
- When history is truncated (still shallow, or more commits exist than were
  analyzed), that limitation is disclosed in `detection_notes` rather than
  silently presenting a partial picture as complete.
- `GET /api/repositories/{id}/history`; rendered in the **History** tab.

### Change impact & risk analysis
- Symbol search/autocomplete (`/symbols`) plus repo-specific starting-point
  suggestions (`/symbols/suggestions`) — the most-connected real symbols in
  the loaded repository, not a generic placeholder example.
- For a chosen symbol: direct and indirect dependents, affected API endpoints,
  affected service-layer components, affected tests, and affected external
  dependencies (via heuristic classifiers over decorators, naming conventions,
  and import targets).
- Deterministic risk scoring (`LOW` / `MEDIUM` / `HIGH` / `CRITICAL`) from a
  fixed point rubric over measurable signals (dependent count, API/service
  exposure, test coverage, external dependencies, graph centrality) — every
  point is returned as a named, auditable `RiskSignal`.
- A generated explanation reasons over those signals (what they imply for a
  developer making the change) rather than just repeating the raw numbers.

## Prerequisites

- Python 3.12+ (a venv is not checked into the repo — create your own)
- Node.js 20+
- A [Neo4j Aura Free](https://console.neo4j.io) instance (no local Docker/Java required)
- A [Groq](https://console.groq.com) API key

## Setup

### Backend

```bash
cd backend
python -m venv .venv
./.venv/Scripts/activate      # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env          # then fill in GROQ_API_KEY, NEO4J_URI, NEO4J_PASSWORD
uvicorn app.main:app --reload --reload-exclude "workspace/**" --port 8000
```

> **Why `--reload-exclude`:** repository analysis clones repos into
> `backend/workspace/`. Without excluding it, `--reload` treats every file in
> a freshly-cloned repo as a source change and restarts the server mid- (or
> right after) analysis — which silently wipes the in-memory vector index
> even though the repository's status still shows "ready". If you hit
> "This repository has no vector index yet" on a repo that already finished
> analyzing, this is why — re-run without `--reload`, or with the flag above.

Run tests: `pytest -q`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the printed local URL (default `http://localhost:5173`). It talks to the
backend at `http://localhost:8000` by default (override with `VITE_API_URL`).

## Using it

1. Paste a GitHub URL (e.g. `https://github.com/pallets/flask`) and submit.
2. Watch the pipeline progress (clone → parse → graph → embed).
3. Once ready, explore eight tabs:
   - **Architecture** — the reconstructed architectural components, their
     inferred roles, confidence, evidence, and relationships to each other.
   - **Execution flow** — pick a detected API entry point and see its static
     call tree down to the database/external service, with a toggle to
     compare against the proposed (optimized) flow.
   - **Evidence explorer** — browse files/classes, click nodes for details,
     click two nodes to see how they're connected.
   - **Architecture analysis** — deterministic architectural smells (per-symbol
     and per-component), ranked by severity.
   - **Optimization** — a proposed fix for every violation found above:
     problem, proposed change, expected benefit, potential risk, and a
     deterministic risk level — recommendations only.
   - **Impact & risk** — pick a symbol and see its dependents, affected
     APIs/services/tests, external dependencies, and a scored risk level.
   - **History** — the most historically active components, their
     introduction commit, top authors, and a recent-commits feed, from the
     repository's own Git history.
   - **Ask the Archeologist** — ask a question (e.g. "How does authentication
     work?") and get an answer with cited evidence and a confidence label.

## API

```text
POST   /api/repositories                              # register a repo, kicks off background analysis
GET    /api/repositories                              # list repos
GET    /api/repositories/{id}                          # repo detail
GET    /api/repositories/{id}/status                    # poll analysis status

GET    /api/repositories/{id}/architecture               # reconstructed architecture (components + relationships)
GET    /api/repositories/{id}/optimization               # proposed fixes for each architecture-analysis finding

GET    /api/repositories/{id}/flows                     # detected API entry points
POST   /api/repositories/{id}/flows/reconstruct          # static execution-flow reconstruction from an entry point

GET    /api/repositories/{id}/history                   # Git-history-derived component activity + recent commits

GET    /api/repositories/{id}/graph                     # file- or class-level graph view
POST   /api/repositories/{id}/graph/relationship        # explain the connection between two nodes

POST   /api/repositories/{id}/ask                        # evidence-backed Q&A

GET    /api/repositories/{id}/smells                     # architectural smell report

GET    /api/repositories/{id}/symbols                    # symbol search
GET    /api/repositories/{id}/symbols/suggestions        # repo-specific impact-analysis starting points
POST   /api/repositories/{id}/impact                     # impact + risk analysis for a symbol

GET    /health                                           # liveness check
```

## Testing

- Unit tests cover the Python parser, IR resolution, URL validation, smell
  detection algorithms (cycle detection, thresholds), impact-analysis risk
  scoring, relationship evidence lookup, architecture-reconstruction
  grouping/role inference, component-level architecture violation detection
  (layer skips, boundary violations, circular dependencies, coupling),
  optimization-proposal assembly (goal mapping, risk/confidence derivation),
  execution-flow tree building (terminal detection, cycle guards, hop
  budget, proposed-flow splicing), and history aggregation (component commit
  grouping, introduction-commit selection, author ranking).
- Run with `pytest -q` from `backend/`.

## Security notes

- Only `https://github.com/<owner>/<repo>` URLs are accepted (blocks git's
  `ext::` transport, `file://`, path traversal, non-GitHub hosts).
- Cloned repos are size/file-count limited and never executed.
- Repository content is never treated as LLM instructions — see the prompt
  boundary in `backend/ai/prompts/qa_prompt.py`.
- API keys are read from environment variables only; `.env` is gitignored.
