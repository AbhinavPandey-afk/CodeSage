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
