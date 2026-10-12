# PROJECT EVIDENCE REPORT — CodeBase Archeologist

Audit performed 2026-10-11 on `main` @ `9040747` plus **76 uncommitted working-tree entries** (the audit measures the working tree; the audit itself added only the `project_audit_2026_10_11/` directory).
Companion files: `IMPLEMENTATION_MATRIX.csv`, `TEST_RESULTS.md`, `METRICS_AND_RESULTS.md`, `ARCHITECTURE_AND_DATA_FLOW.md`, `REPORT_WRITER_HANDOFF.md`, `EVIDENCE_INDEX.md`; raw outputs in `raw/`; re-runnable scripts in `scripts/`.

Evidence labels used throughout: **[V]** verified by execution in this audit · **[S]** from source reading · **[H]** historical claim, not re-measured · **[R]** re-measured and compared to a historical claim · **[U]** unmeasured / no evidence.

---

## 1. Executive summary

CodeBase Archeologist (code name *CodeSage* in the source tree) is a working full-stack prototype: a FastAPI backend that clones a public GitHub repository, parses it with Tree-sitter into a common intermediate representation (IR), resolves cross-file relationships, stores the result as a graph in Neo4j, and then computes — on demand and without an LLM — a reconstructed architecture, architecture-level findings, optimization proposals, static execution flows, change-impact/risk scores and Git-based component history. An LLM (Groq) is used only to answer questions over retrieved evidence and to narrate a verified graph path between two symbols. A React/TypeScript frontend with nine tabs and a Cytoscape.js graph explorer consumes these APIs.

What was verified **[V]**:
* **172/172** backend unit tests pass (0 failed, 0 skipped); frontend type-check and production build succeed; lint has 0 errors and 3 warnings.
* The real FastAPI routes work against the existing Flask graph in Neo4j (HTTP 200 for architecture, smells, optimization, flows, graph views, symbols, impact). Flask (236 files; 83 Python; 2,654 symbols; 3,713 resolved relationships) was re-parsed offline and the numbers match the stored registry exactly.
* Two earlier validation claims were **reproduced**: the Architecture Analysis result on Flask (**47 findings; severity 1/17/29; confidence tiers 3/21/23**) and the execution-flow fix (**`blog.index` 3 → 16 nodes**, comparing the committed code with the working tree on identical data).

What the audit also found, and the report must not hide:
1. **Resolver precision is the weakest link.** Calls are bound by name only; a unique short name is accepted at confidence 0.75. Generic names create false edges: 12/12 sampled incoming "calls" to `examples.tutorial.flaskr.blog.update` are ordinary `dict.update(...)` calls. Consequently **8 of the 15 non-root hops in the 16-node `blog.index` trace are spurious**, and the impact result for `blog.update` (CRITICAL, 20 "affected APIs") is inflated. Only 32 % of Flask CALLS resolve at all.
2. The 3 → 16 improvement is real *as a change in traversal behaviour* (roles no longer terminate traversal) but is **not** evidence of 13 additional correct hops.
3. The execution-flow fix, five new test files and ~50 other changes are **uncommitted**.
4. Tests are unit-level only: no Neo4j/API/LLM integration tests, no frontend tests, no golden repositories, no ground-truth evaluation of any analysis output.
5. Historical Reconstruction is limited to per-component commit statistics; Ask-the-Archeologist and `/history` were not exercised live; the UI was not driven in a browser.
6. There is no research artefact in the repository (no evaluation scripts, baselines, bibliography, screenshots).

## 2. Project problem statement

*Source: `CLAUDE.md` §1-§3, `README.md` intro — [S]. The repository does not contain a formal problem statement or research questions; the following restates what the documents say.*

Developers who join an unfamiliar repository lack a reliable, inspectable picture of how it is structured and how an operation flows through it. General-purpose "chat with your code" tools answer from an LLM's reading of retrieved text and may state structure that the code does not contain. The project's stated position is that **structural facts must come from deterministic repository analysis (parse → graph), with every claim carrying file/line evidence and a rule-derived confidence, while the LLM only explains that evidence**. Product pipeline: *Excavate → Reconstruct → Analyze → Improve → Explain*.

## 3. Objectives and scope

Stated objectives (`CLAUDE.md` §4, §34) and their implementation status [S/V]:

| Objective | Status |
|---|---|
| Ingest and parse public GitHub repositories (5 languages) | Implemented; verified in depth for Python only |
| Knowledge graph with provenance and confidence | Implemented and verified on Flask |
| Architecture reconstruction with evidence/confidence | Implemented; heuristic; not validated against ground truth |
| Architecture analysis (smells + violations) | Implemented; determinism reproduced |
| Optimization recommendations (never modifying the repo) | Implemented as templated proposals |
| Execution-flow reconstruction (current + proposed) | Implemented; proposed variant never triggered on Flask |
| Change impact & deterministic risk | Implemented |
| Historical reconstruction | **Partial** (commit statistics only) |
| Evidence-based Q&A / relationship narration | Implemented; not run in audit |
| Interactive evidence explorer | Implemented; API verified, UI not browser-verified |

Explicit scope limits from `CLAUDE.md` §5, §7, §47: five languages only; no code execution; no automatic repository modification; removed standalone features (onboarding, health dashboard, etc.). Not in scope or not done: incremental analysis (§41), ADRs, golden-repository fixtures (§33).

## 4. System architecture

Summarised here; full diagrams and tables in `ARCHITECTURE_AND_DATA_FLOW.md`.

* **Layers** [S]: `ingestion/` → `parsing/` (parsers + IR + resolver) → `graph/` (Neo4j loader, schema, read queries) → `analysis/` (reconstruction, smells, optimization, impact, execution_flow, history) → `ai/` (prompts, LLM provider, retrieval) → `app/` (FastAPI routes, schemas, services) → `frontend/`.
* **Process model** [S]: one FastAPI process; ingestion runs via `BackgroundTasks`; status polled by the frontend; analysis endpoints compute on request.
* **Persistence** [S]: Neo4j Aura (graph), `backend/workspace/registry.json` (repository records), `backend/workspace/<id>/` (clones). The TF-IDF/FAISS vector index is in process memory only.
* **Layer separation** [S]: analysis modules contain no LLM imports (grep-verified); routes call engines but contain no graph algorithms; only `ai/llm/groq_provider.py` imports the Groq SDK.

## 5. Verified technology stack

| Technology | Version found | Why used here | Where |
|---|---|---|---|
| Python | 3.12.10 (venv); system 3.14.6 lacks dependencies | backend language | `backend/.venv` |
| FastAPI / Uvicorn / Pydantic (+ settings) | 0.141.1 / 0.52.1 / 2.13.4 (2.15.0) | REST API, request/response schemas, env config | `app/main.py`, `app/schemas/*`, `app/core/config.py` |
| Tree-sitter + 5 grammars | 0.26.0; py 0.25.0, js 0.25.0, ts 0.23.2, java 0.23.5, cpp 0.23.4 | error-tolerant syntax trees for structure extraction | `parsing/tree_sitter/loader.py`, `parsing/parsers/*` |
| Neo4j driver / Aura | 6.2.0 | persistent property graph; Cypher traversal | `graph/*`, all `analysis/*` |
| GitPython | 3.1.58 | shallow clone, commit history | `ingestion/cloning/clone.py`, `analysis/history/engine.py` |
| scikit-learn TF-IDF + faiss-cpu | 1.9.0 / 1.15.0 | offline lexical retrieval over symbol text | `embeddings/vector_store/tfidf_store.py` |
| NumPy | 2.5.2 | FAISS inputs | same |
| Groq SDK (model via `GROQ_MODEL`) | 1.6.0 | LLM explanation behind `LLMProvider` | `ai/llm/*` |
| structlog | 26.1.0 | structured logging | `app/core/logging.py` |
| pytest (+asyncio, httpx) | 9.1.1 / 1.4.0 / 0.28.1 | tests (httpx only used implicitly by TestClient in the audit) | `backend/tests` |
| React / TypeScript / Vite | 19.2.8 / 6.0.3 / 8.2.1 | SPA | `frontend/` |
| Tailwind CSS 4, shadcn/radix-ui, motion, lucide | 4.3.3 / n.a. | UI styling and primitives | `frontend/src/components` |
| Cytoscape.js | 3.34.0 | interactive graph explorer | `frontend/src/components/GraphView.tsx`, `graph/*` |
| oxlint | 1.75 | linting | `frontend/.oxlintrc.json` |

Environment variable **names** (values redacted; `.env` not read into this report): `GROQ_API_KEY`, `GROQ_MODEL`, `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `APP_ENV`, `LOG_LEVEL`, `WORKSPACE_DIR`, `MAX_REPO_SIZE_MB`, `MAX_REPO_FILES`; frontend `VITE_API_URL`.

Documentation/implementation discrepancies about technologies (see `ARCHITECTURE_AND_DATA_FLOW.md` §7): FAISS is used with TF-IDF vectors, not neural embeddings; no relational DB; `ROADMAP.md` is outdated; `CLAUDE.md` names Grok while Groq is implemented (the code comments say so explicitly).

## 6. Implementation status by module

Full table with files, tests, evidence and limitations: **`IMPLEMENTATION_MATRIX.csv`** (27 rows). Summary:

| Status class | Modules |
|---|---|
| Implemented and validated on a real repository (Flask) | ingestion/validation/clone, Python parser, IR, graph construction, architecture reconstruction (run, not correctness-validated), architecture analysis, optimization, impact, execution flow, graph views |
| Implemented, unit-tested, not validated on real data | JavaScript (1 ingest), Java (1 ingest), TypeScript, C++ parsers |
| Implemented, not exercised in this audit | Ask the Archeologist, LLM narration of relationships, Repository Overview and all UI behaviour |
| Partially implemented | Historical Reconstruction; error handling; security (API side) |
| Not implemented | incremental analysis; architecture snapshots/diffs; golden fixtures; ADRs; authentication |

## 7. Algorithms and methods

(Code references in §6 of `ARCHITECTURE_AND_DATA_FLOW.md`; formulae below are quoted from source [S].)

**7.1 Parsing → IR.** Tree-sitter parses each file; a language class walks the tree and emits `Symbol`s (file/class/function/method/import) and `Relationship`s (CONTAINS, IMPORTS, CALLS, INHERITS) with file/line. Duplicate symbol ids are disambiguated (`dedupe_symbol_id`) because ids become Neo4j primary keys.

**7.2 Cross-file resolution** (`parsing/ir/resolver.py`): exact qualified name → 0.95; unique short-name match → 0.75; several candidates → unresolved at 0.3; no candidate → unresolved ≤ 0.35. No scope, import-binding or type information is used. Flask effect: 1,072/3,350 calls resolved, 871 ambiguous [V].

**7.3 Architecture reconstruction** (`analysis/reconstruction`): components = directories to depth 2 (top 40 by symbol count); first-match role cascade (test → api → data_access → external_integration → service → model → other); role confidence is an additive score capped at 0.95–0.98; label Confirmed ≥ 0.75, Inferred ≥ 0.4, else Uncertain; inter-component relationship = aggregated resolved CALLS across component boundaries with mean resolver confidence. Imports deliberately excluded.

**7.4 Architecture analysis** (`analysis/smells`): strongly-connected components (Kosaraju) over CALLS for circular dependencies; god class by method count (15/25/40 → LOW/MEDIUM/HIGH); large function by line count (60/100/150); dead-code candidates (no caller and no decorator; ≤ 20; low confidence). Component level: layer order api(0) < service(1) < data_access/external(2); upward call = boundary violation (HIGH if two layers, else MEDIUM); api→data/external while a service component exists = layer skip (MEDIUM); mutual calls = circular component dependency (MEDIUM); degree ≥ 6/≥ 10 = coupling (MEDIUM/HIGH). **Severity** is the size of the observed condition; **confidence** is a separate 0–1 blend of a base value, the underlying resolver confidence and context discounts/flags (e.g. `SUPPORTING_STRUCTURE` −0.25, `EXPECTED_TEST_DEPENDENCY` −0.35, `FRAMEWORK_HUB` −0.2), capped at 0.85 for layering findings. Re-measurement shows they are independent (e.g. 3 MEDIUM findings have Low confidence; 9 LOW findings have Medium confidence) [V].

**7.5 Execution flow** (`analysis/execution_flow`): entry points = functions/methods whose decorators match the route regex; DFS over resolved CALLS, highest-confidence 3 callees per hop, depth ≤ 5, ≤ 150 nodes, cycle-safe. **`terminal_kind`** (database / external_service / none) is a descriptive badge derived from the component role; **`terminal_reason`** records why a branch ended: NO_RESOLVED_CALLEES, STANDARD_LIBRARY, EXTERNAL_DEPENDENCY, UNRESOLVED, DEPTH_LIMIT, BRANCH_LIMIT. A leaf is classed STANDARD_LIBRARY/EXTERNAL_DEPENDENCY only if the unresolved call's prefix (e.g. `sqlite3` in `sqlite3.connect`) is actually imported by that file. A PROPOSED flow inserts a synthetic service hop at each caller→callee component pair flagged as `layer_skip`, labelled `PROPOSED`, confidence 0.5, no source location.

**7.6 Impact & risk** (`analysis/impact`): reverse traversal over CALLS|INHERITS to depth 8 → direct/indirect dependents; classifiers for APIs (decorator regex), services (name suffix), tests ("test" in path or `test_` prefix), external imports; points: total dependents 0–4, API +2, service +1, no covering tests +2, external +1, degree ≥ 15 +1; LOW < 3 ≤ MEDIUM < 5 ≤ HIGH < 8 ≤ CRITICAL.

**7.7 Optimization** (`analysis/optimization`): one proposal per component-level violation with text templated by violation kind (enforce layering / reduce circularity / reduce coupling); risk from a real `analyze_impact` on the affected components' most-connected symbol; confidence 0.4–0.95 from severity (+0.1 when impact data exists).

**7.8 Retrieval & explanation** (`ai/retrieval`): TF-IDF (4,096 features, English stop-words) + FAISS exact inner product over symbol name + decorators + docstring; top 8 hits, 6 enriched with ≤ 13 neighbouring edges; confidence = mean of top-3 cosine scores + 0.2 (or 0.05) graph bonus; Confirmed ≥ 0.55, Inferred ≥ 0.30. Prompt: system rules, `<question>`, `<evidence>`; evidence text contains symbol names/locations/relations, not source bodies.

**7.9 Relationship investigation** (`graph/queries/relationship.py`): direct edge check (any of four types, either direction) → else Cypher `shortestPath` over CALLS|INHERITS|CONTAINS up to 6 hops → else "not connected" with no LLM call.

**7.10 History** (`analysis/history`): per commit (≤ 500), changed paths ∩ current component file lists; per component count, first/last date, top 3 authors, "introduction commit" = oldest commit in the analysed window (explicitly window-bounded).

## 8. Database and graph design

See `ARCHITECTURE_AND_DATA_FLOW.md` §4. Key facts [V/S]: single label `Symbol` plus a type label; `uid = "{repo_id}:{symbol.id}"` is the unique key (so each ingest is an independent subgraph; 50 completed Flask ingests means 50 Flask subgraphs may exist in Aura — not checked); four stored relationship types with `source_file`, `source_line`, `confidence`; unresolved call names kept as a property. Flask counts: 2,647 nodes; CONTAINS 1,622; IMPORTS 942; CALLS 1,071; INHERITS 70. Seven IR symbols (all imports) and one CALLS edge do not appear in Neo4j (MERGE semantics) [V; cause not isolated].

## 9. API and frontend architecture

REST endpoints (17, all under `/api/repositories` except `/health`) [S]:

| Method & path | Purpose | Verified live |
|---|---|---|
| `POST /` (202) · `GET /` · `GET /{id}` · `GET /{id}/status` | register/list/poll repositories | GET `{id}` ✔ |
| `GET /{id}/graph?granularity=files\|classes&limit=` | explorer data | ✔ |
| `POST /{id}/graph/relationship` | path + explanation | graph half ✔; LLM half ✘ |
| `GET /{id}/architecture` | reconstruction model | ✔ |
| `GET /{id}/smells` | analysis findings | ✔ |
| `GET /{id}/optimization` | proposals | ✔ |
| `GET /{id}/flows` · `POST /{id}/flows/reconstruct` | entry points; flow | ✔ ✔ |
| `GET /{id}/symbols` · `GET /{id}/symbols/suggestions` · `POST /{id}/impact` | search, starting points, impact | ✔ ✔ ✔ |
| `GET /{id}/history` | commit statistics | ✘ (writes to clone) |
| `POST /{id}/ask` | Q&A | ✘ (Groq; in-memory index) |
| `GET /health` | liveness | ✔ |

Frontend [S]: single-page app (`App.tsx`) with a polling hook, `AppShell` + sidebar navigation, nine tabs, `InvestigationProvider` for cross-tab "investigate this entity" navigation, pure view-model modules in `src/lib` (`architectureModel`, `analysisModel`, `flowModel`, `semanticFlow`, `evidenceExplorer`, `terminalReasons`), Cytoscape-based `GraphView`, and flow views (Understand / component flow / symbol trace — files `flow/UnderstandFlow.tsx`, `ComponentFlow.tsx`, `TraceCanvas.tsx`). **None of these UI behaviours was run in a browser during this audit.** Note: `CLAUDE.md` §36 forbids analysis logic in the frontend; the `src/lib/*Model.ts` files contain view-model derivations (grouping, tiering) — e.g. finding confidence tiers are defined only in `analysisModel.ts` — which is a boundary question worth raising.

## 10. Security and reliability considerations

Controls present [S]: strict GitHub URL regex (tests cover `ext::`, `file://`, traversal, other hosts); clone with `GIT_TERMINAL_PROMPT=0`, low-speed abort, depth 1; file-count and size limits; ignored directories; repository code is parsed as bytes (no execution found in files read); LLM prompt boundary and "evidence is data" rules; `.env` git-ignored and never committed [V]; Groq key required by `GroqProvider`; no logging of the key was seen in the files read.

Gaps [S]: no authentication/authorisation or rate limiting on any endpoint; CORS regex only for localhost development (`allow_origin_regex=None` otherwise, i.e. no cross-origin access in production mode); prompt-injection protection is prompt-wording only, with no adversarial test; `POST /ask` does not check that the repository status is `ready`; vector index lost on restart ("This repository has no vector index yet" 409); transient Aura connection failures made 5 of 55 Flask ingests fail with no retry; clone directories never cleaned; JSON registry is not concurrency-safe across processes; Neo4j credentials are required for every analysis route.

## 11. Test methodology and actual test results

Full detail: **`TEST_RESULTS.md`**. Summary [V]: 172 passed / 0 failed / 0 skipped (10.01 s, Python 3.12.10 venv); `tsc` exit 0; `oxlint` exit 0 with 3 warnings (one `useEffect`-without-deps in `RepositoryOverview.tsx:27`); `vite build` success, 980.83 kB JS. Tests are pure-function unit tests; they cannot detect Cypher errors or resolver false positives (as the Flask `blog.update` case shows). A first attempt with the system Python failed at collection (missing dependencies) and is not a project defect.

## 12. Flask case study

Repository `pallets/flask`, commit `d73fa1cd`, ingested 50 times successfully between 2026-08-18 and 2026-09-16 (registry: 49 runs at commit `d73fa1cd`, 1 at `d318b683`), every run recording 236 files / 2,654 symbols / 3,713 relationships [V].

1. **Ingestion & parsing [V]** — 236 files, 83 Python, 2,654 symbols (83 files, 949 imports, 1,060 functions, 160 classes, 402 methods), 0 parse errors, offline parse 2.14 s + resolve 0.02 s; end-to-end median 8.4 s.
2. **Relationships [V]** — CALLS 3,350 raw → 1,072 resolved (239 at 0.95; 833 at 0.75; 871 ambiguous); INHERITS 117 → 70; plus 1,622 CONTAINS and 949 IMPORTS.
3. **Architecture [V]** — 8 components / 12 relationships. Roles: `tests`, `tests/type_check`, `tests/test_apps` = test; `examples/tutorial`, `examples/celery`, `examples/javascript` = api; `src/flask`, `docs` = external_integration. *Interpretation caution:* Flask is a framework library, not a layered application; `src/flask` is labelled external_integration only because the heuristic counts any third-party import as that role's evidence. No service/data_access component exists, so layered-violation logic has little to say (and `layer_skip` = 0).
4. **Analysis [R]** — 47 findings (dead code 20, large function 16, god class 4, circular component dependency 3, circular dependency 2, boundary violation 1, coupling 1); severity 1/17/29; confidence tiers 3/21/23. 25 findings carry `SUPPORTING_STRUCTURE` (they sit in tests/docs/examples).
5. **Optimization [V]** — 5 proposals (1 CRITICAL, 4 HIGH).
6. **Execution flow [V/R]** — 20 entry points offered; flow sizes 1…18 nodes (11 are single-node); fix verified: `blog.index` 3 → 16, `blog.create` 4 → 18, `auth.login` 4 → 18, `blog.delete` 6 → 6. No flow has a PROPOSED variant. **Caveat:** in the `blog.index` tree two nodes are the unrelated `blog.update`, each with three children — 8 of 15 callees are artefacts of the name-based resolver (see §1, point 1; `raw/flow_tree_blog_index.txt`). The genuine part of the tree is `blog.index → get_db (STANDARD_LIBRARY end)`, `blog.index → render_template → _render → Flask.update_template_context → Flask.ensure_sync → async_to_sync`, and `render_template → _get_current_object`. (Whether each of those individual edges is correct was judged by reading the printed call-site lines, not by exhaustive review.)
7. **Impact [V]** — `Flask.test_client` HIGH (6), `Flask.test_request_context` HIGH (7), `blog.update` CRITICAL (8, inflated by false edges).
8. **Evidence Explorer [V via API]** — file view 23 nodes/53 edges; class view 85 nodes/86 edges. Relationship check: `test_client`↔`test_request_context` = INDIRECT via two CONTAINS hops (same class), which shows only co-membership.
9. **UI [U]** — not exercised.

Other repositories in the registry: requests (130 files; 1,539 symbols; 2,496 relationships), jinja (107; 2,705; 5,498), black (482; 4,985; 6,765), hackathon-starter JS (171; 386; 464), spring-petclinic Java (132; 753; 993). django was rejected (> 5,000 files). Only counts exist; no analysis output was inspected for these.

## 13. Evaluation metrics and results

All verified numbers and their definitions are in **`METRICS_AND_RESULTS.md`**, separated into CURRENT / HISTORICAL / ESTIMATE / UNMEASURED. Important definitional notes:
* "Confidence" for findings is the engine's own 0–1 value; the High/Medium/Low *tiers* (0.7/0.4) exist only in the frontend. State the thresholds when quoting 3/21/23.
* "Nodes in a trace" = tree nodes including the entry function.
* "Resolved CALLS %" = resolved edges ÷ raw call sites; unresolved calls are mostly legitimate external/dynamic targets, so this is not an error rate.
* **There is no accuracy, precision, recall, user-study or baseline metric in the project.** Any such claim would have to come from new experiments (§16).

## 14. Comparison with existing solutions

No quantitative comparison with Sourcegraph, GitHub Copilot, CodeQL, Understand, Structure101, or any other tool exists in the repository **[U]**. Nothing in this audit supports a claim that CodeBase Archeologist is better than any of them. What *can* be said from the design (not from measurements):

| Dimension | CodeBase Archeologist (as built) | What a comparison would need |
|---|---|---|
| Source of structural claims | Tree-sitter + graph; LLM narrates | Same-task outputs from the other tool |
| Provenance | file/line + resolver confidence on each edge | Measure whether competitors expose equivalents |
| Resolution quality | name-based; demonstrated false positives | Ground-truth call graph (e.g. from a type-aware analyser) |
| Scope | 5 languages, public GitHub repos | – |

An evaluation plan is given in §16 and in `REPORT_WRITER_HANDOFF.md` §11. Literature and related work must be supplied by the student; none is stored in the repo.

## 15. Limitations and threats to validity

* **Construct validity:** "architecture" = directory groups + name/import heuristics; roles are conventions of web back-ends and fit Flask poorly; severity/confidence thresholds are fixed constants without empirical calibration.
* **Internal validity:** resolver false positives propagate into flows, impact, risk, optimization risk and relationship paths (§1.1). Dead-code and large-function findings are heuristics (flagged in the output).
* **External validity:** deep validation on a single Python library; one JS and one Java ingest with outputs uninspected; no TS/C++ real repositories; repositories over 5,000 files unsupported.
* **Reproducibility:** counts were deterministic across 50 Flask runs; end-to-end timing depends on network/Aura; several results depend on uncommitted code.
* **Instrumentation:** metrics were collected by audit scripts calling the application's own routes/engines; they were not independently re-implemented.
* **Documentation drift:** README still describes the older flow-termination rule; `ROADMAP.md` is obsolete; the older presentation prompt has outdated numbers.

## 16. Future work (proposed, not done)

1. Import-aware, scope-aware call resolution (bind via the file's own imports/`self`/class membership; stop treating a unique short name as sufficient for builtin-method names such as `update`, `get`, `add`); report precision/recall on a hand-labelled sample.
2. Golden repositories with expected components, flows and findings (`CLAUDE.md` §33) and integration tests against a local Neo4j.
3. Controlled comparison study (task set, baselines, metrics, protocol) against ≥ 1 existing tool; user study with a supervisor-approved protocol.
4. Persist the vector index; add retries for Aura connection loss; cache analysis results.
5. Historical Reconstruction: architecture snapshots, rename tracking, evolution diff, rationale extraction from commit messages.
6. Real-repository validation for TS, JS, Java and C++; frontend tests and a recorded browser walkthrough.
7. Commit the working tree; update README/ROADMAP; ADRs for the heuristics.

## 17. Reproducibility instructions

All commands from the repository root unless stated; do **not** run live steps without the Neo4j credentials in `backend/.env`.

```bash
# Backend unit tests (project venv; ~10 s)
cd backend && .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider        # expect: 172 passed

# Frontend checks
cd frontend && npx tsc -b --noEmit && npx oxlint && npx vite build --outDir ../project_audit_2026_10_11/raw/dist_build

# Offline Flask parse/resolve metrics (no database, no network; needs the existing clone)
cd backend && .venv/Scripts/python.exe ../project_audit_2026_10_11/scripts/offline_flask_parse_metrics.py workspace/526e8042-1b3f-414e-9959-117464f02e02

# Live read-only probes (needs backend/.env with working Neo4j; no writes, no LLM)
cd backend && .venv/Scripts/python.exe ../project_audit_2026_10_11/scripts/live_readonly_probe.py  526e8042-1b3f-414e-9959-117464f02e02
cd backend && .venv/Scripts/python.exe ../project_audit_2026_10_11/scripts/findings_confidence_tiers.py 526e8042-1b3f-414e-9959-117464f02e02
cd backend && .venv/Scripts/python.exe ../project_audit_2026_10_11/scripts/live_readonly_probe2.py 526e8042-1b3f-414e-9959-117464f02e02
cd backend && .venv/Scripts/python.exe ../project_audit_2026_10_11/scripts/resolver_precision_check.py 526e8042-1b3f-414e-9959-117464f02e02 examples.tutorial.flaskr.blog.update workspace/526e8042-1b3f-414e-9959-117464f02e02
cd backend && .venv/Scripts/python.exe ../project_audit_2026_10_11/scripts/flow_tree_dump.py 526e8042-1b3f-414e-9959-117464f02e02 examples.tutorial.flaskr.blog.index workspace/526e8042-1b3f-414e-9959-117464f02e02

# Before/after execution-flow comparison (extract HEAD to a scratch folder, run the same script from each tree)
git archive HEAD backend | tar -x -C <scratch>/head
(cd <scratch>/head/backend && <venv python> <abs>/scripts/flow_node_count.py <abs>/backend/.env 526e8042-... examples.tutorial.flaskr.blog.index)
(cd backend && <venv python> <abs>/scripts/flow_node_count.py <abs>/backend/.env 526e8042-... examples.tutorial.flaskr.blog.index)
```

The Flask record id and the Neo4j graph are specific to this machine/database. On another machine, ingest first (`POST /api/repositories {"url": "https://github.com/pallets/flask"}`) and substitute the new id; counts for commit `d73fa1cd` should match, a newer Flask commit will differ. Running the app: `cd backend && uvicorn app.main:app --reload --reload-exclude "workspace/**" --port 8000`; `cd frontend && npm run dev`.

## 18. References to source files, outputs and documents

* Source: see `IMPLEMENTATION_MATRIX.csv` (column `source_files`) and `EVIDENCE_INDEX.md`.
* Existing documentation: `README.md`, `CLAUDE.md` (project constitution), `docs/ROADMAP.md` (outdated), `docs/PRESENTATION_PROMPT.md` (older numbers), `frontend/README.md` (not read).
* Audit outputs: `raw/pytest_full.txt`, `raw/tests_per_file.txt`, `raw/test_ids.txt`, `raw/tsc.txt`, `raw/oxlint.txt`, `raw/vite_build.txt`, `raw/offline_flask_parse_metrics.json`, `raw/live_probe_flask_526e8042.json`, `raw/live_probe2.json`, `raw/findings_confidence_tiers.txt`, `raw/flow_head_committed.txt`, `raw/flow_working_tree.txt`, `raw/flow_tree_blog_index.txt`, `raw/resolver_precision_blog_update.txt`, `raw/registry_stats.txt`.
* AGENTS.md and a `docs/architecture/` or `docs/adr/` folder, an existing research/evaluation directory, benchmark/CSV result files and screenshots were searched for and **not found**.
