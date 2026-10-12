"""Audit script (read-only): parse the already-cloned Flask workspace with the
project's own parsers + resolver and print IR/resolution statistics.
No Neo4j connection, no network, no writes to the clone.
Usage (from backend/): .venv/Scripts/python.exe ../project_audit_2026_10_11/scripts/offline_flask_parse_metrics.py <workspace_dir>
"""
import sys, json, time, collections
from pathlib import Path
sys.path.insert(0, ".")
from app.services.graph_pipeline import _parse_workspace
from parsing.ir.resolver import resolve_relationships
from parsing.ir.models import SymbolType, RelationshipType

root = Path(sys.argv[1])
t0 = time.perf_counter()
pfs = _parse_workspace(root)
t1 = time.perf_counter()
syms = [s for p in pfs for s in p.symbols]
rels = [r for p in pfs for r in p.relationships]
res = resolve_relationships(syms, rels)
t2 = time.perf_counter()

out = {
  "files_parsed": len(pfs),
  "parse_errors": sum(len(p.parse_errors) for p in pfs),
  "symbols_total": len(syms),
  "symbols_by_type": dict(collections.Counter(s.symbol_type.value for s in syms)),
  "relationships_raw_total": len(rels),
  "relationships_by_type_raw": dict(collections.Counter(r.relationship_type.value for r in rels)),
  "relationships_resolved_edges": sum(1 for r in res if r.target_id is not None),
  "resolved_by_type": dict(collections.Counter(r.relationship_type.value for r in res if r.target_id is not None)),
  "unresolved_by_type": dict(collections.Counter(r.relationship_type.value for r in res if r.target_id is None)),
  "ambiguous_conf_0.3_unresolved": sum(1 for r in res if r.target_id is None and r.confidence == 0.3),
  "calls_confidence_distribution_resolved": dict(collections.Counter(round(r.confidence,2) for r in res if r.target_id is not None and r.relationship_type==RelationshipType.CALLS)),
  "all_confidence_distribution_resolved": dict(collections.Counter(round(r.confidence,2) for r in res if r.target_id is not None)),
  "parse_seconds": round(t1-t0,3), "resolve_seconds": round(t2-t1,3),
}
print(json.dumps(out, indent=2))
