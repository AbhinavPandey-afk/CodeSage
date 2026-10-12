"""Read-only: list CALLS edges bound by the code tree in cwd but NOT bound by a reference run, for manual review.

Usage (from a backend/ directory):
  python new_edges_review.py <workspace> <reference.json> [--sample N] [--seed S] [--dump out.json]
`reference.json` is the output of lost_edges.py for the reference tree. Edges are matched on
(file, line, attribute) so a change of call-target encoding does not count as a new edge.
Prints, per sampled edge: the source line, the receiver's declared type as the parser recorded it, and the bound target."""
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, ".")
from app.services.graph_pipeline import _parse_workspace  # noqa: E402
from parsing.ir.models import RelationshipType as RT  # noqa: E402
from parsing.ir.models import SymbolType  # noqa: E402
from parsing.ir.resolver import resolve_relationships  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("workspace", type=Path)
ap.add_argument("reference", type=Path)
ap.add_argument("--sample", type=int, default=40)
ap.add_argument("--seed", type=int, default=11)
ap.add_argument("--dump", type=Path)
a = ap.parse_args()

pfs = _parse_workspace(a.workspace)
syms = [s for p in pfs for s in p.symbols]
rels = [r for p in pfs for r in p.relationships]
by = {s.id: s for s in syms}
res = resolve_relationships(syms, rels)
ref = json.loads(a.reference.read_text(encoding="utf-8"))
ref_bound = {tuple([k.split(":", 2)[0], k.split(":", 2)[1], k.split(":", 2)[2].rsplit(".", 1)[-1].split("<")[0]]) for k, v in ref.items() if v}

new = []
for raw, r in zip(rels, res):
    if raw.relationship_type != RT.CALLS or not r.target_id or by[r.target_id].symbol_type == SymbolType.IMPORT:
        continue
    key = (raw.source_file, str(raw.source_line), raw.target_name.rsplit(".", 1)[-1].split("<")[0])
    if key in ref_bound:
        continue
    new.append((raw, r))

random.Random(a.seed).shuffle(new)
print(f"new edges vs reference: {len(new)}")
rows = []
for raw, r in new[: a.sample]:
    caller = by[raw.source_id]
    recv = raw.target_name.split(".")[0]
    declared = caller.declared_types.get(recv)
    line = (a.workspace / raw.source_file).read_text(encoding="utf-8").splitlines()[raw.source_line - 1].strip()
    rows.append({"where": f"{raw.source_file}:{raw.source_line}", "line": line[:100], "target_name": raw.target_name, "declared": declared,
                 "bound_to": by[r.target_id].qualified_name, "confidence": r.confidence})
    print(f"{raw.source_file.split('/')[-1]}:{raw.source_line} | {line[:78]} | tn={raw.target_name} decl={declared} conf={r.confidence} -> {by[r.target_id].qualified_name[-55:]}")
if a.dump:
    a.dump.write_text(json.dumps(rows, indent=1), encoding="utf-8")
