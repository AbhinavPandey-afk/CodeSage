# CodeSage — Panel Review Presentation Prompt (Gamma AI, ≤15 slides)

> Paste everything below into Gamma AI's "paste in text" / prompt generation
> mode. It is written as a slide-by-slide build spec — Gamma will expand each
> section into a slide. Keep the numbers and evidence exactly as written;
> they came from real test runs during development, not estimates. Do not
> add features or claims beyond what's listed here.

---

**Gamma generation instructions:** Build a 15-slide deck for a panel review
of "CodeSage," an AI software architecture intelligence platform. Tone:
technical, credible, evidence-driven — not a marketing pitch. Dark,
developer-tool visual style. Use tables/stat callouts for numbers. Each
`##` heading below is one slide.

---

## Slide 1 — Title

- Title: **CodeSage — AI Software Architecture Intelligence Platform**
- Subtitle: *Panel Review — Phase I Complete, Phase II In Progress*
- Positioning line: "Not ChatGPT for GitHub — a deterministic knowledge
  graph is the source of truth; the LLM only explains what the graph
  already proved."

---

## Slide 2 — The Problem & Vision

- Developers lose enormous time reverse-engineering unfamiliar codebases:
  what does this do, why was it built this way, what breaks if I touch it.
- Existing "chat with your code" tools do naive RAG: dump code chunks into
  an LLM and hope. No structural guarantees, no evidence, invented
  confidence numbers.
- Pull quote: **"The graph understands the codebase. The LLM explains and
  reasons over that understanding."**
- CodeSage's answer: build a real knowledge graph from the code first
  (Tree-sitter → Neo4j), then let the LLM reason only over graph-verified
  evidence.

---

## Slide 3 — System Architecture

Pipeline (show as a diagram):
```
GitHub URL → Validate & sandbox-clone → Tree-sitter parse → Normalized IR
   → Neo4j knowledge graph (structural truth)
   → TF-IDF/FAISS vector index (semantic search)
   → Hybrid retrieval + evidence fusion
   → LLM (via swappable LLMProvider) → Evidence-backed answer
```
Two guarantees to call out:
1. The graph is the only source of structural facts (calls, imports,
   inheritance) — the LLM never invents relationships.
2. The LLM sits behind an `LLMProvider` abstraction — swapping providers
   later touches one file, not the whole app.

---

## Slide 4 — Technology Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI, Python 3.12 | async-ready, typed, fast to iterate |
| Parsing | Tree-sitter + custom Python parser | language-agnostic IR, extensible |
| Graph DB | Neo4j Aura (cloud, free tier) | structural source of truth, no Docker needed |
| Vector search | TF-IDF + FAISS (scikit-learn) | semantic retrieval, swappable interface |
| LLM | Groq (`openai/gpt-oss-120b`) | fast inference, behind `LLMProvider` abstraction |
| Frontend | React + TypeScript + Vite | typed, fast dev loop |
| Graph visualization | Cytoscape.js | interactive, click-to-inspect |
| Testing | pytest | 26 passing unit tests |

Note: CLAUDE.md's spec names "Grok" (xAI); this build uses **Groq**
instead per explicit product decision — interchangeable because of the
`LLMProvider` abstraction.

---

## Slide 5 — Roadmap & Current Status

- 4-phase roadmap (`docs/ROADMAP.md`): Foundation & MVP → Structural
  Intelligence → Temporal/Conversational → Production Hardening.
- ✅ **Phase I (M0–M4) — Foundation & MVP: 100% complete** (ingestion,
  Python parsing, knowledge graph, evidence-backed Q&A)
- ✅ **M7 — Impact analysis engine: complete** (pulled forward from Phase II)
- ✅ **M8 — Architectural smell detection: complete** (pulled forward)
- ⏳ Remaining Phase II: M5 (language expansion), M6 (execution flow), M9
  (health dashboard)
- All code committed/pushed to GitHub with descriptive history; 26
  automated tests passing; every feature verified live against real repos.

---

## Slide 6 — Feature: Secure Repository Ingestion

- `GitHubRepositoryService` validates URLs against a strict pattern
  (`https://github.com/<owner>/<repo>` only).
- Blocks real attack classes, **tested and verified live**:
  - `ext::` git transport (arbitrary command execution vector) — rejected
  - `file://` / path traversal (`owner/../../etc`) — rejected
  - non-GitHub hosts — rejected
- Sandboxed shallow clone (`depth=1`) into an isolated, UUID-named
  workspace — never a user-controlled path.
- Size/file-count limits enforced post-clone; oversized repos cleaned up
  automatically. Automatic language detection by file extension.

---

## Slide 7 — Feature: Multi-Language Parsing Foundation

- Tree-sitter-based Python parser extracts: files, classes, functions,
  methods, imports, function calls, decorators, inheritance, docstrings.
- Everything normalizes into a common **Intermediate Representation**
  (`Symbol` + `Relationship` models) — the same IR any future language
  parser (JS/TS/Java/C++) must produce.
- A cross-file relationship resolver links calls/inheritance across the
  whole repo, assigning a confidence score to every resolution (exact
  match, name-based, ambiguous, or external/unresolved).
- **Real numbers (Flask repo, live test):** 236 files → **2,651 symbols**,
  **3,707 relationships** extracted in **~8 seconds**.

---

## Slide 8 — Feature: Neo4j Knowledge Graph

- Schema: `Symbol` nodes with type-specific labels (`File`, `Class`,
  `Function`, `Method`, `Import`) plus `CONTAINS`, `IMPORTS`, `CALLS`,
  `INHERITS` relationships.
- Every relationship carries **confidence** and **provenance** (source
  file + line) — never an unverifiable claim.
- Hosted on **Neo4j Aura Free** (cloud, zero local infrastructure):
  200K nodes / 400K relationships capacity vs. ~2,650 nodes for a real
  mid-size repo — headroom for dozens of repos simultaneously.

---

## Slide 9 — Feature: Evidence-Backed Q&A

- Hybrid retrieval: graph traversal + TF-IDF/FAISS vector search →
  evidence fusion → LLM answer, always grounded in cited evidence.
- **Deterministic, non-LLM confidence scoring** — labeled Confirmed /
  Inferred / Uncertain.
- Strict prompt boundary: repository content (code, comments, READMEs)
  is architecturally prevented from being treated as system instructions
  — a defense against prompt injection from untrusted repo content.
- **Real example (live, Flask repo):**
  > Q: *"How does Flask session and cookie handling work?"*
  > A: cites `SessionInterface` and `SecureCookieSessionInterface` in
  > `src/flask/sessions.py:233-247`, explicitly states *"No explicit
  > evidence was found for how cookies are dispatched in requests"*
  > rather than guessing. Confidence: **Inferred (0.54)**
- Verified with 5 different Groq models/questions across two repos with
  zero fabrication observed.

---

## Slide 10 — Feature: Interactive Knowledge Graph Explorer

- Built with Cytoscape.js; two granularities: **Files** (default, one
  node per file, edges only for real cross-file calls) and **Files +
  classes** (drill-down with containment/inheritance edges).
- Click any node → inspect qualified name, file:line, connection count.
- **Design iteration story:** first version rendered every symbol at once
  (~150 cluttered, unreadable nodes). Redesigned after direct feedback to
  aggregate cross-file relationships and hide zero-degree nodes — the
  Click repo view went from ~150 tangled nodes to **21 nodes / 39 edges**,
  correctly surfacing `core.py`, `_compat.py`, `termui.py` as the real
  structural hubs.

---

## Slide 11 — Feature: Architectural Design-Issue Detection

- Four deterministic smell detectors with fixed, stated thresholds:
  - **Circular dependencies** — Kosaraju's SCC algorithm over the CALLS graph
  - **God classes** — method-count thresholds (LOW ≥15, MEDIUM ≥25, HIGH ≥40)
  - **Large functions** — line-count thresholds (LOW ≥60, MEDIUM ≥100, HIGH ≥150)
  - **Dead code candidates** — no incoming calls, no decorators, not
    dunder/test — explicitly labeled the weakest-confidence heuristic
- Every finding ships with severity, evidence, and explanation.
- UI shows only **HIGH + up to 5 MEDIUM** findings, with a disclosed
  count of what's hidden.
- **Real example (Flask, live):** 42 total findings, including two genuine
  circular call dependencies and a 35-method `Flask`/`App` god-class finding.

---

## Slide 12 — Feature: Impact Analysis Engine

- Given any symbol, computes: direct + indirect dependents (graph
  traversal, up to 8 hops), affected API endpoints (route-decorator
  matching), affected service-layer components (naming-convention
  heuristic), affected tests, and external/database dependencies (real
  import analysis vs. Python's stdlib list).
- **Deterministic risk scoring** — a fixed point rubric producing
  LOW/MEDIUM/HIGH/CRITICAL, every point shown as a named, auditable signal.
- Explanation text reasons about the signals rather than repeating
  numbers — an explicit design iteration after review feedback. The
  search box surfaces the repo's actual most-connected symbols as
  clickable starting points.
- **Real example (Flask tutorial app, live):** `get_post` helper →
  **71 dependents** (2 direct, 69 indirect), **21 real `@bp.route`
  endpoints** affected, **35 covering tests** found → **HIGH risk
  (score 7)**, with a full explanation of why.

---

## Slide 13 — Engineering Rigor: Testing & Real Bugs Fixed

- **26 passing unit tests**: parser correctness, cross-file resolver,
  URL validation security, smell-detection cycle detection,
  impact-analysis risk rubric. Every feature additionally verified live
  against real repos (Flask, Click), not synthetic fixtures.
- Real bugs found and fixed during development (pick 2–3 to tell as
  before → diagnosis → fix):
  1. **Silent graph query bug:** `symbol_type` was used as a Neo4j node
     *label* but never written as a node *property* — queries filtering
     on it silently returned zero results. Found via two smell detectors
     always returning empty; fixed and re-verified against live data.
  2. **The `--reload` vector-index bug:** `uvicorn --reload` watches the
     backend directory by default, which includes cloned repos in
     `backend/workspace/`. This silently restarted the server mid-analysis,
     wiping the in-memory vector index while status still said "ready."
     Diagnosed by comparing process start-times against failure reports;
     fixed with `--reload-exclude`.
  3. **CORS port fragility:** hardcoded to `localhost:5173`, broke when a
     second dev server bumped to `5174`. Fixed with a regex-based
     localhost-port match.

---

## Slide 14 — Security Principles & What's Next

**Security principles applied (from CLAUDE.md), shown as a checklist:**
- Confidence scores always computed deterministically — never an LLM assertion.
- Repository content never treated as privileged LLM instructions
  (prompt-injection defense).
- Caught a real secret-leak risk live during development: a Groq API key
  briefly pasted into the tracked `.env.example` instead of the gitignored
  `.env` — caught before any commit, fixed.
- LLM provider fully swappable behind `LLMProvider` — no logic coupled to Groq.
- Every heuristic discloses its own detection method and limitations in the UI.

**What's next, in priority order:**
- **M6** — Execution flow reconstruction (entry point → controller →
  service → DB, per-hop confidence)
- **M9** — Repository health dashboard (roll up smell + graph signals)
- **M5** — Language expansion: JavaScript → TypeScript → Java → C++, all
  normalizing into the existing IR
- Later (Phase III): Git evolution/"why" reasoning, Talk-to-the-codebase,
  AI onboarding mode

---

## Slide 15 — Live Demo & Closing

**Demo script (presenter notes):**
1. Paste `https://github.com/pallets/flask` → show live pipeline progress
2. **Knowledge graph tab** — file-level dependency map, click a node
3. **Ask tab** — *"How does Flask session and cookie handling work?"* live,
   with cited evidence + confidence
4. **Design issues tab** — a real circular-dependency or god-class finding
5. **Impact analysis tab** — a dynamic "Try:" suggestion → risk breakdown

**Closing:**
- Restate the thesis: *"The graph understands the codebase. The LLM
  explains and reasons over that understanding."*
- Thank the panel, open for questions.
