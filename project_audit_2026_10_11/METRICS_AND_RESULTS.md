# METRICS_AND_RESULTS.md — CodeBase Archeologist

All values below were obtained on **2026-10-11** unless stated otherwise. Categories:

* **CURRENT** – measured in this audit by a command or script that can be re-run.
* **HISTORICAL** – quoted from older documents or earlier reports; *not* re-measured, or re-measured and compared (outcome stated).
* **ESTIMATE** – derived by hand from CURRENT data; method stated.
* **UNMEASURED** – a goal or claim for which no measurement exists.

Commit under test: `main` @ `9040747` **plus 76 uncommitted working-tree entries** (all CURRENT figures describe the working tree). Flask commit analysed: `d73fa1cd` (49 of 50 registry runs; one early run used `d318b683` with the same counts) (record `526e8042-1b3f-414e-9959-117464f02e02`).

---

## 1. Software-quality metrics (application level)

| Metric | Value | Unit | Repo/dataset | Method | Evidence | Limitations | Cat. |
|---|---:|---|---|---|---|---|---|
| Backend automated tests passed | **172** | tests | CodeSage `backend/tests` | `pytest -q` in project venv (Py 3.12.10), 20:34:24 | `raw/pytest_full.txt` | Unit tests only; no DB/API/LLM tests; 32 of them in untracked files | CURRENT |
| Backend tests failed / skipped / errored | 0 / 0 / 0 | tests | same | same | same | – | CURRENT |
| Backend suite wall time | 10.01 | s | same | pytest summary | same | Machine-dependent | CURRENT |
| Backend source size (non-test `.py`) | 6,934 | lines | `backend/` excl. `.venv`, `workspace`, tests | `wc -l` | audit session | Includes blank lines/comments | CURRENT |
| Backend test code size | 1,989 | lines | `backend/tests/*.py` | `wc -l` | audit session | – | CURRENT |
| Frontend TS/TSX size (excl. `components/ui/`) | 8,642 | lines | `frontend/src` | `wc -l` | audit session | – | CURRENT |
| TypeScript type-check | pass (exit 0) | – | frontend | `npx tsc -b --noEmit` | `raw/tsc.txt` | – | CURRENT |
| Lint | 0 errors, 3 warnings | – | frontend | `npx oxlint` | `raw/oxlint.txt` | One warning is a real hook-dependency smell | CURRENT |
| Production build | success, 980.83 kB JS (296.32 kB gzip), 70.68 kB CSS | – | frontend | `vite build` | `raw/vite_build.txt` | >500 kB chunk warning; no code-splitting | CURRENT |
| Frontend automated tests | 0 | tests | frontend | no test runner configured | `frontend/package.json` | – | CURRENT |
| Earlier backend pass counts | 26 (old deck), 132, 139 | tests | – | quoted in earlier reports | `docs/PRESENTATION_PROMPT.md` (26); 132/139 only in the earlier reports supplied with the request | Superseded by 172; no log of those runs in repo | HISTORICAL |

## 2. Ingestion and parsing metrics — Flask

| Metric | Value | Unit | Method | Evidence | Limitations | Cat. |
|---|---:|---|---|---|---|---|
| Files in clone (after ignore-dirs) | 236 | files | `scan_workspace` at ingestion | `backend/workspace/registry.json` | Includes non-code files | CURRENT |
| Python files parsed | 83 | files | offline re-parse with project parsers | `raw/offline_flask_parse_metrics.json` | – | CURRENT |
| Parse errors | 0 | – | same | same | tree-sitter error nodes may still exist silently; only recorded `parse_errors` counted | CURRENT |
| Symbols extracted (IR) | 2,654 | symbols | same; matches registry `symbol_count` | same | – | CURRENT |
| …by type | file 83, import 949, function 1,060, class 160, method 402 | – | same | same | – | CURRENT |
| Raw relationships emitted | 6,038 | rels | same | same | – | CURRENT |
| …by type (raw) | contains 1,622; imports 949; calls 3,350; inherits 117 | – | same | same | – | CURRENT |
| Relationships resolved to a repo symbol | 3,713 | edges | `resolve_relationships` | same; matches registry `relationship_count` | – | CURRENT |
| …CALLS resolved | 1,072 of 3,350 = **32.0 %** | – | same | same | The 68 % unresolved are mostly calls to stdlib/third-party/dynamic targets (not necessarily errors) | CURRENT |
| …CALLS ambiguous (multiple same-name candidates, left unresolved at conf 0.3) | 871 | calls | same | same | – | CURRENT |
| …INHERITS resolved | 70 of 117 = 59.8 % | – | same | same | – | CURRENT |
| Resolved-CALLS confidence values | 0.95 → 239; 0.75 → 833 | edges | same | same | Only two values exist: exact-qualified-name or unique-short-name | CURRENT |
| Parse + resolve time (offline, 83 files) | 2.14 s + 0.023 s | s | `time.perf_counter` | same | Single run, no repetition | CURRENT |
| Graph in Neo4j: Symbol nodes | 2,647 | nodes | Cypher `count` | `raw/live_probe_flask_526e8042.json` | 7 fewer than IR (2,654); the difference is entirely in `import` symbols (949 → 942); cause not isolated (consistent with duplicate uids collapsing under `MERGE`) | CURRENT |
| Graph edges in Neo4j | CONTAINS 1,622; IMPORTS 942; CALLS 1,071; INHERITS 70 | edges | Cypher | same | CALLS 1 fewer than IR: `MERGE (a)-[:CALLS {source_line}]->(b)` collapses two calls on one line | CURRENT |
| End-to-end ingestion time, Flask (clone→graph→embed→ready) | median 8.4 s (min 6.4, max 127.3), n = 50 ready runs | s | `updated_at − created_at` per record | `raw/registry_stats.txt` | Network/Aura dependent; includes clone | CURRENT |
| Same, other repos (n=ready runs) | requests 10.9 s (1); jinja median 80.4 s (2; 7.0–153.8); black median 15.4 s (4); hackathon-starter 6.0 s (1); spring-petclinic 5.4 s (1) | s | same | same | Very small n; outliers not investigated | CURRENT |
| Registry outcome counts | 59 ready / 8 failed of 67 | records | `registry.json` | `raw/registry_stats.txt` | Developer runs, not a controlled benchmark | CURRENT |
| Failure causes | Flask 5× Aura connection errors ("defunct connection"/write failure); black 1× Neo4j constraint violation (since fixed by `dedupe_symbol_id`, later black runs ready); django 2× rejected: "Repository exceeds 5000 files" | – | same | same | Limit is a configured default (`MAX_REPO_FILES=5000`) | CURRENT |
| Earlier Flask figures | 236 files, 2,651 symbols, 3,707 relationships, ~8 s | – | older deck | `docs/PRESENTATION_PROMPT.md` L121-122 | 2,651/3,707 differ slightly from today's 2,654/3,713 because parser changes since then; ~8 s agrees with the measured median 8.4 s | HISTORICAL |

## 3. Architecture Reconstruction — Flask (CURRENT)

Source: `GET /api/repositories/{id}/architecture` (`raw/live_probe_flask_526e8042.json`).

| Metric | Value |
|---|---|
| Components | 8 (not truncated) |
| Inter-component relationships | 12 |
| Roles assigned | test 3, api 3, external_integration 2 (no service, data_access, model) |
| Component confidence labels | Confirmed 7, Inferred 1 |
| Components | `tests` (test, 23 files, 1,076 symbols); `src/flask` (external_integration, 24, 442); `examples/tutorial` (api, 9, 45); `tests/type_check` (test); `examples/celery` (api); `tests/test_apps` (test); `examples/javascript` (api); `docs` (external_integration, 1 file, 2 symbols, Inferred) |
| Latency | 0.82–0.94 s |

**Interpretation limits (important):** the Flask *framework core* (`src/flask`) is labelled `external_integration` because the role rules treat any non-stdlib import (e.g. `werkzeug`, `click`) as external-integration evidence; the three `examples/*` directories are labelled `api` because they contain `@app.route` handlers. Flask has no service or repository layer, so the layered-architecture vocabulary describes it poorly. This is a property of the heuristic, not evidence that Flask is layered. Expected-vs-actual architecture comparison against a ground truth has **not** been done.

## 4. Architecture Analysis — Flask

| Metric | Earlier report (HISTORICAL) | Re-measured 2026-10-11 (CURRENT) | Match |
|---|---|---|---|
| Total findings | 47 | **47** | ✔ |
| Severity High / Medium / Low | 1 / 17 / 29 | **1 / 17 / 29** | ✔ |
| Confidence tier High / Medium / Low | 3 / 21 / 23 | **3 / 21 / 23** | ✔ |

* Confidence tiers use the **frontend's** thresholds (`frontend/src/lib/analysisModel.ts`: High ≥ 0.7, Medium ≥ 0.4, else Low) applied to the API's raw `confidence` (range 0.25–0.75). The backend itself returns only the numeric value (`confidence_label` is not a field of the smell response). Using the 0.75/0.4 Confirmed/Inferred thresholds instead gives 1 / 23 / 23 — the metric is threshold-dependent, so state the thresholds when citing it. (`raw/findings_confidence_tiers.txt`)
* Severity × confidence: HIGH/High 1; MEDIUM/High 2, MEDIUM/Medium 12, MEDIUM/Low 3; LOW/Medium 9, LOW/Low 20. This confirms severity and confidence are independent quantities (e.g. 3 MEDIUM findings have Low confidence; 9 LOW findings have Medium confidence).
* By type: dead_code_candidate 20 (capped at 20 by `_DEAD_CODE_LIMIT`), large_function 16, god_class 4, circular_component_dependency 3, circular_dependency 2, architecture_boundary_violation 1, excessive_component_coupling 1.
* Context flags present: SUPPORTING_STRUCTURE 25, LENGTH_BASED_HEURISTIC 16, DYNAMIC_DISPATCH_RISK 20, FRAMEWORK_HUB 5, METHOD_COUNT_HEURISTIC 4, EXPECTED_TEST_DEPENDENCY 2, HEURISTIC_LAYERING 1, INTRA_CLASS_DELEGATION 1.
* Reproducibility: the number matches the earlier report, but the same graph and same code produced both; it demonstrates determinism, **not** correctness (no ground truth of "true smells" exists).
* Older deck figure "42 findings" (`docs/PRESENTATION_PROMPT.md` L185) predates the architecture-level detectors and the 20-item dead-code cap; it is superseded (HISTORICAL).
* Latency: 1.08–1.25 s.

## 5. Architecture Optimization — Flask (CURRENT)

5 proposals (1 CRITICAL, 4 HIGH risk): one per component-level violation (1 boundary + 3 cycles + 1 coupling). `layer_skip` proposals: 0 (a service-role component does not exist in Flask). Latency 1.66–1.85 s. Risk levels derive from a *representative* symbol's impact analysis (the most-connected symbol in the affected components), so they inherit the resolver-precision limits in §7.

## 6. Execution Flow Reconstruction — Flask

### 6.1 The `terminal_kind` / `terminal_reason` fix — verified

* **Code**: present in the working tree (`backend/analysis/execution_flow/models.py` docstring + `FlowHop.terminal_reason`; `engine.py` `_terminal_kind_for`, `_leaf_terminal_reason`, `_build_children`). Roles no longer stop traversal.
* **Uncommitted**: committed HEAD `9040747` still contains the *old* behaviour; the fix exists only in the working tree. (`git diff HEAD --stat` shows `engine.py` +144/−31 lines, `models.py` +21.)
* **Unit tests**: `test_build_children_labels_role_but_does_not_stop_traversal_there`, `test_build_children_traverses_through_external_integration_component`, `test_leaf_terminal_reason_*` (4), `test_build_children_depth_limit_reason`, `test_build_children_reports_branch_limit_omission` — all pass.
* **Before/after on identical live data** (HEAD code extracted via `git archive` vs working tree, same Neo4j graph, `raw/flow_head_committed.txt`, `raw/flow_working_tree.txt`):

| Entry point | Nodes incl. entry — HEAD (before) | Nodes — working tree (after) |
|---|---:|---:|
| `examples.tutorial.flaskr.blog.index` | **3** | **16** |
| `…blog.create` | 4 | 18 |
| `…auth.login` | 4 | 18 |
| `…blog.delete` | 6 | 6 |

The historical claim "`blog.index` increased from 3 nodes to 16 nodes" is therefore **reproduced** (counting the entry node). Whether "nodes" included the entry node in the original report is not stated; here the root is counted.

### 6.2 Caveat discovered: part of the expansion is resolver false positives

`raw/flow_tree_blog_index.txt` shows the 16-node tree. Two hops are `Flask.update_template_context → examples.tutorial.flaskr.blog.update`, produced by the call sites `context.update(self.ensure_sync(func)())` (`src/flask/app.py:617`) and `context.update(orig_ctx)` (`:619`) — ordinary `dict.update` calls resolved to the tutorial's unrelated route handler `blog.update` by the unique-short-name rule (confidence 0.75). Each of those two spurious nodes then spawns three children (`get_post`, `get_db`, `flash`), so **8 of the 15 non-root nodes (53 %) in this trace are artefacts of that one false resolution** (ESTIMATE by manual inspection of the printed tree). A manual check of the first 12 incoming CALLS edges of `blog.update` (29 in total, all 0.75) found 12/12 to be unrelated `.update(...)` calls (`raw/resolver_precision_blog_update.txt`). The traversal fix is correct in design (it stops treating *role* as a stop reason) but the headline "16 nodes" must **not** be presented as 16 genuine hops, nor as an accuracy result.

### 6.3 All 20 listed entry points (CURRENT)

`GET /flows` returns at most 20 entry points (`detect_entry_points(limit=20)`, sorted by qualified name), so Flask's route-decorated functions beyond the first 20 (alphabetically) are not offered.

| Metric | Value |
|---|---|
| Entry points returned | 20 (15 under `examples/*`, 5 under `tests/test_appctx.*`) |
| Flow node counts (incl. root), sorted | 1,1,1,1,1,1,1,1,1,1,1,2,6,8,15,15,16,18,18,18 |
| Flows that are a single node (no resolved callee) | 11 of 20 |
| Flows truncated by the 150-hop budget | 0 |
| Flows with a PROPOSED variant | **0** (needs a `layer_skip`, absent in Flask) |
| Leaf `terminal_reason` totals | DEPTH_LIMIT 42; NO_RESOLVED_CALLEES 14; UNRESOLVED 12; STANDARD_LIBRARY 8 (EXTERNAL_DEPENDENCY 0, BRANCH_LIMIT 0) |

Note: a leaf at depth 5 is always labelled `DEPTH_LIMIT`, even if it has no callees (the depth check precedes the "no edges" check in `_build_children`). So some DEPTH_LIMIT leaves may really be NO_RESOLVED_CALLEES (code observation).

## 7. Resolver / evidence quality (CURRENT, qualitative + sample)

| Observation | Evidence |
|---|---|
| Only 32 % of CALLS resolve to a repository symbol; 26 % of all CALLS (871/3,350) are discarded as ambiguous | §2 |
| Unique-short-name matching gives high-fan-in false positives for generic names (`update`, `get`, `add`…) | `blog.update` has 29 incoming CALLS (all conf 0.75) in a repo where only one symbol is named `update` |
| Downstream effect: impact analysis for `blog.update` reports **22 direct / 48 indirect dependents, 20 affected APIs, risk CRITICAL (score 8)** | `raw/live_probe2.json` — almost certainly inflated by the same false edges |
| The "unresolved" CALLS are not stored as edges; only their raw names are stored on the source symbol (`unresolved_call_targets`) | `graph/loader.py` |

## 8. Other live-API observations — Flask (CURRENT)

| Item | Result |
|---|---|
| Graph view `files` | 23 nodes, 53 edges (edge type `USES` only), not truncated, 0.5–1.7 s |
| Graph view `classes` | 85 nodes, 86 edges (CONTAINS, INHERITS, USES), 0.3–0.4 s |
| Symbol search `q=Flask` | HTTP 200, 20 hits |
| Suggested impact starting points | `Flask.test_client`, `Flask.test_request_context`, `blog.update`, … (top-degree symbols; includes test helpers) |
| Impact `Flask.test_client` | 45 direct / 5 indirect, 50 tests, risk HIGH (score 6) |
| Impact `Flask.test_request_context` | 32 / 6, risk HIGH (7) |
| Impact `blog.update` | 22 / 48, 20 APIs, risk CRITICAL (8) – see §7 |
| Relationship (graph half only, no LLM) | `test_client`↔`test_request_context`: INDIRECT, 2 hops via two `CONTAINS` edges (i.e. "siblings in the same class"); `test_client`↔`blog.update`: INDIRECT, 3 hops ending in a `CALLS` edge at 0.75 (the false edge of §7) |
| Latencies (single run) | impact 0.15–0.16 s; architecture 0.8–0.9 s; smells 1.1–1.3 s; optimization 1.7–1.8 s |

Observation: a "relationship" found only through two `CONTAINS` hops merely says two methods belong to the same class; the UI/report should not present that as a meaningful dependency.

## 9. Not measured (no data exists — do not quote as results)

* Parser/resolver precision and recall against a hand-labelled ground truth.
* Accuracy of reconstructed architecture or roles against a known-correct architecture.
* Quality/faithfulness of Ask-the-Archeologist answers (no evaluation set; the retrieval confidence formula in `ai/retrieval/evidence.py` is a heuristic, not a calibrated probability).
* Comparison with Sourcegraph, GitHub Copilot, or any other tool; user study; statistical tests; repeatability/sensitivity experiments; scalability beyond 482 files (largest ingested: `psf/black`, 482 files, 4,985 symbols, 6,765 relationships, 13.7–19.6 s).
* Performance at the 5,000-file limit (Django was rejected by that limit).
* TypeScript and C++ on real repositories. JavaScript (`sahat/hackathon-starter`: 171 files, 386 symbols, 464 relationships) and Java (`spring-projects/spring-petclinic`: 132 files, 753 symbols, 993 relationships) each have one successful ingest in the registry (CURRENT counts from `registry.json`), but no result was inspected for correctness.
