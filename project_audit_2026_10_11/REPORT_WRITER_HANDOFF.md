# REPORT_WRITER_HANDOFF.md — for the person writing the VIT Chennai BCSE497J report

Read this first; it is deliberately short on prose and long on "what you may and may not say". Everything here is traceable via `EVIDENCE_INDEX.md`. Audit date: 2026-10-11. Product name in documents: **CodeBase Archeologist** (the source tree and API still say "CodeSage" — pick one name and explain the rename once).

## 1. Verified project facts (safe to state)

* Pipeline: GitHub URL → validated, shallow, size-limited clone → Tree-sitter parse → common IR → name-based cross-file resolution → Neo4j graph + in-memory TF-IDF/FAISS index → on-demand analysis → React UI.
* Five parsers exist (Python, JavaScript, TypeScript, Java, C++), all emit the same IR; analysis code has no per-language branches (except small import/stdlib classifiers).
* Neo4j stores four relationship types (CONTAINS, IMPORTS, CALLS, INHERITS), each with source file, line and a numeric confidence.
* Architecture reconstruction, architecture analysis, optimization proposals, execution flow, impact/risk are **deterministic** (no LLM calls inside them). The LLM (Groq) is used only for Q&A and for narrating a verified graph path; if no path exists the system answers "not connected" without calling it.
* The optimization module only recommends; it never changes the analysed repository.
* Backend: **172 unit tests passing** on 2026-10-11 (0 failed/skipped). Frontend: TypeScript check and production build pass; 0 lint errors, 3 warnings.
* Flask case study (commit `d73fa1cd`): 236 files; 83 Python files; 2,654 symbols; 3,713 resolved relationships; 8 reconstructed components; 12 component relationships; 47 findings (severity 1 High / 17 Medium / 29 Low; confidence tiers 3 High / 21 Medium / 23 Low using thresholds 0.7/0.4); 5 optimization proposals; ingestion median ≈ 8.4 s over 50 runs.
* Execution-flow fix (separating `terminal_kind` from `terminal_reason`): present in the working tree, unit-tested, and `blog.index` grows from 3 to 16 nodes versus the committed code.

## 2. Modules — what exists

| Fully usable (backend + UI + unit tests) | Ingestion; Python parser; graph construction; architecture reconstruction; architecture analysis; optimization; execution flow; impact & risk; evidence explorer |
|---|---|
| Implemented but only lightly verified | JS/TS/Java/C++ parsers (unit tests; 1 real JS and 1 real Java ingest, TS and C++ none); Ask the Archeologist; relationship narration; Repository Overview |
| Partial | **Historical Reconstruction** — per-component commit counts, first/last dates, top authors only |
| Absent | Architecture snapshots over time, rename tracking, "why" reasoning, incremental analysis, authentication, golden-repository fixtures, ADRs, relational DB |

Be precise in the abstract: do not write that the system "reconstructs architecture evolution"; write that it "summarises per-component commit history".

## 3. Remaining or partially implemented modules (for the "Future work" chapter)

Historical Reconstruction (snapshots, renames, rationale); import-/scope-aware resolution; persisted vector index; retries/caching; integration + frontend tests; real-repo validation for TS/C++; comparison study; calibration of thresholds; commit and tidy documentation.

## 4. Metric definitions you must carry into the report

| Term | Exact meaning in this project |
|---|---|
| Symbol | file, class, function, method or import extracted into the IR (imports count as symbols: 949 of Flask's 2,654) |
| Resolved relationship | an IR relationship whose target was bound to a repository symbol (3,713 for Flask, including 1,622 CONTAINS and 949 IMPORTS); not "3,713 calls" |
| Resolved CALLS | 1,072 of 3,350 call sites (32 %) — the rest are mostly external/dynamic or ambiguous, not necessarily errors |
| Resolver confidence | rule output: 0.95 exact qualified name; 0.75 unique short name; 0.3 ambiguous; ≤0.35 unresolved. **Not** a probability |
| Severity | magnitude of the observed condition (thresholds in code) |
| Finding confidence | 0–1 blend of base value, resolver confidence and context discounts; **tiers (High ≥0.7, Medium ≥0.4) are a frontend convention**; the Confirmed/Inferred/Uncertain labels use different thresholds (0.75/0.4) for components and (0.55/0.30) for Q&A |
| Trace nodes | tree nodes in the OBSERVED flow including the entry function; a flow stops at NO_RESOLVED_CALLEES / STANDARD_LIBRARY / EXTERNAL_DEPENDENCY / UNRESOLVED / DEPTH_LIMIT (5) / BRANCH_LIMIT (150 total, 3 per hop) |
| Risk level | LOW <3, MEDIUM 3–4, HIGH 5–7, CRITICAL ≥8 points from named signals |

## 5. Existing research and literature sources

**None are stored in the repository** (no bibliography file, no research directory, no related-work notes). `CLAUDE.md` §46 lists research *topics* (architecture reconstruction from repository artefacts; graph-based program representation; temporal code knowledge graphs; evidence-aware LLM reasoning; static+semantic hybrid analysis; change-impact analysis; architecture-violation detection) but cites no papers. You must collect and verify references yourself. Suggested search areas (not citations): software architecture recovery/reconstruction; call-graph construction precision (name-based vs type-based); code knowledge graphs; retrieval-augmented generation for code; code smell detection (god class, cyclic dependency); change impact analysis; Tree-sitter; tools to position against (Sourcegraph, CodeQL, Understand, Structure101, GitHub Copilot) — cite their official documentation, not marketing claims. No bibliographic metadata was invented in this audit.

## 6. Figures / screenshots available

* **Screenshots: none.** No screenshot or recording exists in the repo (`frontend/src/assets/hero.png` is not a screenshot) and none were taken in the audit. Capture them yourself from a running instance (backend `uvicorn`, frontend `npm run dev`) for: submission form + pipeline progress; Architecture tab for Flask; Execution flow (all three views); Evidence explorer with a relationship investigation; Architecture Analysis list + inspector; Optimization; Impact; History; Ask.
* **Diagrams ready to adapt:** the Mermaid diagrams in `ARCHITECTURE_AND_DATA_FLOW.md` (system, ingestion sequence, graph schema, analysis dependencies, Q&A flow) and the README's workflow chart (the README flow section predates the terminal-reason change).
* **Tables ready to use:** `IMPLEMENTATION_MATRIX.csv`, test-count table (`TEST_RESULTS.md` §1.1), Flask metrics (`METRICS_AND_RESULTS.md` §2–§6).

## 7. Recommended chapter structure (mapped to BCSE497J headings)

1. **Abstract** – problem, deterministic-evidence approach, five-language pipeline, Flask case study numbers, honest scope sentence.
2. **Introduction & objectives** – onboarding/archaeology motivation; objectives from §3 of the evidence report.
3. **Background & literature review** – (you supply) architecture recovery, call-graph construction, code KGs, RAG, smell detection; related tools.
4. **Problem statement & research gap** – LLM-only code chat vs evidence-grounded reconstruction. State the gap as an *aim* of the design; do not claim novelty without literature support.
5. **Proposed methodology** – evidence → reconstruction → analysis → explanation; confidence model; the "OBSERVED / INFERRED / PROPOSED" labelling (`CLAUDE.md` §37).
6. **System architecture & design** – layers, data flow, graph schema, API (use `ARCHITECTURE_AND_DATA_FLOW.md`).
7. **Implementation** – parsers/IR, resolver, graph loader, each engine, retrieval + prompt boundary, frontend views.
8. **Testing & evaluation** – test pyramid as it is (172 unit tests; no integration/UI tests), live Flask probes, the reproduced claims, the resolver-precision finding.
9. **Results & discussion** – Flask tables; discuss limitations frankly (resolver precision; role heuristics fit Flask poorly; 8/15 spurious hops in the 16-node trace).
10. **Conclusion & future work** – §16 of the evidence report.
11. **References (APA)** – your verified sources only.
12. **Appendices** – matrix CSV, test list, scripts, sample JSON outputs, API table.

## 8. Technical explanations worth including

* Why Tree-sitter (error-tolerant, multi-language grammars) and why a common IR (analysis written once).
* Why resolution is hard: parsers see one file; the resolver sees the symbol table but no types — hence confidence values and the "ambiguous ⇒ not an edge" rule.
* Severity vs confidence (independent axes; show the severity × tier table from `METRICS_AND_RESULTS.md` §4).
* `terminal_kind` vs `terminal_reason`: the bug was using an architecture *role* as a stop condition, so a trace ended at the first `external_integration` node (Flask's own `render_template` lives in such a component). Now role is only a badge; the reason a branch ended is recorded separately.
* Static-flow honesty: dynamic dispatch, decorators, dependency injection and name collisions are invisible; PROPOSED flows are projections, never traces.
* Prompt-boundary design (system / question / evidence) and the "no path ⇒ no LLM call" rule.

## 9. Claims that must NOT be made

* That 16 nodes is 16 correct hops, or that the fix "improved accuracy" (there is no accuracy measurement; 8 of 15 hops in that trace come from a false resolution).
* That the system is more accurate, faster or better than Sourcegraph, Copilot or any tool; that it is "novel", "the first" or "state of the art" (no literature review or comparison exists).
* That the architecture reconstruction is "correct" or "recovers the true architecture" (no ground truth; Flask's core is labelled `external_integration`).
* That the vector search is "semantic" or uses neural embeddings (it is TF-IDF).
* That the retrieval is "graph-first hybrid" (it is vector search plus one-hop graph context).
* That Historical Reconstruction reconstructs architectural evolution, or explains developer intent.
* That confidence values are calibrated probabilities.
* That all five languages are validated on real repositories (TS and C++ are unit-tested only).
* That the UI has been tested (no browser tests exist; none were run).
* That the LLM "never hallucinates" — only that structural facts are computed without it and the prompt restricts it to supplied evidence (not tested adversarially).
* That the system is secure for public deployment (no authentication, rate limiting, or adversarial testing).
* The older figures "26 tests", "2,651 symbols", "3,707 relationships", "42 findings" (superseded); and the 132/139 test counts (superseded by 172 — quote 172 with the date).
* That test counts or results refer to a committed version: they describe the uncommitted working tree.

## 10. Information only the student/supervisor can provide

Student names, register numbers, programme/branch; guide/supervisor name, designation, department, school; panel members; project title as approved; certificate/declaration/acknowledgement text and signatures; plagiarism/similarity report; dates (review dates, submission date); abstract word limits and formatting rules from the supplied template; whether a user study or comparison with other tools is expected and approved; ethical/consent requirements for any user study; which literature the guide expects to see; GitHub repository URL/licence to cite; any datasets or repositories the guide wants used besides Flask; whether the Neo4j/Groq cloud accounts may be referenced in the report.

## 11. Checklist of outstanding validation tasks (ordered by value for the report)

- [ ] Commit (or at least tag) the working tree so the reported results correspond to a stable version.
- [ ] Fix or at least quantify resolver false positives (hand-label ~100 sampled CALLS edges from Flask; report precision per confidence band).
- [ ] Build 2–3 small golden repositories with a known architecture/flow and compare expected vs actual (`CLAUDE.md` §33/§48).
- [ ] Run Ask the Archeologist on Flask (needs re-ingest to rebuild the in-memory index) and record 10–20 questions with answers, cited evidence and your own correctness judgement.
- [ ] Run `GET /history` on Flask and record outputs (note: it fetches more commits into the clone).
- [ ] Walk the UI end to end in a browser and capture screenshots; verify navigation between tabs ("investigate" actions) and the three flow views.
- [ ] Ingest one real TypeScript and one real C++ repository; inspect outputs.
- [ ] Repeat Flask ingestion + analysis a few times and report variability in timings (counts are already stable).
- [ ] Define and run a comparison experiment against at least one existing tool, or state in the report that none was done.
- [ ] Add integration tests (Neo4j + API) and at least smoke tests for the frontend.
- [ ] Address the `RepositoryOverview.tsx:27` effect warning; update README (flow-termination text) and retire/refresh `docs/ROADMAP.md` and `docs/PRESENTATION_PROMPT.md`.
- [ ] Decide on and document a data-retention approach for cloned repositories and Neo4j subgraphs (50 Flask subgraphs may exist in Aura).
