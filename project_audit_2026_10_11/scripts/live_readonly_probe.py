"""Audit script: READ-ONLY live probe of the existing Flask graph in Neo4j via the real
FastAPI routes (in-process TestClient). No ingestion, no writes, no LLM calls, no git fetch.
Prints only counts/derived values; never prints credentials.
Usage (from backend/): .venv/Scripts/python.exe ../project_audit_2026_10_11/scripts/live_readonly_probe.py <repo_id>
"""
import sys, json, collections
sys.path.insert(0, ".")
from fastapi.testclient import TestClient
from app.main import app
from graph.neo4j.client import get_driver, verify_connectivity

repo = sys.argv[1]
out = {"repo_id": repo}
out["neo4j_connectivity"] = verify_connectivity()
with get_driver().session() as s:   # read-only queries
    out["graph_counts"] = {
        "symbols": s.run("MATCH (n:Symbol {repo_id:$r}) RETURN count(n) AS c", r=repo).single()["c"],
        "by_label": {r["l"]: r["c"] for r in s.run("MATCH (n:Symbol {repo_id:$r}) RETURN n.symbol_type AS l, count(*) AS c", r=repo)},
        "rels_by_type": {r["t"]: r["c"] for r in s.run("MATCH (a:Symbol {repo_id:$r})-[x]->(b:Symbol {repo_id:$r}) RETURN type(x) AS t, count(*) AS c", r=repo)},
        "calls_conf": {str(r["k"]): r["c"] for r in s.run("MATCH (a:Symbol {repo_id:$r})-[x:CALLS]->() RETURN x.confidence AS k, count(*) AS c ORDER BY k", r=repo)},
    }
c = TestClient(app)
def get(p): r = c.get(p); return r.status_code, (r.json() if r.status_code == 200 else r.text[:200])
code, h = get("/health"); out["health"] = [code, h]
code, rec = get(f"/api/repositories/{repo}"); out["repo_record_status"] = [code, rec.get("status") if code == 200 else rec]

code, arch = get(f"/api/repositories/{repo}/architecture"); out["architecture_status"] = code
if code == 200:
    out["architecture"] = {
      "components": len(arch["components"]), "relationships": len(arch["relationships"]), "truncated": arch["truncated"],
      "roles": dict(collections.Counter(x["role"] for x in arch["components"])),
      "confidence_labels": dict(collections.Counter(x["confidence_label"] for x in arch["components"])),
      "components_list": [(x["id"], x["role"], x["file_count"], x["symbol_count"], x["confidence_label"]) for x in arch["components"]],
    }
code, sm = get(f"/api/repositories/{repo}/smells"); out["smells_status"] = code
if code == 200:
    out["smells"] = {
      "total": len(sm),
      "by_severity": dict(collections.Counter(x["severity"] for x in sm)),
      "by_type": dict(collections.Counter(x["smell_type"] for x in sm)),
      "keys": sorted(sm[0].keys()) if sm else [],
      "confidence_field_sample": [x.get("confidence") for x in sm[:5]],
      "confidence_label_field": dict(collections.Counter(x.get("confidence_label") for x in sm)),
      "confidence_buckets_raw_(>=0.75/>=0.4/else)": dict(collections.Counter(("high" if x["confidence"]>=0.75 else "medium" if x["confidence"]>=0.4 else "low") for x in sm if x.get("confidence") is not None)),
      "context_flags": dict(collections.Counter(f for x in sm for f in x.get("context_flags", []))),
    }
code, op = get(f"/api/repositories/{repo}/optimization"); out["optimization_status"] = code
if code == 200:
    out["optimization"] = {"proposals": len(op["proposals"]), "by_risk": dict(collections.Counter(p["risk_level"] for p in op["proposals"])),
                           "summary": op["current_architecture_summary"]}
code, fl = get(f"/api/repositories/{repo}/flows"); out["flows_status"] = code
flows = []
def count(h):
    n=1; reasons=collections.Counter(); depth=0
    for ch in h["children"]:
        a,b,d = count(ch); n+=a; reasons.update(b); depth=max(depth,d+1)
    if not h["children"] and h.get("terminal_reason"): reasons[h["terminal_reason"]]+=1
    return n, reasons, depth
if code == 200:
    out["entry_points"] = [(e["qualified_name"], e["route_hint"]) for e in fl]
    for e in fl:
        r = c.post(f"/api/repositories/{repo}/flows/reconstruct", json={"entry_uid": e["uid"]})
        if r.status_code != 200: flows.append((e["qualified_name"], r.status_code)); continue
        j = r.json(); n, reasons, d = count(j["observed"])
        flows.append({"entry": e["qualified_name"], "observed_nodes_incl_entry": n, "max_depth": d, "truncated": j["truncated"],
                      "leaf_terminal_reasons": dict(reasons), "has_proposed": j["proposed"] is not None})
    out["flows"] = flows
print(json.dumps(out, indent=2, default=str))
