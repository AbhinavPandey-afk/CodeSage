"""The normalized Intermediate Representation every language parser must produce.

This is the contract described in CLAUDE.md §5: Tree-sitter -> language parser
-> this IR -> Neo4j. Analysis engines and the graph loader depend only on this
module, never on a specific language's AST shapes.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from app.core.languages import Language


class SymbolType(str, Enum):
    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    IMPORT = "import"
    VARIABLE = "variable"


class RelationshipType(str, Enum):
    CONTAINS = "contains"
    IMPORTS = "imports"
    CALLS = "calls"
    INHERITS = "inherits"


class Symbol(BaseModel):
    """One structural unit extracted from source: a file, class, function, etc."""

    id: str
    name: str
    qualified_name: str
    symbol_type: SymbolType
    file_path: str
    start_line: int
    end_line: int
    language: Language
    decorators: list[str] = []
    docstring: str | None = None


class Relationship(BaseModel):
    """A directed edge between two symbols, with provenance and a confidence score.

    confidence < 1.0 signals inference (e.g. a call resolved by name-matching
    rather than an unambiguous import binding) — CLAUDE.md §11 requires this
    distinction to survive all the way to the UI, never collapsed to a boolean.
    """

    source_id: str
    target_id: str | None  # None when the target could not be resolved to a known symbol
    target_name: str  # raw referenced name, kept even when target_id is unresolved
    relationship_type: RelationshipType
    source_file: str
    source_line: int
    confidence: float = 1.0


class ParsedFile(BaseModel):
    """Everything one parser run extracted from a single source file."""

    file_path: str
    language: Language
    symbols: list[Symbol]
    relationships: list[Relationship]
    parse_errors: list[str] = []
