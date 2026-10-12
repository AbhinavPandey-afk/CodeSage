# Phase 3 — conservative typed-receiver resolution: measured results

Baselines: **original** = commit `caf823d` (unique-short-name resolver); **Phase 2** = commit `a10e450` (scope-evidence resolver);
**Phase 3** = working tree on top of `a10e450` (uncommitted). Workspaces: existing Flask clone (`d73fa1cd`) and Spring PetClinic clone.
Nothing here touched Neo4j; downstream numbers come from the in-memory stand-in (`scripts/downstream_offline.py`, validated against the live
database in `RESULTS.md` §3). Date: 2026-10-12.

## 1. What was implemented

* `Symbol.declared_types: dict[str, str]` (in-memory only, never persisted): parameters/locals on FUNCTION/METHOD symbols, fields on CLASS
  symbols, module-level variables on FILE symbols (Python). Values: `"Foo"` declared, `"new:Foo"` single constructor assignment, `"def"` nested
  def/class/local import, `"?"` bound with no usable or with conflicting types (lookups stop there; no fall-through to outer variables).
* Python parser: annotated parameters / locals / `self.x: T` / class-level annotations / module-level annotated variables; `x = Foo(...)` /
  `x = mod.Foo(...)` only when the name has a single binding site in the function; `Optional[T]` and `T | None` unwrapped; unions, generics
  and `Any` rejected. Call targets of the form `self.f.m()` / `cls.f.m()` are now kept (previously `?.m`).
* Java parser: typed parameters, locals, fields, enhanced-for and try-with-resources variables, `catch (T e)`, typed lambda parameters,
  `var x = new T()`; untyped lambda parameters and locals that shadow a field are recorded as `?`; generic arguments dropped
  (`Page<Owner>` → `Page`); the declared `package` is recorded on the FILE symbol (`bound_path`).
* Resolver: a receiver variable is looked up through enclosing function scopes, class fields (Java; Python only via `self.f`) and module
  variables, including module variables reached through imports (`from flask.globals import current_app`). Its type must resolve — through
  the existing lexical / import / alias / re-export rules — to exactly one repository **class** that has the method (itself or a resolved base).
  `new Box<>()` is normalised to `Box`. Java same-package visibility now uses the declared package (spans `src/main` and `src/test`).
* Confidence (rule scores, not probabilities): 0.85 declared type; 0.80 constructor-inferred; −0.05 when the method is inherited.
* No short-name fallback exists anywhere (`test_no_short_name_fallback_was_reintroduced`).

## 2. Precision / recall on the labelled samples

TP = bound to the labelled target. FP = bound but wrong (wrong repository target, or bound although the label is EXTERNAL).
FN = labelled repository target not produced (unresolved or wrong). Precision = TP/(TP+FP); recall = TP/(TP+FN).

| Sample | Sites (repo-labelled) | Resolver | TP | FP | FN | Precision | Recall |
|---|---:|---|---:|---:|---:|---:|---:|
| Flask A (labelled before Phase 2) | 117 (74) | original | 53 | 25 | 21 | 0.679 | 0.716 |
| | | Phase 2 | 60 | 0 | 14 | 1.000 | 0.811 |
| | | **Phase 3** | **64** | **0** | **10** | **1.000** | **0.865** |
| Flask B (held out) | 116 (59) | original | 35 | 10 | 24 | 0.778 | 0.593 |
| | | Phase 2 | 41 | 0 | 18 | 1.000 | 0.695 |
| | | **Phase 3** | **47** | **0** | **12** | **1.000** | **0.797** |
| Java P1 (frozen before implementation) | 40 (10) | original | 9 | 0 | 1 | 1.000 | 0.900 |
| | | Phase 2 | 6 | 0 | 4 | 1.000 | 0.600 |
| | | **Phase 3** | **9** | **0** | **1** | **1.000** | **0.900** |
| Java P2 (frozen supplement, calls with a same-named repo method) | 19 (17) | original | 16 | 0 | 1 | 1.000 | 0.941 |
| | | Phase 2 | 5 | 0 | 12 | 1.000 | 0.294 |
| | | **Phase 3** | **17** | **0** | **0** | **1.000** | **1.000** |
| Java P3 (fresh, labelled blind, after tuning on P1/P2) | 18 (16) | original | 15 | 0 | 1 | 1.000 | 0.938 |
| | | Phase 2 | 4 | 0 | 12 | 1.000 | 0.250 |
| | | **Phase 3** | **14** | **0** | **2** | **1.000** | **0.875** |

How to read this:
* Samples are small and single-annotator. They show results **on these samples**, not that precision is 1.00 in general; with 47–64 bound
  sites a 95 % lower bound on true precision is roughly 0.94–0.95 (rule of three).
* P1 and P2 were frozen (labels + SHA-256 in `FROZEN_java_samples.txt`) **before** any typed-receiver code was written. After the first
  Phase 3 run, the misses on them exposed a real defect (Java same-package visibility used the directory, but a package spans
  `src/main/java` and `src/test/java`), which I fixed; P1/P2 are therefore no longer an unbiased test. **P3** was drawn afterwards
  (different seed, P1/P2 excluded) and labelled with no resolver output visible; it is the cleaner Java generalisation check.
* On PetClinic the original unique-short-name resolver was already precise (its names are mostly unique); Phase 2's drop was pure recall
  loss. Phase 3 recovers it **with evidence** and keeps FP = 0. It does not beat the original on Java recall (equal on P1, higher on P2, lower on P3).
* Flask labels were not changed in Phase 3 (the single Phase-2-review correction of the `abort` label stands).
* Remaining Flask FNs (A: 10, B: 12): unannotated pytest fixture parameters (`app`, `client`, `auth` — no type evidence exists), attribute
  chains from variables (`app.config.from_object`, `ctx.app.redirect`), `super().__init__`, and genuinely ambiguous definitions.
  Remaining Java FNs: three same-named `Owner.getPet` overloads (a call to an overloaded method is intentionally left ambiguous), and
  return-type chains (`george.getPet("Max").getVisits()`).

## 3. Review of newly resolved edges (not in any labelled sample)

Random samples of edges bound by Phase 3 but not by Phase 2, judged by reading the source line and the receiver's declaration:

| Repository | New edges | Reviewed | Judged correct | Notes |
|---|---:|---:|---:|---|
| Flask | 115 | 45 | 45 | `app = flask.Flask(..)` → `app.test_client()`; `current_app: Flask`; `g: _AppCtxGlobals` → `g.pop`; `self.session_interface: SessionInterface` |
| Spring PetClinic | 223 | 45 | 45 | typed locals/params/fields; inherited `getName/setId`; constructors; `this.petTypeFormatter.print` |
| requests (no labels) | 166 | 36 | 36 | `s = requests.Session()` → `send/mount/get`; `RequestsCookieJar.set`; inherited `register_hook` |

Files: `phase3_{flask,java,requests}_new_edges_review_sample.json`. These are my judgements (single reviewer). Static-type binding is by
the **declared** type: a call on a variable declared as a base type is bound to the base-class method even if a subclass overrides it at runtime.

## 4. Downstream effects (Flask, offline stand-in; original → Phase 2 → Phase 3)

| Metric | Original | Phase 2 | Phase 3 |
|---|---:|---:|---:|
| CALLS edges (resolved) | 1,071 (239 end at an import statement) | 739 (0) | 854 (0) |
| Resolved-call confidence values | 0.75 ×832, 0.95 ×239 | 0.90 ×456, 0.95 ×245, 0.85 ×38 | adds 0.85 ×14, 0.80 ×60, 0.75 ×41 |
| Architecture components / relationships | 8 / 12 | 8 / 6 | 8 / 6 (cross-component call counts 380→470 on the largest edge) |
| Findings | 47 (1/17/29) | 41 (0/12/29) | 41 (0/12/29) |
| Optimization proposals | 5 | 1 | 1 |
| `blog.update` incoming CALLS / impact | 30 / CRITICAL | 1 / LOW | 1 / LOW |
| `Flask.test_client` impact | 45 direct, HIGH (6) | 0, LOW | 27 direct, 27 tests, HIGH (6) |
| `Flask.test_request_context` impact | 32 direct, HIGH (7) | 0, LOW | 8 direct, MEDIUM (3) |
| `blog.index` trace (nodes) | 13 in the stand-in (16 live), 4 of them spurious | 4 | 4 |
| Flow sizes, 20 entry points | 1×11,2,6,8,12,12,13,15,15,15 | 1×10,2,3,3,3,4,4,4,4,5,5 | 1×10,2,3,3,4,4,5,5,8,9,9 |

Explanations:
* **Findings and proposals unchanged at 41 / 1**: the 6 findings and 4 proposals that disappeared in Phase 2 did not come back. The new
  edges are tests → library calls and library-internal calls through typed members; they created no new cycle or layering violation.
  (I did not verify one by one whether the original 6 were true cycles.)
* **`blog.index` stays at 4 nodes**: its remaining branch (`_render` → `app.update_template_context`) goes through `app = ctx.app`, an
  attribute chain from a variable — unsupported by design, so the trace is short and its stop reason is `UNRESOLVED`, shown honestly.
* **Larger flows are real, not an artefact**: e.g. `auth.login` (9 nodes) now continues `url_for → current_app.url_for (Flask.url_for) →
  create_url_adapter / inject_url_defaults / handle_url_build_error`, each hop a genuine static call (module variable `current_app: Flask`, `self.` calls).
  The old 13–16-node trace was the opposite: eight of its hops came from the false `dict.update → blog.update` binding.
* **Impact is still an under-estimate** for `Flask.test_client` (27 vs the original 45): the missing dependents call it through unannotated pytest fixtures.
  Longer traces, more edges and higher impact are not improvements by themselves; the improvements are the edges whose evidence was checked above.
* Java (`calls_summary.py`): definition-bound calls 282 (original) → 61 (Phase 2) → **284** (Phase 3); ambiguous calls 59 → 2 → 16 (overload sets stay ambiguous).
  Other repositories (definition-bound calls, original → Phase 2 → Phase 3): requests 930 → 742 → 908; jinja 2,704 → 1,760 → 2,093; black 2,060 → 1,804 → 1,966;
  hackathon-starter (JS) 130 → 131 → 131 (no JS/TS/C++ type support was added); Flask 833 → 739 → 854. Resolution still takes < 0.1 s per repository.

## 5. Known limitations

* Types come only from annotations, declarations and single constructor assignments. Not handled: pytest fixtures and any other untyped
  parameter, return types and call chains (`a.b().c()`), attribute chains from variables (`x.f.m()` — only `self.`/`this.`-rooted fields), type
  aliases, generics' type arguments (`list[Foo]` elements), `super()`, tuple unpacking, flow-sensitive narrowing (`isinstance`), reassigned
  variables (left unresolved on purpose), JS/TS/C++ (parsers unchanged; only the Python and Java parsers emit `declared_types`).
* Constructor inference is flow-insensitive and trusts a name only when it has one binding site; the 0.80 score reflects that.
* Calls to overloaded Java methods stay ambiguous (the IR cannot tell overloads apart; they share one qualified name).
* A variable declared with a base type is bound to the base method (static semantics), not to a runtime override.
* Python class bodies are not visible to methods; function-scope shadowing is modelled, loop/with/except/comprehension bindings count as unknown.
* The evaluation is small, single-annotator, and on three repositories (two labelled).

## 6. Reproduce (from `backend/`, Git Bash; nothing touches Neo4j)

```bash
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider                                   # 212 passed
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_cpp_parser.py tests/test_java_parser.py tests/test_javascript_parser.py tests/test_python_parser.py tests/test_typescript_parser.py   # 44 passed
F=workspace/526e8042-1b3f-414e-9959-117464f02e02; J=$(ls -d workspace/46ac61a0*); E=../project_audit_2026_10_11
for s in sample heldout; do .venv/Scripts/python.exe $E/scripts/resolver_eval.py eval $F $E/resolver_eval/flask_${s}_labelled.json; done
for s in java_petclinic java_petclinic_supplement java_petclinic_p3; do .venv/Scripts/python.exe $E/scripts/resolver_eval.py eval $J $E/resolver_eval/${s}_labelled.json; done
.venv/Scripts/python.exe $E/scripts/downstream_offline.py $F
```
"Original" and "Phase 2" rows: run the same scripts from an extracted tree (`git archive caf823d backend` / `git archive a10e450 backend`
into a scratch directory, then `cd <scratch>/backend` and call the scripts by absolute path). Check the frozen labels with
`sha256sum java_petclinic*_labelled.json` against `FROZEN_java_samples.txt`.
