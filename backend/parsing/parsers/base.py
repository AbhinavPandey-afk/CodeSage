"""Common interface every language parser implements.

Adding a language means adding one subclass here — nothing downstream (graph
loader, retrieval, analysis engines) branches on language.
"""
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.languages import Language
from parsing.ir.models import ParsedFile


class LanguageParser(ABC):
    language: Language

    @abstractmethod
    def parse_file(self, file_path: Path, repo_root: Path) -> ParsedFile:
        """Parse one source file into the normalized IR.

        file_path is absolute; repo_root is used to compute the repo-relative
        path stored on every Symbol/Relationship for evidence display.
        """
        raise NotImplementedError


def dedupe_symbol_id(seen_ids: dict[str, int], candidate: str) -> str:
    """Guarantee a unique Symbol.id within one parse_file call.

    Symbol.id becomes the Neo4j `uid` primary key (graph/loader.py writes
    all symbols of a type in one UNWIND+MERGE batch), so two symbols sharing
    an id crash the whole repository's graph build with a
    ConstraintValidationFailed error. But two distinct definitions can
    legitimately share a qualified_name -- e.g. a redefinition inside an
    if/else branch, or literal duplicate names in test-fixture source (real
    case: psf/black's tests/data/cases/*.py, which are formatted-output
    samples, not importable modules). qualified_name is left untouched so
    cross-file resolution (parsing.ir.resolver, keyed on qualified_name)
    is unaffected -- only the id disambiguates.
    """
    count = seen_ids.get(candidate, 0)
    seen_ids[candidate] = count + 1
    return candidate if count == 0 else f"{candidate}#{count}"
