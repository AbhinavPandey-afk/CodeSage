"""Offline downstream metrics: runs the REAL analysis engines (architecture reconstruction, smell
detection, optimization, execution flow, impact) against an IN-MEMORY stand-in for Neo4j that is
built from the code tree found on sys.path (cwd) -- its parsers + resolver -- applied to a cloned
workspace. Nothing connects to Neo4j or the network; nothing is written anywhere except stdout/--out.

Why: lets the resolver change be evaluated end to end without touching the user's Neo4j database.
Validity check: run it from a checkout of the COMMITTED code and compare with the live-database
numbers recorded in the earlier audit (47 findings; blog.index 16 nodes); see the report.

The fake mirrors graph/loader.py semantics: one node per symbol uid; edges written only for resolved
relationships; MERGE on (source, target, type, source_line); `unresolved_call_targets` on callers.
Only the specific read queries issued by the engines are implemented (matched by distinctive text).

Usage (from a backend/ directory):  python <this file> <workspace> [--out result.json]
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from app.services.graph_pipeline import _parse_workspace  # noqa: E402
from parsing.ir.models import RelationshipType as RT  # noqa: E402
from parsing.ir.models import SymbolType  # noqa: E402
from parsing.ir.resolver import resolve_relationships  # noqa: E402

REPO = "R"


class FakeGraph:
    def __init__(self, workspace: Path):
        pfs = _parse_workspace(workspace)
        symbols = [s for p in pfs for s in p.symbols]
        rels = [r for p in pfs for r in p.relationships]
        resolved = resolve_relationships(symbols, rels)
        self.nodes: dict[str, dict] = {}
        for s in symbols:
            uid = f"{REPO}:{s.id}"
            self.nodes[uid] = {
                "uid": uid, "id": s.id, "repo_id": REPO, "symbol_type": s.symbol_type.value, "name": s.name,
                "qualified_name": s.qualified_name, "file_path": s.file_path, "start_line": s.start_line,
                "end_line": s.end_line, "language": s.language.value, "decorators": s.decorators,
                "docstring": s.docstring, "unresolved_call_targets": None,
            }
        self.edges: dict[tuple, dict] = {}
        unresolved = collections.defaultdict(list)
        for r in resolved:
            if r.target_id is None:
                if r.relationship_type == RT.CALLS:
                    unresolved[f"{REPO}:{r.source_id}"].append(r.target_name)
                continue
            key = (f"{REPO}:{r.source_id}", f"{REPO}:{r.target_id}", r.relationship_type.value.upper(), r.source_line)
            self.edges[key] = {"src": key[0], "dst": key[1], "type": key[2], "source_file": r.source_file,
                               "source_line": r.source_line, "confidence": r.confidence}
        for uid, targets in unresolved.items():
            self.nodes[uid]["unresolved_call_targets"] = targets
        self.out = collections.defaultdict(list)
        self.inc = collections.defaultdict(list)
        for e in self.edges.values():
            self.out[e["src"]].append(e)
            self.inc[e["dst"]].append(e)
        self.calls = [e for e in self.edges.values() if e["type"] == "CALLS"]
        self.file_nodes = [n for n in self.nodes.values() if n["symbol_type"] == "file"]

    def degree(self, uid, types=None):
        total = 0
        for e in self.out.get(uid, []) + self.inc.get(uid, []):
            if types is None or e["type"] in types:
                total += 1
        return total


class _Result:
    def __init__(self, rows): self._rows = rows
    def data(self): return self._rows
    def single(self): return self._rows[0] if self._rows else None


class _Session:
    def __init__(self, g): self.g = g
    def __enter__(self): return self
    def __exit__(self, *a): return False

    def run(self, q, **p):
        g = self.g
        N = g.nodes
        if "MATCH (f:File {repo_id: $repo_id}) RETURN f.file_path AS file_path" in q:
            return _Result([{"file_path": n["file_path"]} for n in g.file_nodes])
        if "WHERE s.symbol_type IN ['class', 'function', 'method'] RETURN s.file_path AS file_path" in q:
            return _Result([{"file_path": n["file_path"], "qualified_name": n["qualified_name"], "symbol_type": n["symbol_type"],
                             "decorators": n["decorators"]} for n in N.values() if n["symbol_type"] in ("class", "function", "method")])
        if "symbol_type: 'import', file_path: $file_path" in q:
            return _Result([{"dotted": d} for d in dict.fromkeys(n["name"] for n in N.values()
                            if n["symbol_type"] == "import" and n["file_path"] == p["file_path"])])
        if "symbol_type: 'import'}) RETURN s.file_path AS file_path, s.name AS dotted" in q:
            return _Result([{"file_path": n["file_path"], "dotted": n["name"]} for n in N.values() if n["symbol_type"] == "import"])
        if "a.file_path <> b.file_path" in q:
            return _Result([{"src_file": N[e["src"]]["file_path"], "dst_file": N[e["dst"]]["file_path"], "confidence": e["confidence"],
                             "source_file": e["source_file"], "source_line": e["source_line"]}
                            for e in g.calls if N[e["src"]]["file_path"] != N[e["dst"]]["file_path"]])
        if "a.uid AS src, b.uid AS dst, a.qualified_name AS src_name" in q:
            return _Result([{"src": e["src"], "dst": e["dst"], "src_name": N[e["src"]]["qualified_name"], "src_file": N[e["src"]]["file_path"],
                             "src_line": N[e["src"]]["start_line"], "src_end": N[e["src"]]["end_line"], "rel_file": e["source_file"],
                             "rel_line": e["source_line"], "rel_confidence": e["confidence"]} for e in g.calls])
        if "a.uid AS src, b.uid AS dst, r.confidence AS confidence" in q:
            return _Result([{"src": e["src"], "dst": e["dst"], "confidence": e["confidence"], "source_file": e["source_file"],
                             "source_line": e["source_line"]} for e in g.calls])
        if "(c:Class {repo_id: $repo_id})-[:CONTAINS]->(m:Method)" in q:
            counts = collections.Counter(e["src"] for e in g.edges.values() if e["type"] == "CONTAINS"
                                         and N[e["src"]]["symbol_type"] == "class" and N[e["dst"]]["symbol_type"] == "method")
            rows = [{"qname": N[u]["qualified_name"], "file_path": N[u]["file_path"], "start_line": N[u]["start_line"],
                     "end_line": N[u]["end_line"], "method_count": c} for u, c in counts.items() if c >= p["min_methods"]]
            return _Result(sorted(rows, key=lambda r: -r["method_count"]))
        if "AND (s.end_line - s.start_line) >= $min_lines" in q:
            rows = [{"qname": n["qualified_name"], "file_path": n["file_path"], "start_line": n["start_line"], "end_line": n["end_line"],
                     "line_count": n["end_line"] - n["start_line"]} for n in N.values()
                    if n["symbol_type"] in ("function", "method") and n["end_line"] - n["start_line"] >= p["min_lines"]]
            return _Result(sorted(rows, key=lambda r: -r["line_count"]))
        if "NOT EXISTS { MATCH ()-[:CALLS]->(s) }" in q:
            called = {e["dst"] for e in g.calls}
            rows = [{"qname": n["qualified_name"], "file_path": n["file_path"], "start_line": n["start_line"], "end_line": n["end_line"]}
                    for n in N.values() if n["symbol_type"] in ("function", "method") and not n["name"].startswith("__")
                    and not n["name"].startswith("test_") and len(n["decorators"]) == 0 and n["uid"] not in called]
            return _Result(rows[: p["limit"]])  # live query has no ORDER BY: which 20 is arbitrary there too
        if "size(s.decorators) > 0 RETURN s.uid AS uid" in q:
            return _Result([{"uid": n["uid"], "qualified_name": n["qualified_name"], "file_path": n["file_path"],
                             "start_line": n["start_line"], "decorators": n["decorators"]} for n in N.values()
                            if n["symbol_type"] in ("function", "method") and len(n["decorators"]) > 0])
        if "s.unresolved_call_targets AS unresolved_call_targets" in q:
            return _Result([{"uid": n["uid"], "qualified_name": n["qualified_name"], "file_path": n["file_path"], "language": n["language"],
                             "unresolved_call_targets": n["unresolved_call_targets"]} for n in N.values() if n["symbol_type"] in ("function", "method")])
        if "RETURN s.start_line AS start_line, s.decorators AS decorators" in q:
            n = N.get(p["uid"])
            return _Result([{"start_line": n["start_line"], "decorators": n["decorators"]}] if n else [])
        if "OPTIONAL MATCH (t)-[r]-()" in q:
            n = N.get(p["uid"])
            if not n:
                return _Result([])
            deg = g.degree(n["uid"]) + (1 if n["symbol_type"] == "file" else 0)  # Repository-[:CONTAINS]->File
            return _Result([{"qualified_name": n["qualified_name"], "symbol_type": n["symbol_type"], "file_path": n["file_path"],
                             "decorators": n["decorators"], "degree": deg}])
        if "-[:CALLS|INHERITS*1.." in q:
            maxd = int(q.split("*1..")[1].split("]")[0])
            depth, frontier, level = {}, [p["uid"]], 0
            seen_levels = {}
            while frontier and level < maxd:
                level += 1
                nxt = []
                for u in frontier:
                    for e in g.inc.get(u, []):
                        if e["type"] in ("CALLS", "INHERITS") and e["src"] not in depth:
                            depth[e["src"]] = level
                            nxt.append(e["src"])
                frontier = nxt
            rows = [{"uid": u, "symbol_type": N[u]["symbol_type"], "name": N[u]["name"], "qualified_name": N[u]["qualified_name"],
                     "file_path": N[u]["file_path"], "start_line": N[u]["start_line"], "end_line": N[u]["end_line"],
                     "decorators": N[u]["decorators"], "depth": d} for u, d in depth.items()]
            return _Result(sorted(rows, key=lambda r: (r["depth"], r["qualified_name"])))
        if "OPTIONAL MATCH (s)-[r:CALLS|INHERITS]-()" in q:
            files = set(p["files"])
            cands = [n for n in N.values() if n["symbol_type"] in ("class", "function", "method") and n["file_path"] in files]
            if not cands:
                return _Result([])
            best = max(cands, key=lambda n: g.degree(n["uid"], ("CALLS", "INHERITS")))
            return _Result([{"uid": best["uid"]}])
        raise NotImplementedError(f"fake graph has no handler for query: {q[:120]}")


class FakeDriver:
    def __init__(self, g): self.g = g
    def session(self): return _Session(self.g)


def install(g):
    import analysis.execution_flow.engine as flow
    import analysis.impact.engine as impact
    import analysis.optimization.engine as opt
    import analysis.reconstruction.engine as recon
    import analysis.smells.detector as det
    drv = FakeDriver(g)
    for mod in (flow, impact, opt, recon, det):
        mod.get_driver = lambda drv=drv: drv


def tree_nodes(h):
    return 1 + sum(tree_nodes(c) for c in h.children)


def leaves(h, acc):
    if not h.children:
        acc[h.terminal_reason or "none"] += 1
    for c in h.children:
        leaves(c, acc)
    return acc


def dump(h, d=0, out=None):
    out = [] if out is None else out
    out.append("  " * d + f"{h.callee_qualified_name} [conf={h.confidence:.2f} stop={h.terminal_reason}]")
    for c in h.children:
        dump(c, d + 1, out)
    return out


def main(workspace: Path, out_path: Path | None):
    g = FakeGraph(workspace)
    install(g)
    from analysis.execution_flow.engine import detect_entry_points, reconstruct_execution_flow
    from analysis.impact.engine import analyze_impact
    from analysis.optimization.engine import generate_optimization_report
    from analysis.reconstruction.engine import reconstruct_architecture
    from analysis.smells.detector import run_smell_detection

    res = {"graph": {"symbol_nodes": len(g.nodes), "edges_by_type": dict(collections.Counter(e["type"] for e in g.edges.values())),
                     "calls_confidence": dict(collections.Counter(round(e["confidence"], 2) for e in g.calls)),
                     "calls_to_import_nodes": sum(1 for e in g.calls if g.nodes[e["dst"]]["symbol_type"] == "import")}}
    arch = reconstruct_architecture(REPO)
    res["architecture"] = {"components": len(arch.components), "relationships": len(arch.relationships),
                           "roles": dict(collections.Counter(c.role for c in arch.components)),
                           "relationship_call_counts": sorted((r.call_count for r in arch.relationships), reverse=True)}
    smells = run_smell_detection(REPO)
    tier = lambda c: "High" if c >= 0.7 else "Medium" if c >= 0.4 else "Low"  # frontend analysisModel.ts thresholds
    res["findings"] = {"total": len(smells), "severity": dict(collections.Counter(s.severity for s in smells)),
                       "confidence_tier_0.7_0.4": dict(collections.Counter(tier(s.confidence) for s in smells)),
                       "by_type": dict(collections.Counter(s.smell_type for s in smells))}
    opt = generate_optimization_report(REPO)
    res["optimization"] = {"proposals": len(opt.proposals), "by_risk": dict(collections.Counter(p.risk_level for p in opt.proposals))}
    eps = detect_entry_points(REPO, limit=20)
    flows = []
    for e in eps:
        rep = reconstruct_execution_flow(REPO, e.uid)
        flows.append({"entry": e.qualified_name, "nodes": tree_nodes(rep.observed), "leaf_reasons": dict(leaves(rep.observed, collections.Counter())),
                      "has_proposed": rep.proposed is not None})
    res["flows"] = flows
    res["flow_size_distribution"] = sorted(f["nodes"] for f in flows)
    wanted = {e.qualified_name: e for e in eps}
    blog = next((e for q, e in wanted.items() if q.endswith("flaskr.blog.index")), None)
    if blog is not None:
        res["blog_index_tree"] = dump(reconstruct_execution_flow(REPO, blog.uid).observed)
    impacts = []
    for suffix in ("src.flask.app.Flask.test_client", "src.flask.app.Flask.test_request_context", "examples.tutorial.flaskr.blog.update"):
        uid = next((u for u, n in g.nodes.items() if n["qualified_name"] == suffix), None)
        if uid is None:
            continue
        r = analyze_impact(REPO, uid)
        impacts.append({"target": suffix, "direct": len(r.direct_dependents), "indirect": len(r.indirect_dependents),
                        "apis": len(r.affected_apis), "tests": len(r.affected_tests), "risk": r.risk_level, "score": r.risk_score})
    res["impact"] = impacts
    uid = next((u for u, n in g.nodes.items() if n["qualified_name"] == "examples.tutorial.flaskr.blog.update"), None)
    res["blog_update_incoming_calls"] = len(g.inc.get(uid, [])) if uid else None
    text = json.dumps(res, indent=1)
    print(text)
    if out_path:
        out_path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    main(a.workspace, a.out)
