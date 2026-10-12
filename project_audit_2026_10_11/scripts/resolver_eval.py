"""Resolver precision/recall harness (read-only: parses a cloned workspace, runs the CURRENT
parsing.ir.resolver, never touches Neo4j or the network).

Modes
  make-sample  Draw a stratified, seeded sample of CALLS call sites from a workspace and write a
               label skeleton (JSON) with the context needed to label each site by hand.
               Strata are defined by the BASELINE resolver output stored in the skeleton, so the
               same sample is reused unchanged for before/after comparison.
  eval         Score the current resolver against a labelled sample file.

Label semantics (field "label" in the sample file)
  "<qualified_name>"  the call's true target is this repository definition
  "EXTERNAL"          the true target is outside the repository (stdlib, third party, builtin,
                      dynamic object we cannot identify) -> the correct resolver output is "unresolved"

Metrics (per call site; a call site is keyed by (source_file, source_line, target_name))
  bound             the resolver returned a repository target
  correct           bound and target qualified_name == label
  precision         correct / bound
  recall            correct / (sites whose label is a repository definition)
  wrong_repo        bound to a repository definition different from the label
  bound_external    bound although label == EXTERNAL
Targets that are IMPORT symbols count as bound-but-wrong when the label is a definition, because a
call edge to an import statement does not reach the definition.

Usage (from backend/):
  python ../project_audit_2026_10_11/scripts/resolver_eval.py make-sample <workspace> <out.json> [--seed N]
  python ../project_audit_2026_10_11/scripts/resolver_eval.py eval <workspace> <labelled.json> [--json out.json]
"""
import argparse
import collections
import json
import linecache
import random
import sys
from pathlib import Path

sys.path.insert(0, ".")
from app.services.graph_pipeline import _parse_workspace  # noqa: E402
from parsing.ir.models import RelationshipType as RT  # noqa: E402
from parsing.ir.models import SymbolType  # noqa: E402
from parsing.ir.resolver import resolve_relationships  # noqa: E402

RESOLVER_OVERRIDE = None  # set by --resolver-file: path to an alternative resolver.py (e.g. from `git show HEAD:...`)


def _resolve(symbols, rels):
    if RESOLVER_OVERRIDE is None:
        return resolve_relationships(symbols, rels)
    import importlib.util
    spec = importlib.util.spec_from_file_location("alt_resolver", RESOLVER_OVERRIDE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.resolve_relationships(symbols, rels)


def _load(workspace: Path):
    pfs = _parse_workspace(workspace)
    symbols = [s for p in pfs for s in p.symbols]
    rels = [r for p in pfs for r in p.relationships]
    resolved = _resolve(symbols, rels)
    return symbols, rels, resolved


def _shape(target_name: str) -> str:
    if "." not in target_name:
        return "bare"
    head = target_name.split(".", 1)[0]
    return "self" if head in ("self", "cls", "this") else "recv.attr"


def _key(r) -> str:
    # The "?." marker (receiver is an expression) was introduced with the resolver change; samples
    # labelled before it recorded the bare attribute, so the marker is stripped to keep keys stable.
    name = r.target_name[2:] if r.target_name.startswith("?.") else r.target_name
    return f"{r.source_file}:{r.source_line}:{name}"


def _baseline_status(res, by_id) -> str:
    if res.target_id is None:
        return "unresolved"
    return "bound_import_node" if by_id[res.target_id].symbol_type == SymbolType.IMPORT else "bound_definition"


def make_sample(workspace: Path, out: Path, seed: int, by_shape: bool = False, exclude: Path | None = None) -> None:
    symbols, rels, resolved = _load(workspace)
    by_id = {s.id: s for s in symbols}
    short_index = collections.defaultdict(list)
    for s in symbols:
        if s.symbol_type in (SymbolType.CLASS, SymbolType.FUNCTION, SymbolType.METHOD):
            short_index[s.name].append(s.qualified_name)

    strata = collections.defaultdict(list)
    seen = set()
    if exclude is not None:
        seen |= {it["key"] for it in json.loads(exclude.read_text(encoding="utf-8"))["items"]}
    for raw, res in zip(rels, resolved):
        if raw.relationship_type != RT.CALLS:
            continue
        k = _key(raw)
        if k in seen:
            continue
        seen.add(k)
        status = _baseline_status(res, by_id)
        shape = _shape(raw.target_name)
        short = raw.target_name.rsplit(".", 1)[-1]
        has_cand = bool(short_index.get(short))
        if status == "unresolved":
            stratum = f"unresolved/{'has_candidate' if has_cand else 'no_candidate'}"
        elif status == "bound_import_node":
            stratum = "bound_import_node"
        else:
            stratum = f"bound_definition/{shape}"
        if by_shape:
            stratum = "chained(?.attr)" if raw.target_name.startswith("?.") else shape
        strata[stratum].append((raw, res))

    quotas = {
        "bound_definition/bare": 22, "bound_definition/recv.attr": 26, "bound_definition/self": 18,
        "bound_import_node": 14, "unresolved/has_candidate": 26, "unresolved/no_candidate": 14,
    }
    if by_shape:
        quotas = {"bare": 30, "self": 30, "recv.attr": 40, "chained(?.attr)": 20}
    rng = random.Random(seed)
    items = []
    for stratum, quota in quotas.items():
        pool = sorted(strata.get(stratum, []), key=lambda t: _key(t[0]))
        for raw, res in rng.sample(pool, min(quota, len(pool))):
            short = raw.target_name.rsplit(".", 1)[-1]
            ctx_before = [linecache.getline(str(workspace / raw.source_file), n).rstrip()
                          for n in range(max(1, raw.source_line - 3), raw.source_line)]
            items.append({
                "key": _key(raw), "stratum": stratum, "caller": raw.source_id,
                "source_file": raw.source_file, "source_line": raw.source_line,
                "target_name": raw.target_name,
                "line": linecache.getline(str(workspace / raw.source_file), raw.source_line).rstrip(),
                "context_before": ctx_before,
                "baseline_target": by_id[res.target_id].qualified_name if res.target_id else None,
                "baseline_confidence": res.confidence,
                "same_short_name_candidates": sorted(short_index.get(short, []))[:8],
                "label": None,
            })
    payload = {"seed": seed, "workspace_commit_note": "pin to the Flask commit recorded in the registry",
               "stratum_population": {k: len(v) for k, v in strata.items()}, "items": items}
    out.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"wrote {len(items)} items to {out}")
    print("population by stratum:", payload["stratum_population"])


def evaluate(workspace: Path, labelled: Path, json_out: Path | None) -> None:
    data = json.loads(labelled.read_text(encoding="utf-8"))
    symbols, rels, resolved = _load(workspace)
    by_id = {s.id: s for s in symbols}
    outcome = {}
    for raw, res in zip(rels, resolved):
        if raw.relationship_type == RT.CALLS:
            outcome.setdefault(_key(raw), res)

    rows = []
    for it in data["items"]:
        it["key"] = it["key"].replace(":?.", ":", 1)  # samples drawn after the parser change carry the marker
        if it["label"] is None:
            raise SystemExit(f"unlabelled item: {it['key']}")
        if it["key"] not in outcome:
            raise SystemExit(f"labelled call site not found in parse output (stale sample?): {it['key']}")
        res = outcome[it["key"]]
        target = by_id[res.target_id] if res is not None and res.target_id else None
        is_def = target is not None and target.symbol_type != SymbolType.IMPORT
        got = target.qualified_name if is_def else (f"IMPORT:{target.qualified_name}" if target else None)
        rows.append({**{k: it[k] for k in ("key", "stratum", "label")}, "got": got})

    def metrics(subset):
        has_def = [r for r in subset if r["label"] != "EXTERNAL"]
        bound = [r for r in subset if r["got"] is not None]
        correct = [r for r in subset if r["got"] == r["label"]]
        return {
            "n": len(subset), "label_is_repo_definition": len(has_def), "bound": len(bound), "correct": len(correct),
            "wrong_repo": sum(1 for r in bound if r["label"] != "EXTERNAL" and r["got"] != r["label"]),
            "bound_external": sum(1 for r in bound if r["label"] == "EXTERNAL"),
            "precision": round(len(correct) / len(bound), 3) if bound else None,
            "recall": round(len(correct) / len(has_def), 3) if has_def else None,
        }

    report = {"overall": metrics(rows), "by_baseline_stratum": {}}
    for st in sorted({r["stratum"] for r in rows}):
        report["by_baseline_stratum"][st] = metrics([r for r in rows if r["stratum"] == st])
    pop = data.get("stratum_population", {})
    # stratum-weighted population estimates (each stratum weighted by its population share)
    total = sum(pop.get(st, 0) for st in report["by_baseline_stratum"]) or 1
    w_correct = w_bound = w_has = 0.0
    for st, m in report["by_baseline_stratum"].items():
        w = pop.get(st, 0) / total
        if m["n"]:
            w_correct += w * m["correct"] / m["n"]
            w_bound += w * m["bound"] / m["n"]
            w_has += w * m["label_is_repo_definition"] / m["n"]
    report["stratum_weighted_estimate"] = {
        "precision": round(w_correct / w_bound, 3) if w_bound else None,
        "recall": round(w_correct / w_has, 3) if w_has else None,
        "note": "strata weighted by population share of the BASELINE resolver output; small-sample estimate",
    }
    report["resolved_calls_total_definition_targets"] = sum(
        1 for r in resolved if r.relationship_type == RT.CALLS and r.target_id
        and by_id[r.target_id].symbol_type != SymbolType.IMPORT)
    report["resolved_calls_total_import_targets"] = sum(
        1 for r in resolved if r.relationship_type == RT.CALLS and r.target_id
        and by_id[r.target_id].symbol_type == SymbolType.IMPORT)
    report["calls_total"] = sum(1 for r in rels if r.relationship_type == RT.CALLS)
    text = json.dumps(report, indent=1)
    print(text)
    if json_out:
        json_out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    a = sub.add_parser("make-sample")
    a.add_argument("workspace", type=Path)
    a.add_argument("out", type=Path)
    a.add_argument("--seed", type=int, default=20261012)
    a.add_argument("--by-shape", action="store_true", help="stratify by call shape (resolver-independent) for a held-out sample")
    a.add_argument("--exclude", type=Path, default=None, help="labelled sample whose call sites must not be re-drawn")
    b = sub.add_parser("eval")
    b.add_argument("workspace", type=Path)
    b.add_argument("labelled", type=Path)
    b.add_argument("--json", type=Path, default=None)
    b.add_argument("--resolver-file", type=Path, default=None, help="score an alternative resolver.py on the CURRENT parser output (NOT a true baseline; for a baseline run the script from an extracted `git archive` of the committed tree)")
    args = ap.parse_args()
    if args.mode == "make-sample":
        make_sample(args.workspace, args.out, args.seed, args.by_shape, args.exclude)
    else:
        RESOLVER_OVERRIDE = args.resolver_file
        evaluate(args.workspace, args.labelled, args.json)
