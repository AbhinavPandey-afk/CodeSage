"""Unit tests for the shared symbol-id dedup helper (parsing/parsers/base.py).

Regression coverage for a real failure: psf/black's tests/data/cases/*.py
fixtures are literal formatted-output samples, not importable modules, and
some legitimately define the same class name twice in one file. Before this
fix, Symbol.id was just the qualified_name, so both definitions produced an
identical id -> identical Neo4j uid -> ConstraintValidationFailed on the
Symbol.uid uniqueness constraint, aborting the whole repository's graph build.
"""
from parsing.parsers.base import dedupe_symbol_id


def test_first_occurrence_keeps_the_plain_id():
    seen: dict[str, int] = {}
    assert dedupe_symbol_id(seen, "pkg.mod.A") == "pkg.mod.A"


def test_repeated_qualified_name_gets_a_unique_suffix():
    seen: dict[str, int] = {}
    first = dedupe_symbol_id(seen, "pkg.mod.A")
    second = dedupe_symbol_id(seen, "pkg.mod.A")
    third = dedupe_symbol_id(seen, "pkg.mod.A")

    assert first == "pkg.mod.A"
    assert second == "pkg.mod.A#1"
    assert third == "pkg.mod.A#2"
    assert len({first, second, third}) == 3


def test_dedup_state_is_scoped_to_the_dict_passed_in():
    # Each parse_file call constructs its own seen_ids dict, so unrelated
    # files (or unrelated names within the same file) never interfere.
    seen_a: dict[str, int] = {}
    seen_b: dict[str, int] = {}
    assert dedupe_symbol_id(seen_a, "pkg.mod.A") == "pkg.mod.A"
    assert dedupe_symbol_id(seen_b, "pkg.mod.A") == "pkg.mod.A"
