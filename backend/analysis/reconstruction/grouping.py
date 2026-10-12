"""Deterministic component discovery and role inference (CLAUDE.md §15/§35 Steps A-C).

Pure functions over already-extracted graph facts — no Neo4j access here, so
this is unit-testable without a live database, matching the style of
analysis/impact/risk.py and analysis/smells/graph_algorithms.py.

Role inference reuses analysis.impact.classifiers.is_api_endpoint and
classify_import verbatim (same evidence, same rule). It does NOT reuse
is_service_component, because that function deliberately lumps
Service/Repository/Controller/Manager/Client/Gateway/Handler into one
"service-ish" bucket for impact analysis; architecture reconstruction needs a
finer split (service vs. data_access vs. external_integration) to reconstruct
a layered picture, so the suffix sets below subdivide that same convention
rather than duplicating unrelated logic.
"""
from dataclasses import dataclass

from analysis.impact.classifiers import classify_import, is_api_endpoint
from analysis.reconstruction.models import ComponentRole, ConfidenceLabel, ThirdPartyDependency

_DATA_ACCESS_SUFFIXES = ("Repository", "Dao", "DAO")
_EXTERNAL_SUFFIXES = ("Client", "Gateway")
_SERVICE_SUFFIXES = ("Service", "Controller", "Manager", "Handler")

_CONFIRMED_THRESHOLD = 0.75
_INFERRED_THRESHOLD = 0.4


@dataclass(frozen=True)
class SymbolSignal:
    qualified_name: str
    symbol_type: str  # "class" | "function" | "method"
    decorators: list[str]


def confidence_label(score: float) -> ConfidenceLabel:
    if score >= _CONFIRMED_THRESHOLD:
        return "Confirmed"
    if score >= _INFERRED_THRESHOLD:
        return "Inferred"
    return "Uncertain"


def group_key(file_path: str) -> str:
    """The architectural component a file belongs to: its directory path, up
    to two levels deep (deep enough to separate e.g. app/api from app/services,
    shallow enough that a 5000-file repo doesn't produce 5000 components)."""
    dir_parts = file_path.split("/")[:-1]
    if not dir_parts:
        return "(root)"
    return "/".join(dir_parts[:2])


def third_party_dependencies(import_targets: list[str]) -> list[ThirdPartyDependency]:
    """Real, named external packages a component imports — same evidence
    already used for role inference (classify_import), but keeping the
    actual name instead of discarding it after counting categories. Mirrors
    analysis/impact/engine.py's per-symbol external-dependency extraction
    (dedup by top-level import segment), just applied to a whole component's
    import set instead of one symbol's file."""
    seen: set[str] = set()
    deps: list[ThirdPartyDependency] = []
    for dotted in import_targets:
        category = classify_import(dotted)
        if category is None:
            continue
        top_level = dotted.split(".")[0]
        if not top_level or top_level in seen:
            continue
        seen.add(top_level)
        deps.append(ThirdPartyDependency(name=top_level, category=category))
    return deps


def _has_segment(key: str, *needles: str) -> bool:
    segments = [s.lower() for s in key.split("/")]
    return any(any(n in seg for n in needles) for seg in segments)


def _class_suffix_hits(symbols: list[SymbolSignal], suffixes: tuple[str, ...]) -> list[SymbolSignal]:
    return [
        s for s in symbols
        if s.symbol_type == "class" and s.qualified_name.split(".")[-1].endswith(suffixes)
    ]


def infer_role(
    key: str, symbols: list[SymbolSignal], import_targets: list[str]
) -> tuple[ComponentRole, float, list[str]]:
    """Returns (role, confidence 0-1, evidence lines). First matching rule wins,
    checked in the order a layered API->Service->DataAccess->External
    architecture would expect a directory to declare its intent."""
    if _has_segment(key, "test"):
        return "test", 0.9, [f"Directory name '{key}' indicates test code."]

    import_categories = [classify_import(t) for t in import_targets]
    db_imports = import_categories.count("database")
    ext_imports = import_categories.count("external_service")

    api_hits = [s for s in symbols if is_api_endpoint(s.decorators)]
    if api_hits or _has_segment(key, "api", "route"):
        evidence, conf = [], 0.5
        if api_hits:
            conf += 0.35
            evidence.append(f"{len(api_hits)} symbol(s) decorated with a route/endpoint decorator.")
        if _has_segment(key, "api", "route"):
            conf += 0.15
            evidence.append(f"Directory name '{key}' matches an API-layer naming convention.")
        return "api", min(conf, 0.98), evidence

    data_access_hits = _class_suffix_hits(symbols, _DATA_ACCESS_SUFFIXES)
    if data_access_hits or db_imports or _has_segment(key, "repositor", "dao", "persistence"):
        evidence, conf = [], 0.3
        if data_access_hits:
            conf += 0.4
            evidence.append(f"{len(data_access_hits)} class(es) named *Repository/*Dao.")
        if db_imports:
            conf += 0.2
            evidence.append(f"{db_imports} import(s) of a known database client library.")
        if _has_segment(key, "repositor", "dao", "persistence"):
            conf += 0.15
            evidence.append(f"Directory name '{key}' matches a data-access naming convention.")
        return "data_access", min(conf, 0.98), evidence

    external_hits = _class_suffix_hits(symbols, _EXTERNAL_SUFFIXES)
    if external_hits or ext_imports or _has_segment(key, "client", "integration", "external"):
        evidence, conf = [], 0.3
        if external_hits:
            conf += 0.35
            evidence.append(f"{len(external_hits)} class(es) named *Client/*Gateway.")
        if ext_imports:
            conf += 0.2
            evidence.append(f"{ext_imports} import(s) of a third-party (non-stdlib) package.")
        if _has_segment(key, "client", "integration", "external"):
            conf += 0.15
            evidence.append(f"Directory name '{key}' matches an external-integration naming convention.")
        return "external_integration", min(conf, 0.95), evidence

    service_hits = _class_suffix_hits(symbols, _SERVICE_SUFFIXES)
    if service_hits or _has_segment(key, "service"):
        evidence, conf = [], 0.3
        if service_hits:
            conf += 0.4
            evidence.append(f"{len(service_hits)} class(es) named *Service/*Controller/*Manager/*Handler.")
        if _has_segment(key, "service"):
            conf += 0.2
            evidence.append(f"Directory name '{key}' matches a service-layer naming convention.")
        return "service", min(conf, 0.95), evidence

    if _has_segment(key, "model", "schema", "entity"):
        return "model", 0.55, [f"Directory name '{key}' matches a data-model naming convention."]

    return "other", 0.3, ["No decorator, naming-convention, or import evidence matched a specific architectural role."]
