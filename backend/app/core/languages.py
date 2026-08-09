"""Single source of truth for which languages CodeSage claims to support.

A language only belongs here once a parser exists that reliably extracts
structural information into the common IR — not merely because Tree-sitter
can parse its grammar.
"""
from enum import Enum


class Language(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    CPP = "cpp"


# Extension -> Language, used for repository language detection during ingestion.
EXTENSION_LANGUAGE_MAP: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".js": Language.JAVASCRIPT,
    ".jsx": Language.JAVASCRIPT,
    ".mjs": Language.JAVASCRIPT,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
    ".java": Language.JAVA,
    ".cpp": Language.CPP,
    ".cc": Language.CPP,
    ".cxx": Language.CPP,
    ".hpp": Language.CPP,
    ".h": Language.CPP,
}

# Languages with a real parser implementation wired up (grows as milestones land).
IMPLEMENTED_PARSERS: set[Language] = {Language.PYTHON}
