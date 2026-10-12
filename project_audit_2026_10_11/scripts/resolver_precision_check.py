"""Audit script (read-only): inspect callers of one symbol and the exact source lines at the call sites
in the cloned workspace, to judge name-based resolver precision."""
import sys, json, linecache
from pathlib import Path
sys.path.insert(0, ".")
from graph.neo4j.client import get_driver
repo, qname, ws = sys.argv[1], sys.argv[2], Path(sys.argv[3])
with get_driver().session() as s:
    rows = s.run("MATCH (a:Symbol {repo_id:$r})-[x:CALLS]->(b:Symbol {repo_id:$r, qualified_name:$q}) "
                 "RETURN a.qualified_name AS caller, x.source_file AS f, x.source_line AS l, x.confidence AS c ORDER BY f,l", r=repo, q=qname).data()
    cands = s.run("MATCH (b:Symbol {repo_id:$r}) WHERE b.name = $n AND b.symbol_type IN ['function','method','class'] RETURN count(b) AS c", r=repo, n=qname.rsplit('.',1)[-1]).single()["c"]
print("RESULT_HEADER", json.dumps({"target": qname, "same_short_name_candidates_in_repo": cands, "incoming_calls": len(rows)}))
for r in rows[:12]:
    print("RESULT_ROW", r["c"], r["f"], r["l"], "|", linecache.getline(str(ws / r["f"]), r["l"]).strip()[:100])
