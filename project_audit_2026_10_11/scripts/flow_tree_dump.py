"""Audit script (read-only): print the OBSERVED execution-flow tree for an entry point with call-site source lines."""
import sys, os, json, linecache
from pathlib import Path
sys.path.insert(0, ".")
import analysis.execution_flow.engine as eng
repo, entry, ws = sys.argv[1], sys.argv[2], Path(sys.argv[3])
eps = {e.qualified_name: e for e in eng.detect_entry_points(repo, limit=50)}
rep = eng.reconstruct_execution_flow(repo, eps[entry].uid)
def walk(h, d=0):
    site = linecache.getline(str(ws / h.source_file), h.source_line).strip()[:70] if h.source_file and h.source_line and h.relationship_type == "CALLS" else ""
    print("RESULT", "  " * d + f"{h.callee_qualified_name} [conf={h.confidence:.2f}, role={h.component_role}, stop={h.terminal_reason}, omitted={h.children_omitted}] @ {h.source_file}:{h.source_line} :: {site}")
    for c in h.children: walk(c, d + 1)
walk(rep.observed)
