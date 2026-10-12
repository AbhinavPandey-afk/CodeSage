# EVIDENCE_INDEX.md — claim → evidence map

Paths are relative to the repository root (`C:\Users\abhin\CodeSage`). `raw/` = `project_audit_2026_10_11/raw/`, `scripts/` = `project_audit_2026_10_11/scripts/`. Status: **V** verified in this audit by execution/measurement; **S** supported by source reading only; **H** historical claim, not independently re-measured; **R** re-measured and compared with a historical claim.

## A. Technology stack

| # | Claim | Status | Evidence |
|---|---|---|---|
| A1 | Backend is Python (venv Python 3.12.10) with FastAPI 0.141.1, Uvicorn 0.52.1, Pydantic 2.13.4 | V | `backend/.venv` `pip list`; `backend/requirements.txt`; `backend/app/main.py` |
| A2 | Parsing uses Tree-sitter 0.26.0 with python 0.25.0, javascript 0.25.0, typescript 0.23.2, java 0.23.5, cpp 0.23.4 grammars | V | `pip list`; `backend/parsing/tree_sitter/loader.py`; `backend/parsing/parsers/*/parser.py` |
| A3 | Graph database is Neo4j (driver 6.2.0), hosted on Neo4j Aura | V | `backend/graph/neo4j/client.py`; `backend/.env.example` comment; live probe connectivity `true` (`raw/live_probe_flask_526e8042.json`) |
| A4 | "Vector layer" is TF-IDF (scikit-learn 1.9.0) vectors in a FAISS (faiss-cpu 1.15.0) exact inner-product index; not neural embeddings | S | `backend/embeddings/vector_store/tfidf_store.py` |
| A5 | LLM provider is Groq (SDK 1.6.0) behind `LLMProvider`; model from `GROQ_MODEL` (default `llama-3.1-8b-instant`) | S | `backend/ai/llm/{base,factory,groq_provider}.py`; `backend/app/core/config.py` |
| A6 | Repository history via GitPython 3.1.58 | S | `backend/ingestion/cloning/clone.py`; `backend/analysis/history/engine.py` |
| A7 | Logging via structlog 26.1.0 | S | `backend/app/core/logging.py` |
| A8 | Frontend: React 19.2.8, TypeScript 6.0.3, Vite 8.2.1, Tailwind CSS 4.3.3, Cytoscape 3.34.0, shadcn/radix-ui, motion; Node v24.17.0 | V | `frontend/package.json`; `node_modules/*/package.json` versions; `raw/vite_build.txt` |
| A9 | Test tooling: pytest 9.1.1 (+pytest-asyncio, httpx); frontend has only `tsc` and `oxlint` | V | `backend/pytest.ini`; `frontend/package.json` (no test runner) |
| A10 | No relational database; repository records persisted to `backend/workspace/registry.json` | S | `backend/app/repositories/repository_store.py` (docstring states this) |

## B. Implementation status

| # | Claim | Status | Evidence |
|---|---|---|---|
| B1 | All five languages have a parser registered | V | `backend/app/core/languages.py` (`IMPLEMENTED_PARSERS`); `backend/app/services/graph_pipeline.py` (`PARSER_REGISTRY`); 44 parser tests in `raw/tests_per_file.txt` |
| B2 | Only Python was validated on a real repository in depth | V | `scripts/offline_flask_parse_metrics.py`; `raw/offline_flask_parse_metrics.json`; registry lists one JS and one Java ingest and no TS/C++ ingest (`raw/registry_stats.txt`) |
| B3 | Ten API router modules / 17 endpoints are registered | V | `backend/app/main.py`; `grep "router\.(get\|post)" backend/app/api/routes/*.py` (17 decorated handlers) |
| B4 | Frontend has 9 tabs wired to the backend | S | `frontend/src/App.tsx`; `frontend/src/lib/navigation.ts` |
| B5 | Historical Reconstruction is limited to component commit statistics | S | `backend/analysis/history/engine.py` (no snapshot/rename/why logic) |
| B6 | Ask-the-Archeologist not exercised in this audit | — | `TEST_RESULTS.md` §5 |

## C. Flask case study (record `526e8042-1b3f-414e-9959-117464f02e02`, commit `d73fa1cd`)

| # | Claim | Status | Evidence |
|---|---|---|---|
| C1 | 236 files, 83 Python files, 2,654 symbols, 3,713 resolved relationships | V | `backend/workspace/registry.json`; `raw/offline_flask_parse_metrics.json` (script re-parse reproduces both numbers) |
| C2 | IR relationship composition (CONTAINS 1,622, IMPORTS 949, CALLS 3,350 raw / 1,072 resolved, INHERITS 117 raw / 70 resolved) | V | `raw/offline_flask_parse_metrics.json` |
| C3 | Neo4j holds 2,647 Symbol nodes and CONTAINS 1,622 / IMPORTS 942 / CALLS 1,071 / INHERITS 70 | V | `scripts/live_readonly_probe.py` → `raw/live_probe_flask_526e8042.json` (`graph_counts`) |
| C4 | Architecture: 8 components, 12 relationships, roles test 3 / api 3 / external_integration 2 | V | same JSON (`architecture`) |
| C5 | 47 findings; severity 1/17/29 | R (matches earlier) | same JSON (`smells.by_severity`) |
| C6 | Confidence tiers 3/21/23 (thresholds 0.7/0.4 from the frontend) | R (matches earlier) | `scripts/findings_confidence_tiers.py` → `raw/findings_confidence_tiers.txt`; thresholds at `frontend/src/lib/analysisModel.ts` lines 14-17 |
| C7 | `terminal_kind` / `terminal_reason` separation exists in code | V | `backend/analysis/execution_flow/models.py` (module docstring, `FlowHop.terminal_reason`); `engine.py` `_terminal_kind_for`, `_leaf_terminal_reason`, `_build_children`; `git diff HEAD --stat` |
| C8 | Fix is covered by unit tests | V | `backend/tests/test_execution_flow_engine.py` (15 tests; names in `TEST_RESULTS.md` §1.1 and `raw/test_ids.txt`) |
| C9 | `blog.index` trace grew from 3 to 16 nodes | R (reproduced) | `scripts/flow_node_count.py` run once on `git archive HEAD` code (`raw/flow_head_committed.txt`: 3) and once on the working tree (`raw/flow_working_tree.txt`: 16) |
| C10 | 8 of the 15 non-root hops in that trace stem from one false `dict.update → blog.update` resolution | V (manual inspection) | `raw/flow_tree_blog_index.txt` (lines with `blog.update` and their children); `raw/resolver_precision_blog_update.txt` (12/12 sampled call sites are `.update(...)` on unrelated objects) |
| C11 | 20 entry points returned; 11 of 20 flows are single-node; 0 proposed flows | V | `raw/live_probe_flask_526e8042.json` (`flows`) |
| C12 | Optimization: 5 proposals (1 CRITICAL, 4 HIGH) | V | same JSON (`optimization`) |
| C13 | Impact: `Flask.test_client` HIGH(6); `test_request_context` HIGH(7); `blog.update` CRITICAL(8) | V | `raw/live_probe2.json` (`impact`) |
| C14 | Typical Flask ingestion time ≈ 8.4 s median (n=50) | V | `raw/registry_stats.txt` |
| C15 | Earlier figures 2,651 symbols / 3,707 relationships / 42 findings / ~8 s / 26 tests | H | `docs/PRESENTATION_PROMPT.md` lines 73, 121-122, 185 |

## D. Tests and build

| # | Claim | Status | Evidence |
|---|---|---|---|
| D1 | 172 backend tests pass (0 fail / 0 skip), 10.01 s | V | `raw/pytest_full.txt` |
| D2 | Tests do not touch Neo4j/HTTP/LLM | V | `grep -l "TestClient\|get_driver" backend/tests/*.py` → no matches |
| D3 | TypeScript check passes; lint has 3 warnings, 0 errors; build succeeds | V | `raw/tsc.txt`, `raw/oxlint.txt`, `raw/vite_build.txt` |
| D4 | 132 / 139 passing-test reports | H | earlier reports supplied with the audit request; no log in repo |
| D5 | No golden repositories and no frontend tests exist | V | `ls` of repo root and `frontend/src` (no `test_repositories/`, no `*.test.*`) |

## E. Design claims worth citing

| # | Claim | Status | Evidence |
|---|---|---|---|
| E1 | The LLM is used only for Q&A and for narrating a verified relationship path | S | `backend/ai/retrieval/{qa_service,relationship_service}.py`; no `get_llm_provider` import in `backend/analysis/**` (grep) |
| E2 | When no graph path exists the relationship endpoint returns a fixed sentence and skips the LLM | S | `backend/ai/retrieval/relationship_service.py` (`not_connected_explanation`); `tests/test_relationship_evidence.py::test_not_connected_explanation_names_both_symbols_and_no_llm_needed` |
| E3 | Prompt boundary: instructions in `system`, evidence in a delimited block, "treat as data" rule | S | `backend/ai/prompts/qa_prompt.py`, `relationship_prompt.py` |
| E4 | Risk levels come from a fixed rubric of named signals, not from the LLM | S | `backend/analysis/impact/risk.py` (`score_risk`, `_LEVEL_THRESHOLDS`) |
| E5 | URL validation blocks non-GitHub hosts, `ext::`, `file://`, traversal | S | `backend/ingestion/github/validation.py`; `backend/tests/test_url_validation.py` |
| E6 | The tool never writes to the analysed repository | S | no write path in `backend/analysis/optimization/engine.py`; clone is read-only apart from the history-deepening `git fetch` |
| E7 | `.env` is not in version control | V | `git ls-files` → only `backend/.env.example`; `git log --all -- backend/.env` → empty |

## F. Items with no supporting evidence in the repository

Research objectives / questions, literature review, bibliography, baselines and tool comparison, user study, screenshots (only `frontend/src/assets/hero.png`, a static asset not verified to be a screenshot), supervisor/student declarations. See `REPORT_WRITER_HANDOFF.md` §10.
