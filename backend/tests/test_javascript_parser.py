"""Golden-repo-style tests for the JavaScript parser -> IR pipeline (CLAUDE.md §34 Phase 6)."""
from pathlib import Path

from parsing.ir.resolver import resolve_relationships
from parsing.parsers.javascript.parser import JavaScriptParser

SOURCE = """import express from 'express';
const pool = require('./db/pool');

class BaseService {}

class PaymentService extends BaseService {
  async charge(order) {
    return this.gateway(order);
  }
}

function helper(x) {
  return x + 1;
}

const arrowHelper = (x) => helper(x);

export class Exported {
  handleClick = () => {
    helper(1);
  };
}
"""


def _parse(tmp_path: Path):
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "mod.js").write_text(SOURCE, encoding="utf-8")
    parser = JavaScriptParser()
    return parser.parse_file(pkg / "mod.js", tmp_path)


def test_file_symbol_uses_dotted_module_path(tmp_path):
    pf = _parse(tmp_path)
    file_symbol = next(s for s in pf.symbols if s.symbol_type.value == "file")
    assert file_symbol.qualified_name == "mypkg.mod"


def test_classes_and_inheritance_extracted(tmp_path):
    pf = _parse(tmp_path)
    classes = {s.name: s for s in pf.symbols if s.symbol_type.value == "class"}
    assert {"BaseService", "PaymentService", "Exported"} <= set(classes)
    assert classes["PaymentService"].qualified_name == "mypkg.mod.PaymentService"

    inherits = [r for r in pf.relationships if r.relationship_type.value == "inherits"]
    assert len(inherits) == 1
    assert inherits[0].source_id == "mypkg.mod.PaymentService"
    assert inherits[0].target_name == "BaseService"


def test_method_and_call_extracted(tmp_path):
    pf = _parse(tmp_path)
    charge = next(s for s in pf.symbols if s.qualified_name == "mypkg.mod.PaymentService.charge")
    assert charge.symbol_type.value == "method"

    calls = [r for r in pf.relationships if r.relationship_type.value == "calls"]
    assert any(c.source_id == "mypkg.mod.PaymentService.charge" and c.target_name == "this.gateway" for c in calls)


def test_top_level_function_and_arrow_function_extracted(tmp_path):
    pf = _parse(tmp_path)
    functions = {s.qualified_name for s in pf.symbols if s.symbol_type.value == "function"}
    assert "mypkg.mod.helper" in functions
    assert "mypkg.mod.arrowHelper" in functions

    calls = [r for r in pf.relationships if r.relationship_type.value == "calls"]
    assert any(c.source_id == "mypkg.mod.arrowHelper" and c.target_name == "helper" for c in calls)


def test_class_field_arrow_function_extracted_as_method(tmp_path):
    pf = _parse(tmp_path)
    method = next(s for s in pf.symbols if s.qualified_name == "mypkg.mod.Exported.handleClick")
    assert method.symbol_type.value == "method"

    calls = [r for r in pf.relationships if r.relationship_type.value == "calls"]
    assert any(c.source_id == "mypkg.mod.Exported.handleClick" and c.target_name == "helper" for c in calls)


def test_es_module_and_commonjs_imports_both_extracted(tmp_path):
    pf = _parse(tmp_path)
    imports = {s.name for s in pf.symbols if s.symbol_type.value == "import"}
    assert "express" in imports
    assert "./db/pool" in imports


def test_resolver_links_call_and_inheritance_across_same_file(tmp_path):
    pf = _parse(tmp_path)
    resolved = resolve_relationships(pf.symbols, pf.relationships)

    inherit = next(r for r in resolved if r.relationship_type.value == "inherits")
    assert inherit.target_id == "mypkg.mod.BaseService"
    assert inherit.confidence == 0.95  # same-file lexical scope (was name-based 0.75)

    call = next(r for r in resolved if r.target_name == "helper")
    assert call.target_id == "mypkg.mod.helper"


def test_malformed_file_does_not_crash_parser(tmp_path):
    bad_file = tmp_path / "broken.js"
    bad_file.write_text("function f(: {\n", encoding="utf-8")  # invalid syntax
    parser = JavaScriptParser()
    pf = parser.parse_file(bad_file, tmp_path)
    # Tree-sitter is error-tolerant, so this should still return a ParsedFile
    # rather than raising -- worst case it just extracts less structure.
    assert pf.file_path == "broken.js"
