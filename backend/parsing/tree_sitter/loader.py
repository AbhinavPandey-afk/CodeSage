"""Loads and caches compiled Tree-sitter grammars.

Each supported language's grammar package exposes a `language()` capsule;
wrapping that here means individual parsers never touch the tree_sitter_*
packages directly.
"""
from functools import lru_cache

from tree_sitter import Language, Parser

from app.core.languages import Language as CodeSageLanguage


@lru_cache(maxsize=None)
def get_ts_parser(language: CodeSageLanguage) -> Parser:
    if language == CodeSageLanguage.PYTHON:
        import tree_sitter_python as tspython

        return Parser(Language(tspython.language()))

    raise NotImplementedError(f"No Tree-sitter grammar wired for {language.value} yet.")
