# TEST_RESULTS.md — CodeBase Archeologist

Audit date: **2026-10-11** (local time, IST +05:30). Machine: Windows 11, Git Bash/PowerShell.
Branch: `main`, HEAD `9040747`, working tree had **76 modified/untracked entries before the audit** (preserved; the only addition made by this audit is the `project_audit_2026_10_11/` directory — see §6).

Raw outputs are stored in `project_audit_2026_10_11/raw/`.

---

## 1. Commands that were run, and their actual results

| # | Command (working dir) | Started | Exit | Result | Raw output |
|---|---|---|---|---|---|
| 1 | `python -m pytest -q -p no:cacheprovider` (`backend/`, **system** Python 3.14.6) | 20:34:09 | 2 | **Not a valid test run** – 12 collection errors: `ModuleNotFoundError: tree_sitter / neo4j / git`. System Python has no project dependencies installed. Recorded for transparency; it says nothing about code quality. | (superseded; not kept) |
| 2 | `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` (`backend/`, project venv, Python 3.12.10) | 20:34:24 | **0** | **172 passed, 0 failed, 0 skipped, 0 errors, 0 warnings reported**, in 10.01 s | `raw/pytest_full.txt` |
| 3 | `.venv/Scripts/python.exe -m pytest --collect-only -q` | 20:34 | 0 | 172 test IDs collected, across 21 files | `raw/test_ids.txt`, `raw/tests_per_file.txt` |
| 4 | `npx tsc -b --noEmit` (`frontend/`, TypeScript 6.0.3) | 20:35 | **0** | No type errors | `raw/tsc.txt` |
| 5 | `npx oxlint` (`frontend/`, oxlint 1.75) | 20:35 | **0** | 0 errors, **3 warnings** (details below) | `raw/oxlint.txt` |
| 6 | `npx vite build --outDir <audit raw dir>` (`frontend/`, Vite 8.2.1) | 20:35:15 | **0** | Build succeeded in 2.03 s; JS bundle 980.83 kB (296.32 kB gzip); Vite warns that a chunk exceeds 500 kB. Output directory was deleted afterwards (the project's own `frontend/dist` was not touched). | `raw/vite_build.txt` |

Note on command 6: the project's `npm run build` is `tsc -b && vite build`. `tsc -b` (command 4) and `vite build` (command 6) were run separately so the build artefacts could be redirected away from `frontend/dist`.

### 1.1 Backend test count per file (172 total)

| File | Tests | Area covered |
|---|---:|---|
| `test_architecture_reconstruction.py` | 12 | component grouping key, role inference (api/data_access/external/service/test/other), confidence label thresholds, third-party dependency extraction |
| `test_architecture_violations.py` | 9 | boundary violations, layer skips, component cycles, coupling thresholds |
| `test_cpp_parser.py` | 8 | C++ parser |
| `test_execution_flow_engine.py` | 15 | terminal_kind vs terminal_reason, traversal through external_integration, depth/branch/budget limits, cycle safety, proposed-flow splice |
| `test_finding_identity.py` | 6 | stable finding IDs |
| `test_history_engine.py` | 7 | commit→component aggregation (pure function, no real Git) |
| `test_impact_classifiers.py` | 15 | endpoint/service/test/import classifiers |
| `test_impact_risk.py` | 6 | deterministic risk rubric |
| `test_java_parser.py` | 10 | Java parser |
| `test_javascript_parser.py` | 8 | JavaScript parser |
| `test_optimization_engine.py` | 8 | proposal text, risk/confidence, finding-ID linkage |
| `test_parser_base.py` | 3 | `dedupe_symbol_id` etc. |
| `test_python_parser.py` | 7 | Python parser |
| `test_related_findings.py` | 4 | related-finding linking |
| `test_relationship_evidence.py` | 3 | relationship evidence rendering / not-connected message |
| `test_relationship_kind.py` | 4 | DIRECT vs INDIRECT, hop count |
| `test_smell_algorithms.py` | 8 | strongly-connected components / cycle path |
| `test_smell_confidence.py` | 14 | finding-confidence formulas and context flags |
| `test_smells_schema_compat.py` | 4 | API schema backward compatibility |
| `test_typescript_parser.py` | 11 | TypeScript parser |
| `test_url_validation.py` | 10 | GitHub URL validation / injection rejection |
| **Total** | **172** | |

### 1.2 Frontend lint warnings (oxlint, exit 0)

1. `src/lib/investigation.tsx:56:17` – `react(only-export-components)`.
2. `src/components/ui/button.tsx:67:18` – `react(only-export-components)`.
3. `src/components/RepositoryOverview.tsx:27:3` – `react-hooks(exhaustive-deps)`: a `useEffect` with a `setState` call and no dependency array ("can lead to an infinite chain of updates"). This one is a genuine potential defect and should be looked at.

---

## 2. About the historical test counts (132 → 139 → 172)

Earlier reports quoted 132, 139 and 172 passing backend tests, and `docs/PRESENTATION_PROMPT.md` (an older document) says "26 passing unit tests". **The only number measured in this audit is 172 passed (2026-10-11, command 2).** The earlier numbers are consistent with a suite that grew over time; they are not competing claims. The report should state the date of any test total it quotes, because the count changes whenever tests are added.

Five of the 21 test files are currently **untracked** (never committed; 32 of the 172 tests): `test_finding_identity.py` (6), `test_related_findings.py` (4), `test_relationship_kind.py` (4), `test_smell_confidence.py` (14), `test_smells_schema_compat.py` (4). Five more tracked test files contain uncommitted edits: `test_architecture_reconstruction.py`, `test_execution_flow_engine.py`, `test_impact_classifiers.py`, `test_optimization_engine.py`, `test_smell_algorithms.py`. The 172 figure therefore describes the **working tree**, not commit `9040747`. Committing before the final submission is advisable.

---

## 3. What these tests are — and are not

* All 172 tests are **unit tests of pure functions and parser output**. None of them connects to Neo4j, calls an HTTP route, clones a repository, or calls the LLM (verified by grep: no test imports `TestClient` or `get_driver`).
* Engines that read Neo4j (`reconstruct_architecture`, `run_smell_detection`, `reconstruct_execution_flow`, `analyze_impact`, `find_relationship`) are therefore tested only through their **pure helper functions** (`_build_children`, `_leaf_terminal_reason`, `_build_proposal`, `aggregate_component_history`, …). The Cypher queries themselves have no automated test.
* There are **no frontend tests** (no test runner in `package.json`, no `*.test.*`/`*.spec.*` files). The frontend is covered only by `tsc` and `oxlint`.
* There is **no golden-repository fixture set** (`test_repositories/` from CLAUDE.md §33 does not exist). Parser tests use inline source snippets.
* A passing unit suite is not end-to-end validation. End-to-end evidence in this audit comes from the read-only live probes in §4, on a single repository (Flask).

---

## 4. Live read-only validation against the existing Flask graph

Authorised by the user ("read-only"). Method: the real FastAPI application was driven **in-process** with `fastapi.testclient.TestClient` (no server started, no ingestion, no graph writes, no LLM calls, no `git fetch`). Only `SELECT`-style Cypher (`MATCH … RETURN`) was issued by the audit scripts. Credentials were read from `backend/.env` by the application itself and never printed or saved.

Target: repository record `526e8042-1b3f-414e-9959-117464f02e02` (pallets/flask, commit `d73fa1cd`, status `ready`).

| Probe | Script | Run at | Result | Raw output |
|---|---|---|---|---|
| Connectivity + graph counts + all analysis routes (`/health`, `/architecture`, `/smells`, `/optimization`, `/flows`, `/flows/reconstruct`×20) | `scripts/live_readonly_probe.py` | 20:46:53 | all HTTP 200; Neo4j reachable | `raw/live_probe_flask_526e8042.json` |
| Finding confidence tiers | `scripts/findings_confidence_tiers.py` | ~20:48 | 47 findings; tiers 3/21/23 | `raw/findings_confidence_tiers.txt` |
| Execution-flow HEAD (pre-fix) vs working tree | `scripts/flow_node_count.py` | ~20:48 | `blog.index` 3 → 16 nodes (see METRICS) | `raw/flow_head_committed.txt`, `raw/flow_working_tree.txt` |
| Graph views, symbol search/suggestions, impact (3 symbols), relationship graph-half (2 pairs), latencies | `scripts/live_readonly_probe2.py` | 20:49:27 | all HTTP 200 | `raw/live_probe2.json` |
| Resolver precision spot check | `scripts/resolver_precision_check.py` | ~20:50 | 12 of 12 inspected call sites into `blog.update` are unrelated `.update(...)` calls | `raw/resolver_precision_blog_update.txt` |
| Full execution-flow tree with call-site source lines | `scripts/flow_tree_dump.py` | ~20:50 | 16-node tree printed | `raw/flow_tree_blog_index.txt` |
| Offline parse + resolve of the cloned Flask workspace (no DB) | `scripts/offline_flask_parse_metrics.py` | 20:36:02 | reproduces 2,654 symbols / 3,713 resolved edges | `raw/offline_flask_parse_metrics.json` |

A first run of the impact probe failed with HTTP 422 because the audit script used the wrong request field name (`target_uid` instead of `symbol_uid`); it was a script error, not an application defect, and was corrected and re-run.

---

## 5. Things that could NOT be run or verified, and why

| Item | Reason |
|---|---|
| Browser/UI verification (navigation, Understand/Components/Symbols flow views, inspectors, Cytoscape interaction) | No browser-automation tool was used in this session; no screenshots were taken. UI claims in the report are based on source inspection plus a successful TypeScript build only. **No UI behaviour is claimed as verified.** |
| `GET /history` on Flask | The endpoint calls `git fetch --deepen 500` on the cloned workspace (network access and a write to the clone). Not run. History is covered only by unit tests of the pure aggregation function. |
| `POST /ask` and the LLM-narrated half of `POST /graph/relationship` | The user authorised read-only checks only; these call Groq and send evidence text to an external API. The deterministic graph half of relationship investigation (`find_relationship`) **was** run. |
| Fresh ingestion of any repository (clone → graph → embed) | Would write to the Aura database and the network. Ingestion evidence instead comes from `backend/workspace/registry.json` (59 completed runs; see METRICS) and the offline re-parse. |
| In-memory vector index for Flask | The index lives only in server memory (`embeddings/registry.py`) and is lost on restart; none exists now, so retrieval could not be exercised without a re-ingest. |
| Neo4j-backed integration tests / API tests | Do not exist in the repository. |
| Parser behaviour on real TypeScript and C++ repositories | No TS or C++ repository appears in the ingestion registry; only unit tests exist. |
| Comparison against Sourcegraph, Copilot or other tools | No such experiment exists in the repository. Not performed. |

---

## 6. Actions that touched the filesystem

* Created `project_audit_2026_10_11/` (reports, `scripts/`, `raw/`). Nothing else in the tracked tree was modified; `git status` shows the same 76 pre-existing entries plus this one new untracked directory.
* Temporary: `git archive HEAD backend` was extracted into the session scratchpad (outside the repository) to run the committed pre-fix execution-flow engine; it is not part of the repository.
* pytest/tsc/vite/oxlint may have refreshed ignored caches (`__pycache__`, `tsbuildinfo`); no source files were changed.
* No dependency was installed. No production code, test, threshold or reference dataset was edited.
