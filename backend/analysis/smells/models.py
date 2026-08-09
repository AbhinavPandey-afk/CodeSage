"""Output model for the architectural smell detector (CLAUDE.md §16).

Every smell is produced by a deterministic, measurable rule — never an LLM
judgment call — and carries the evidence that triggered it so a developer can
verify the finding directly in the source.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AffectedSymbol:
    qualified_name: str
    file_path: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class Smell:
    smell_type: str  # circular_dependency | god_class | large_function | dead_code_candidate
    severity: str  # LOW | MEDIUM | HIGH
    title: str
    explanation: str
    evidence: str
    affected: list[AffectedSymbol] = field(default_factory=list)
