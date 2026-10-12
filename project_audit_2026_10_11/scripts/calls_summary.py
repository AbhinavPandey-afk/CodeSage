"""Read-only: parse a cloned workspace with the code tree on sys.path (cwd) and summarise CALLS resolution."""
import sys, json, collections, time
from pathlib import Path
sys.path.insert(0, ".")
from app.services.graph_pipeline import _parse_workspace
from parsing.ir.resolver import resolve_relationships
from parsing.ir.models import RelationshipType as RT, SymbolType
ws = Path(sys.argv[1]); t = time.perf_counter()
pfs = _parse_workspace(ws); syms = [s for p in pfs for s in p.symbols]; rels = [r for p in pfs for r in p.relationships]
t1 = time.perf_counter(); res = resolve_relationships(syms, rels); t2 = time.perf_counter()
by = {s.id: s for s in syms}
calls = [r for r in res if r.relationship_type == RT.CALLS]
print(json.dumps({"files": len(pfs), "symbols": len(syms), "calls": len(calls),
  "calls_resolved_to_definition": sum(1 for r in calls if r.target_id and by[r.target_id].symbol_type != SymbolType.IMPORT),
  "calls_resolved_to_import_node": sum(1 for r in calls if r.target_id and by[r.target_id].symbol_type == SymbolType.IMPORT),
  "calls_ambiguous": sum(1 for r in calls if r.target_id is None and r.confidence == 0.3),
  "inherits_resolved": sum(1 for r in res if r.relationship_type == RT.INHERITS and r.target_id),
  "inherits_total": sum(1 for r in res if r.relationship_type == RT.INHERITS),
  "resolve_seconds": round(t2 - t1, 3)}))
