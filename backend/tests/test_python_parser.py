"""Golden-repo-style tests for the Python parser -> IR pipeline (CLAUDE.md §32)."""
from pathlib import Path

from parsing.ir.resolver import resolve_relationships
from parsing.parsers.python.parser import PythonParser

SOURCE = '''"""Module docstring."""
import os
from collections import OrderedDict as OD


class Base:
    pass


class Foo(Base):
    """Foo class."""

    @staticmethod
    def bar(x):
        return helper(x)


def helper(x):
    return x + 1
'''


def _parse(tmp_path: Path):
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "mod.py").write_text(SOURCE, encoding="utf-8")
    parser = PythonParser()
    return parser.parse_file(pkg / "mod.py", tmp_path)


def test_file_symbol_uses_dotted_module_path(tmp_path):
    pf = _parse(tmp_path)
    file_symbol = next(s for s in pf.symbols if s.symbol_type.value == "file")
    assert file_symbol.qualified_name == "mypkg.mod"
    assert file_symbol.docstring == '"""Module docstring."""'


def test_classes_and_inheritance_extracted(tmp_path):
    pf = _parse(tmp_path)
    classes = {s.name: s for s in pf.symbols if s.symbol_type.value == "class"}
    assert set(classes) == {"Base", "Foo"}
    assert classes["Foo"].qualified_name == "mypkg.mod.Foo"

    inherits = [r for r in pf.relationships if r.relationship_type.value == "inherits"]
    assert len(inherits) == 1
    assert inherits[0].source_id == "mypkg.mod.Foo"
    assert inherits[0].target_name == "Base"


def test_method_decorator_and_call_extracted(tmp_path):
    pf = _parse(tmp_path)
    bar = next(s for s in pf.symbols if s.qualified_name == "mypkg.mod.Foo.bar")
    assert bar.symbol_type.value == "method"
    assert bar.decorators == ["@staticmethod"]

    calls = [r for r in pf.relationships if r.relationship_type.value == "calls"]
    assert any(c.source_id == "mypkg.mod.Foo.bar" and c.target_name == "helper" for c in calls)


def test_imports_extracted_including_aliases(tmp_path):
    pf = _parse(tmp_path)
    imports = {s.name for s in pf.symbols if s.symbol_type.value == "import"}
    assert "os" in imports
    assert "collections.OrderedDict" in imports


def test_resolver_links_call_and_inheritance_across_same_file(tmp_path):
    pf = _parse(tmp_path)
    resolved = resolve_relationships(pf.symbols, pf.relationships)

    call = next(r for r in resolved if r.relationship_type.value == "calls")
    assert call.target_id == "mypkg.mod.helper"
    assert call.confidence == 0.75

    inherit = next(r for r in resolved if r.relationship_type.value == "inherits")
    assert inherit.target_id == "mypkg.mod.Base"
    assert inherit.confidence == 0.75


def test_malformed_file_does_not_crash_parser(tmp_path):
    bad_file = tmp_path / "broken.py"
    bad_file.write_text("def f(:\n  pass", encoding="utf-8")  # invalid syntax
    parser = PythonParser()
    pf = parser.parse_file(bad_file, tmp_path)
    # Tree-sitter is error-tolerant, so this should still return a ParsedFile
    # rather than raising — worst case it just extracts less structure.
    assert pf.file_path == "broken.py"
