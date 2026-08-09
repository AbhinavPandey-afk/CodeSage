"""Resolves CALLS/INHERITS relationship targets across the whole repository.

Parsers work one file at a time and can't know whether `Foo` in file B is the
`Foo` defined in file A, so they emit target_id=None + a raw target_name.
This runs once per repo, after every file is parsed, with the full symbol
table available — the only place cross-file linking can happen correctly.
"""
from parsing.ir.models import Relationship, Symbol, SymbolType

_RESOLVABLE_TARGETS = {SymbolType.CLASS, SymbolType.FUNCTION, SymbolType.METHOD}


def resolve_relationships(symbols: list[Symbol], relationships: list[Relationship]) -> list[Relationship]:
    by_qualified_name = {s.qualified_name: s.id for s in symbols}
    by_short_name: dict[str, list[str]] = {}
    for s in symbols:
        if s.symbol_type in _RESOLVABLE_TARGETS:
            by_short_name.setdefault(s.name, []).append(s.id)

    resolved: list[Relationship] = []
    for rel in relationships:
        if rel.target_id is not None:
            resolved.append(rel)
            continue

        # Exact qualified-name match (e.g. "self.method" resolved within a class scope
        # would already carry the short name; this branch mainly catches dotted imports
        # and fully-qualified inheritance references).
        exact = by_qualified_name.get(rel.target_name)
        if exact:
            resolved.append(rel.model_copy(update={"target_id": exact, "confidence": 0.95}))
            continue

        # Fall back to the last dotted segment (handles "self.method", "obj.method").
        short_name = rel.target_name.rsplit(".", 1)[-1]
        candidates = by_short_name.get(short_name, [])
        if len(candidates) == 1:
            resolved.append(rel.model_copy(update={"target_id": candidates[0], "confidence": 0.75}))
        elif len(candidates) > 1:
            # Ambiguous — genuinely uncertain, not a resolver bug. Surface it as such
            # rather than guessing one candidate silently.
            resolved.append(rel.model_copy(update={"confidence": 0.3}))
        else:
            # Likely external (stdlib/third-party) or dynamic — leave unresolved.
            resolved.append(rel.model_copy(update={"confidence": min(rel.confidence, 0.35)}))

    return resolved
