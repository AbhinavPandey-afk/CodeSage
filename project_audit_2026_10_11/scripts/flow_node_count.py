"""Audit script (read-only): count nodes of the OBSERVED execution-flow tree for given entry
qualified names, using whichever code tree is first on sys.path (cwd). Used to compare the
committed HEAD engine (pre-fix) with the working-tree engine on the SAME live graph data.
Loads Neo4j/Groq settings from the real backend/.env into os.environ (never printed)."""
import sys, os, json
from pathlib import Path
env_path, repo = sys.argv[1], sys.argv[2]
for line in Path(env_path).read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
sys.path.insert(0, ".")
import analysis.execution_flow.engine as eng
print("ENGINE_FILE", Path(eng.__file__).resolve())
def n(h): return 1 + sum(n(c) for c in h.children)
def reasons(h, acc):
    if not h.children: acc[getattr(h, "terminal_reason", None) or getattr(h, "terminal_kind", None) or "none"] = acc.get(getattr(h, "terminal_reason", None) or getattr(h, "terminal_kind", None) or "none", 0) + 1
    for c in h.children: reasons(c, acc)
    return acc
eps = {e.qualified_name: e for e in eng.detect_entry_points(repo, limit=50)}
for q in sys.argv[3:]:
    rep = eng.reconstruct_execution_flow(repo, eps[q].uid)
    print("RESULT", json.dumps({"entry": q, "nodes_incl_entry": n(rep.observed), "leaf_reasons_or_kinds": reasons(rep.observed, {})}))
