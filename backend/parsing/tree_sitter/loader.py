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

    if language == CodeSageLanguage.JAVASCRIPT:
        import tree_sitter_javascript as tsjavascript

        return Parser(Language(tsjavascript.language()))

    if language == CodeSageLanguage.TYPESCRIPT:
        import tree_sitter_typescript as tstypescript

        return Parser(Language(tstypescript.language_typescript()))

    if language == CodeSageLanguage.JAVA:
        import tree_sitter_java as tsjava

        return Parser(Language(tsjava.language()))

    raise NotImplementedError(f"No Tree-sitter grammar wired for {language.value} yet.")


@lru_cache(maxsize=None)
def get_tsx_parser() -> Parser:
    """TypeScript ships two grammars: `.ts` and `.tsx`. They aren't
    interchangeable -- `<Foo>` is ambiguous between a JSX element and a type
    assertion, so a `.tsx` file must be parsed with the `tsx` grammar rather
    than get_ts_parser(TYPESCRIPT)'s plain-`.ts` one."""
    import tree_sitter_typescript as tstypescript

    return Parser(Language(tstypescript.language_tsx()))
