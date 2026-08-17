"""Output model for the impact analysis engine (CLAUDE.md §19/§20).

Every field here is either a direct graph fact (dependents, files) or the
output of a named, deterministic heuristic (API/service/test classification,
external-dependency detection, risk scoring) — never an LLM judgment call.
Fields whose detection is heuristic say so explicitly in `detection_note` so
the UI can disclose it, per CLAUDE.md §11's ban on presenting uncertain
static analysis as fact.
"""
from dataclasses import dataclass, field

RiskLevel = str  # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"


@dataclass(frozen=True)
class DependentSymbol:
    uid: str
    symbol_type: str
    name: str
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int
    depth: int  # 1 = direct dependent, >1 = indirect (transitive)


@dataclass(frozen=True)
class ExternalDependency:
    name: str
    category: str  # "database" | "external_service"


@dataclass(frozen=True)
class RiskSignal:
    name: str
    value: str
    points: int


@dataclass(frozen=True)
class ImpactReport:
    target_uid: str
    target_qualified_name: str
    target_symbol_type: str
    target_file_path: str

    direct_dependents: list[DependentSymbol]
    indirect_dependents: list[DependentSymbol]

    affected_apis: list[DependentSymbol]
    affected_services: list[DependentSymbol]
    affected_tests: list[DependentSymbol]

    external_dependencies: list[ExternalDependency]

    risk_level: RiskLevel
    risk_score: int
    risk_signals: list[RiskSignal]
    explanation: str

    detection_notes: list[str] = field(default_factory=list)
