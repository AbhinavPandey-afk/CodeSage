"""Read-only: CALLS bound by the code tree in cwd, listed with the call-site source line (used to diff two trees)."""
import sys, json
from pathlib import Path
sys.path.insert(0, ".")
from app.services.graph_pipeline import _parse_workspace
from parsing.ir.resolver import resolve_relationships
from parsing.ir.models import RelationshipType as RT, SymbolType
ws = Path(sys.argv[1]); pfs = _parse_workspace(ws)
syms = [s for p in pfs for s in p.symbols]; rels = [r for p in pfs for r in p.relationships]
by = {s.id: s for s in syms}; out = {}
for a, b in zip(rels, resolve_relationships(syms, rels)):
    if a.relationship_type == RT.CALLS:
        k = f"{a.source_file}:{a.source_line}:{a.target_name.replace('?.', '', 1) if a.target_name.startswith('?.') else a.target_name}"
        out[k] = by[b.target_id].qualified_name if b.target_id and by[b.target_id].symbol_type != SymbolType.IMPORT else None
print(json.dumps(out))
