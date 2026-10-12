"""Audit script (read-only): graph views, symbol search/suggestions, impact analysis and the
LLM-free graph half of relationship investigation, plus endpoint latencies."""
import sys, json, time
sys.path.insert(0, ".")
from fastapi.testclient import TestClient
from app.main import app
from graph.queries.relationship import find_relationship
repo = sys.argv[1]; c = TestClient(app); out = {}
def timed(label, fn):
    t = time.perf_counter(); r = fn(); out.setdefault("latency_s", {})[label] = round(time.perf_counter() - t, 3); return r
for g in ("files", "classes"):
    r = timed(f"graph_{g}", lambda: c.get(f"/api/repositories/{repo}/graph", params={"granularity": g}))
    j = r.json(); out[f"graph_{g}"] = {"status": r.status_code, "nodes": len(j["nodes"]), "edges": len(j["edges"]), "truncated": j["truncated"],
                                          "edge_types": sorted({e["relationship_type"] for e in j["edges"]})}
r = c.get(f"/api/repositories/{repo}/symbols", params={"q": "Flask"}); out["symbol_search_Flask"] = {"status": r.status_code, "n": len(r.json()), "first": [x["qualified_name"] for x in r.json()[:3]]}
r = c.get(f"/api/repositories/{repo}/symbols/suggestions"); sugg = r.json(); out["suggestions"] = {"status": r.status_code, "top": [x["qualified_name"] for x in sugg[:5]]}
imp_out = []
for s in sugg[:3]:
    r = timed(f"impact_{s['qualified_name']}", lambda: c.post(f"/api/repositories/{repo}/impact", json={"symbol_uid": s["uid"]}))
    if r.status_code == 200:
        j = r.json(); imp_out.append({"target": j["target_qualified_name"], "direct": len(j["direct_dependents"]), "indirect": len(j["indirect_dependents"]),
            "apis": len(j["affected_apis"]), "tests": len(j["affected_tests"]), "risk": j["risk_level"], "score": j["risk_score"], "signals": [(x["name"], x["points"]) for x in j["risk_signals"]]})
    else: imp_out.append({"status": r.status_code, "body": r.text[:150]})
out["impact"] = imp_out
for label, fn in (("architecture", lambda: c.get(f"/api/repositories/{repo}/architecture")), ("smells", lambda: c.get(f"/api/repositories/{repo}/smells")), ("optimization", lambda: c.get(f"/api/repositories/{repo}/optimization"))):
    timed(label, fn)
# Relationship (graph half only; the LLM narration step is NOT invoked)
uid = {x["qualified_name"]: x["uid"] for x in sugg}
names = list(uid)
if len(names) >= 2:
    pairs = [(names[0], names[1]), (names[0], names[2] if len(names) > 2 else names[1])]
    rel = []
    for a, b in pairs:
        res = find_relationship(repo, uid[a], uid[b])
        rel.append({"a": a, "b": b, "connected": res.connected, "kind": res.relationship_kind, "hops": res.hop_count,
                    "steps": [(s.relationship_type, s.source_file, s.source_line, s.confidence) for s in res.steps][:3]})
    out["relationship_graph_half"] = rel
print("RESULT", json.dumps(out, default=str))
