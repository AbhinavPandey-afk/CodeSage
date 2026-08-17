"""Contracts for GET .../symbols (search) and POST .../impact."""
from pydantic import BaseModel


class SymbolSearchResponse(BaseModel):
    uid: str
    symbol_type: str
    name: str
    qualified_name: str
    file_path: str
    start_line: int


class ImpactRequest(BaseModel):
    symbol_uid: str


class DependentResponse(BaseModel):
    uid: str
    symbol_type: str
    name: str
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int
    depth: int


class ExternalDependencyResponse(BaseModel):
    name: str
    category: str


class RiskSignalResponse(BaseModel):
    name: str
    value: str
    points: int


class ImpactResponse(BaseModel):
    target_uid: str
    target_qualified_name: str
    target_symbol_type: str
    target_file_path: str

    direct_dependents: list[DependentResponse]
    indirect_dependents: list[DependentResponse]
    affected_apis: list[DependentResponse]
    affected_services: list[DependentResponse]
    affected_tests: list[DependentResponse]
    external_dependencies: list[ExternalDependencyResponse]

    risk_level: str
    risk_score: int
    risk_signals: list[RiskSignalResponse]
    explanation: str
    detection_notes: list[str]
