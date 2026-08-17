"""Impact analysis engine (CLAUDE.md §19): given a symbol, answer "what
happens if I change this?" using graph traversal + the classifiers in this
package, then hand the measured signals to risk.score_risk for a
deterministic risk level. No LLM involvement anywhere in this module.
"""
from analysis.impact.classifiers import classify_import, is_api_endpoint, is_service_component, is_test
from analysis.impact.models import DependentSymbol, ExternalDependency, ImpactReport, RiskSignal
from analysis.impact.risk import explain, score_risk
from graph.neo4j.client import get_driver

_MAX_DEPTH = 8


class SymbolNotFoundError(ValueError):
    pass


def _to_dependent(row: dict) -> DependentSymbol:
    return DependentSymbol(
        uid=row["uid"], symbol_type=row["symbol_type"], name=row["name"],
        qualified_name=row["qualified_name"], file_path=row["file_path"],
        start_line=row["start_line"], end_line=row["end_line"], depth=row["depth"],
    )


def analyze_impact(repo_id: str, target_uid: str) -> ImpactReport:
    with get_driver().session() as session:
        target_row = session.run(
            "MATCH (t:Symbol {uid: $uid, repo_id: $repo_id}) "
            "OPTIONAL MATCH (t)-[r]-() "
            "RETURN t.qualified_name AS qualified_name, t.symbol_type AS symbol_type, "
            "t.file_path AS file_path, t.decorators AS decorators, count(r) AS degree",
            uid=target_uid, repo_id=repo_id,
        ).single()

        if target_row is None:
            raise SymbolNotFoundError(f"Symbol {target_uid} not found in repository {repo_id}.")

        dependent_rows = session.run(
            "MATCH path = (dependent:Symbol {repo_id: $repo_id})"
            "-[:CALLS|INHERITS*1.." + str(_MAX_DEPTH) + "]->"
            "(target:Symbol {uid: $uid, repo_id: $repo_id}) "
            "WITH dependent, min(length(path)) AS depth "
            "RETURN dependent.uid AS uid, dependent.symbol_type AS symbol_type, "
            "dependent.name AS name, dependent.qualified_name AS qualified_name, "
            "dependent.file_path AS file_path, dependent.start_line AS start_line, "
            "dependent.end_line AS end_line, dependent.decorators AS decorators, depth "
            "ORDER BY depth, qualified_name",
            uid=target_uid, repo_id=repo_id,
        ).data()

        import_rows = session.run(
            "MATCH (imp:Symbol {repo_id: $repo_id, symbol_type: 'import', file_path: $file_path}) "
            "RETURN DISTINCT imp.name AS dotted",
            repo_id=repo_id, file_path=target_row["file_path"],
        ).data()

    direct = [_to_dependent(r) for r in dependent_rows if r["depth"] == 1]
    indirect = [_to_dependent(r) for r in dependent_rows if r["depth"] > 1]

    affected_apis = [_to_dependent(r) for r in dependent_rows if is_api_endpoint(r.get("decorators") or [])]
    affected_services = [
        _to_dependent(r) for r in dependent_rows
        if is_service_component(r["qualified_name"], r["symbol_type"])
    ]
    affected_tests = [_to_dependent(r) for r in dependent_rows if is_test(r["file_path"], r["name"])]

    external_deps: list[ExternalDependency] = []
    seen_names: set[str] = set()
    for row in import_rows:
        category = classify_import(row["dotted"])
        top_level = row["dotted"].split(".")[0]
        if category and top_level not in seen_names:
            seen_names.add(top_level)
            external_deps.append(ExternalDependency(name=top_level, category=category))

    risk_level, risk_score, risk_signals = score_risk(
        direct_count=len(direct),
        indirect_count=len(indirect),
        affected_apis_count=len(affected_apis),
        affected_services_count=len(affected_services),
        affected_tests_count=len(affected_tests),
        external_dependency_count=len(external_deps),
        target_degree=target_row["degree"],
    )

    explanation = explain(
        target_qualified_name=target_row["qualified_name"],
        direct_count=len(direct),
        indirect_count=len(indirect),
        affected_apis_count=len(affected_apis),
        affected_services_count=len(affected_services),
        affected_tests_count=len(affected_tests),
        external_names=[d.name for d in external_deps],
        risk_level=risk_level,
    )

    return ImpactReport(
        target_uid=target_uid,
        target_qualified_name=target_row["qualified_name"],
        target_symbol_type=target_row["symbol_type"],
        target_file_path=target_row["file_path"],
        direct_dependents=direct,
        indirect_dependents=indirect,
        affected_apis=affected_apis,
        affected_services=affected_services,
        affected_tests=affected_tests,
        external_dependencies=external_deps,
        risk_level=risk_level,
        risk_score=risk_score,
        risk_signals=risk_signals,
        explanation=explanation,
        detection_notes=[
            "API endpoints are detected via common route-decorator patterns "
            "(@app.route/get/post/..., @api_view), not full request-routing analysis.",
            "Service-layer components are detected via naming convention "
            "(*Service, *Repository, *Controller, *Manager, *Client, *Gateway, *Handler).",
            "Dependents beyond depth "
            + str(_MAX_DEPTH)
            + " in the call/inheritance graph are not traversed.",
        ],
    )
