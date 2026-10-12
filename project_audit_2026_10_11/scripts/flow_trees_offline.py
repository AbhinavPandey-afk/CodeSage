"""Read-only: print the OBSERVED execution-flow trees (with call-site source lines) for entry points whose tree has at
least --min nodes, using the in-memory graph stand-in from downstream_offline.py and the code tree in cwd.
Usage (from a backend/ directory): python flow_trees_offline.py <workspace> [--min 5]"""
import argparse
import importlib.util
import linecache
import sys
from pathlib import Path

sys.path.insert(0, ".")
here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("downstream_offline", here / "downstream_offline.py")
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

ap = argparse.ArgumentParser()
ap.add_argument("workspace", type=Path)
ap.add_argument("--min", type=int, default=5)
a = ap.parse_args()

g = d.FakeGraph(a.workspace)
d.install(g)
from analysis.execution_flow.engine import detect_entry_points, reconstruct_execution_flow  # noqa: E402


def walk(h, depth=0):
    site = ""
    if h.source_file and h.source_line and h.relationship_type == "CALLS":
        site = linecache.getline(str(a.workspace / h.source_file), h.source_line).strip()[:60]
    print("  " * depth + f"{h.callee_qualified_name.replace('src.flask.', 'sf.')} [{h.confidence:.2f} stop={h.terminal_reason}] :: {site}")
    for c in h.children:
        walk(c, depth + 1)


for e in detect_entry_points(d.REPO, limit=20):
    rep = reconstruct_execution_flow(d.REPO, e.uid)
    if d.tree_nodes(rep.observed) >= a.min:
        print(f"=== {e.qualified_name} ({d.tree_nodes(rep.observed)} nodes)")
        walk(rep.observed)
