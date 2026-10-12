# Call-resolution change — measured results (Phase 2)

Repository state: baseline = committed `caf823d`; after = working tree on top of `caf823d` (uncommitted).
Workspace used for everything: the existing Flask clone `backend/workspace/526e8042-1b3f-414e-9959-117464f02e02` (commit `d73fa1cd`).
No Neo4j connection, no network, no writes to your database. Date: 2026-10-12.

## 1. Labelled-sample precision / recall

Unit = one call site (file, line, target text). Label = the call's true target by language semantics, using variable
types evident from nearby code (e.g. an `app` that is a `Flask` instance); library/builtin/dynamic targets = `EXTERNAL`.
Ambiguous cases were excluded as `SKIP` (3 in sample A, 4 in sample B). Single annotator (the assistant), no second rater. **Label correction (Phase 2 review):** one sample-A label (`examples/tutorial/flaskr/blog.py:55 abort`) was wrong — the file imports `abort` from `werkzeug.exceptions`, so the target is EXTERNAL; corrected in the file with a note, and both resolvers re-scored on the corrected labels (A before 0.692/0.720 → 0.679/0.716; A after 1.000/0.800 → 1.000/0.811).

* **Sample A** (`flask_sample_labelled.json`, 117 scored): labelled *before* the resolver was changed, stratified by the
  baseline resolver's output. The rule design was done afterwards with these examples in view, so A can be optimistic.
* **Sample B** (`flask_heldout_labelled.json`, 116 scored): drawn afterwards with a different seed, stratified by call shape
  (resolver-independent), A's call sites excluded, labelled **without any resolver output visible**.

| Sample | Resolver | Bound | Correct | Wrong repo target | Bound but truly external | Precision | Recall |
|---|---|---:|---:|---:|---:|---:|---:|
| A | before | 78 | 53 | 14 (all: edge ends at an *import statement*) | 11 | **0.679** | **0.716** |
| A | after | 60 | 60 | 0 | 0 | **1.000** | **0.811** |
| B (held out) | before | 45 | 35 | 5 | 5 | **0.778** | **0.593** |
| B (held out) | after | 41 | 41 | 0 | 0 | **1.000** | **0.695** |

* Precision = correct / bound. Recall = correct / sites whose label is a repository definition (A: 74, B: 59).
* 60/60 and 41/41 are small samples: a 95 % lower bound for the true precision is roughly 0.94 and 0.91 (rule of three), not 1.0.
* Per-stratum detail and population-weighted estimates are in `result_baselineHEAD_*.json` / `result_after_*.json`.
  Population-weighted recall (strata weighted by their share of all Flask call sites): A 0.579 → 0.758; B 0.501 → 0.514 —
  i.e. on the whole population recall is roughly flat in B: the gain from reaching real definitions is offset by the loss
  below.
* Recall that the change gives up: calls through a **typed receiver the parser cannot see** — `app.test_client()` where
  `app` is a `Flask` fixture, `current_app.make_shell_context()`, `app.config.from_object(...)` — used to be bound by
  unique-name luck and are now unresolved (A, stratum `recv.attr`: recall 1.00 → 0.47, precision 0.71 → 1.00).
* Option evaluated and **not** adopted: a fallback that binds an unknown-receiver call when the attribute is a method name
  defined in exactly one class. On the 233 labelled sites it recovers 19–22 correct edges but adds 5–9 false ones
  (≈ 80 % precision for that tier), so it would reintroduce the failure the change removes.

## 2. Flask resolution counts (offline parse + resolve, 83 files)

| | Before | After |
|---|---:|---:|
| CALLS call sites | 3,350 | 3,350 |
| …resolved to a **definition** | 833 | 739 |
| …resolved to an **import statement** (edge ends at the `import`) | 239 | 0 |
| …left ambiguous (confidence 0.3) | 862 | 12 |
| INHERITS resolved (of 117) | 70 | 76 |
| Symbols (IR) | 2,654 | 2,353 |
| Resolved CALLS confidence values | 0.95 ×239 (all import nodes), 0.75 ×833 | 0.95 ×245, 0.90 ×456, 0.85 ×38 (rule-based) |

The symbol count fell by 301 because the Python parser no longer emits a bogus extra import symbol for every
`from x import y` (a `child is module_node` identity test never matched).
Other repositories (counts only, `other_repos_calls_before_after.txt`): requests 930→742 definition-bound calls,
jinja 2,704→1,760, black 2,060→1,804, hackathon-starter (JS) 130→131, spring-petclinic (Java) 282→61. Java drops most
because Java receivers are fields/locals whose declared types the parser does not record.

## 3. Downstream effect on Flask (real engines on an in-memory stand-in for the graph)

`scripts/downstream_offline.py` runs the real reconstruction / smell / optimization / execution-flow / impact code against
an in-memory graph built from the parser+resolver in the current directory. **Validation of the stand-in:** run with the
committed code it reproduces the live-database numbers recorded earlier exactly — 2,647 nodes; CONTAINS 1,622 / IMPORTS
942 / CALLS 1,071 / INHERITS 70; 8 components, 12 relationships; **47 findings**, severity 1/17/29, confidence tiers
3/21/23, same type counts; 5 optimization proposals (1 CRITICAL, 4 HIGH); impact results for the three probe symbols —
with one exception: execution-flow tree sizes differ (blog.index 13 vs 16 live) because the engine picks the three
highest-confidence callees per hop and ties are ordered by database row order, which the stand-in cannot reproduce.
Before/after flow comparisons below therefore use the stand-in on both sides.

| Metric (Flask) | Before | After |
|---|---:|---:|
| `blog.update` incoming CALLS | 30 | 1 |
| Architecture components / relationships | 8 / 12 | 8 / **6** |
| Findings total | 47 | **41** |
| …severity H/M/L | 1 / 17 / 29 | 0 / 12 / 29 |
| …confidence tier H/M/L (0.7/0.4) | 3 / 21 / 23 | 0 / 20 / 21 |
| …by type | boundary 1, circular_dep 2, god_class 4, large_fn 16, circ_component 3, coupling 1, dead_code 20 | god_class 4, large_fn 16, coupling 1, dead_code 20 |
| Optimization proposals | 5 (1 CRITICAL, 4 HIGH) | 1 (HIGH) |
| Flow sizes (20 entry points, sorted) | 1×11, 2, 6, 8, 12, 12, 13, 15, 15, 15 | 1×10, 2, 3, 3, 3, 4, 4, 4, 4, 5, 5 |
| `blog.index` trace (nodes incl. entry) | 13 (incl. 1 spurious `blog.update` hop and its 3 children; the live database gave 16 with 2 such hops) | 4 |
| Impact `Flask.test_client` | 45 direct / 5 indirect, HIGH (6) | 0 / 0, LOW (1) |
| Impact `Flask.test_request_context` | 32 / 6, HIGH (7) | 0 / 0, LOW (1) |
| Impact `blog.update` | 22 / 48, 20 APIs, CRITICAL (8) | 0 / 0, LOW (1) |

How to read this:
* The `blog.update` result, the spurious flow branch, and the CRITICAL rating disappear — these were artefacts of false edges.
* The loss of 6 findings (2 circular call dependencies, 3 circular component dependencies, 1 boundary violation) and 4
  optimization proposals follows from removed edges; those cycles ran through edges that included name-only matches. Whether any
  of them was a *true* cycle was not checked finding by finding.
* **Impact for `Flask.test_client` and `Flask.test_request_context` drops to zero** — the real dependents are tests calling
  `app.test_client()` through a typed fixture. The old numbers were right in direction (many tests do call them) but were
  produced by name matching. Impact analysis is therefore now **conservative (under-reports)** for frameworks used through
  typed variables, and the Flask `blog.index` trace is short because `app.update_template_context(...)` is a call through the
  typed variable `app`. This is the main cost of the change.

## 4. Reproduce

From the repository root (Git Bash). Needs the existing Flask clone; nothing below touches Neo4j.

```bash
cd backend
# 1. tests
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider                       # expect 192 passed
# 2. labelled-sample metrics, AFTER (working tree)
.venv/Scripts/python.exe ../project_audit_2026_10_11/scripts/resolver_eval.py eval workspace/526e8042-1b3f-414e-9959-117464f02e02 ../project_audit_2026_10_11/resolver_eval/flask_sample_labelled.json
.venv/Scripts/python.exe ../project_audit_2026_10_11/scripts/resolver_eval.py eval workspace/526e8042-1b3f-414e-9959-117464f02e02 ../project_audit_2026_10_11/resolver_eval/flask_heldout_labelled.json
# 3. BEFORE = committed caf823d (extract it somewhere outside the repo, run the same script from there)
git -C .. archive caf823d backend | tar -x -C /tmp/before          # use any scratch dir
(cd /tmp/before/backend && <venv python> <abs>/project_audit_2026_10_11/scripts/resolver_eval.py eval <abs>/backend/workspace/526e8042-... <abs>/project_audit_2026_10_11/resolver_eval/flask_sample_labelled.json)
# 4. downstream metrics (run from each tree)
.venv/Scripts/python.exe ../project_audit_2026_10_11/scripts/downstream_offline.py workspace/526e8042-1b3f-414e-9959-117464f02e02
# 5. other repositories, counts only
.venv/Scripts/python.exe ../project_audit_2026_10_11/scripts/calls_summary.py workspace/<id>
```

Known limits of this evaluation: one repository; one annotator; labels made by reading source (semantic judgement for typed
receivers); the stand-in graph does not reproduce database ordering ties; Java/JS/TS/C++ changes were checked by unit tests and
count comparisons only, **not** by labelled precision/recall.

## 5. Housekeeping notes (Phase 2 commit)

* `after_result_v1.json` and `baseline_result.json` were deleted: both were produced before the call-site key
  normalisation fix and before the `abort` label correction (they report 1.0/0.80 and 0.692/0.720 on the old label), nothing
  referenced them, and `result_after_*.json` / `result_baselineHEAD_*.json` supersede them.
* `resolver_baseline_HEAD_caf823d.py` (a verbatim `git show` of the old resolver) was deleted: it is fully recoverable from
  commit `caf823d`, and scoring it with `--resolver-file` runs the OLD resolver on the NEW parser output, which is not a true
  baseline (it gave 0.703/0.693 instead of 0.692/0.720 on sample A before the label fix). The true baseline is always the
  extracted committed tree (`git archive caf823d backend`), as in section 4.
* All six result files cited above were regenerated from scratch at commit time and are byte-identical to the stored ones.
