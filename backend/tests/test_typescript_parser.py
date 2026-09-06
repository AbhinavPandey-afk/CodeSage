"""Golden-repo-style tests for the TypeScript parser -> IR pipeline (CLAUDE.md §34 Phase 6)."""
from pathlib import Path

from parsing.ir.resolver import resolve_relationships
from parsing.parsers.typescript.parser import TypeScriptParser

SOURCE = """import { Injectable } from '@nestjs/common';

interface Order {
  id: number;
}

class BaseService {}

@Injectable()
class PaymentService extends BaseService {
  @Get('/pay')
  async charge(order: Order): Promise<void> {
    return this.gateway.charge(order);
  }

  handleClick = () => {
    helper(1);
  };
}

function helper(x: number): number {
  return x + 1;
}

enum Status {
  Active,
  Inactive,
}
"""


def _parse(tmp_path: Path):
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "mod.ts").write_text(SOURCE, encoding="utf-8")
    parser = TypeScriptParser()
    return parser.parse_file(pkg / "mod.ts", tmp_path)


def test_file_symbol_uses_dotted_module_path(tmp_path):
    pf = _parse(tmp_path)
    file_symbol = next(s for s in pf.symbols if s.symbol_type.value == "file")
    assert file_symbol.qualified_name == "mypkg.mod"


def test_classes_and_inheritance_extracted(tmp_path):
    pf = _parse(tmp_path)
    classes = {s.name: s for s in pf.symbols if s.symbol_type.value == "class"}
    assert {"BaseService", "PaymentService"} <= set(classes)

    inherits = [r for r in pf.relationships if r.relationship_type.value == "inherits"]
    assert len(inherits) == 1
    assert inherits[0].source_id == "mypkg.mod.PaymentService"
    assert inherits[0].target_name == "BaseService"


def test_class_and_method_decorators_captured(tmp_path):
    pf = _parse(tmp_path)
    payment_service = next(s for s in pf.symbols if s.qualified_name == "mypkg.mod.PaymentService")
    assert any("@Injectable" in d for d in payment_service.decorators)

    charge = next(s for s in pf.symbols if s.qualified_name == "mypkg.mod.PaymentService.charge")
    assert charge.symbol_type.value == "method"
    assert any("@Get" in d for d in charge.decorators)


def test_nestjs_style_decorator_is_detected_as_api_endpoint(tmp_path):
    from analysis.impact.classifiers import is_api_endpoint

    pf = _parse(tmp_path)
    charge = next(s for s in pf.symbols if s.qualified_name == "mypkg.mod.PaymentService.charge")
    assert is_api_endpoint(charge.decorators)


def test_class_field_arrow_function_extracted_as_method(tmp_path):
    pf = _parse(tmp_path)
    method = next(s for s in pf.symbols if s.qualified_name == "mypkg.mod.PaymentService.handleClick")
    assert method.symbol_type.value == "method"

    calls = [r for r in pf.relationships if r.relationship_type.value == "calls"]
    assert any(c.source_id == "mypkg.mod.PaymentService.handleClick" and c.target_name == "helper" for c in calls)


def test_top_level_function_extracted(tmp_path):
    pf = _parse(tmp_path)
    functions = {s.qualified_name for s in pf.symbols if s.symbol_type.value == "function"}
    assert "mypkg.mod.helper" in functions


def test_imports_extracted(tmp_path):
    pf = _parse(tmp_path)
    imports = {s.name for s in pf.symbols if s.symbol_type.value == "import"}
    assert "@nestjs/common" in imports


def test_interfaces_and_enums_do_not_crash_and_are_not_extracted_as_symbols(tmp_path):
    pf = _parse(tmp_path)
    assert pf.parse_errors == []
    names = {s.name for s in pf.symbols}
    assert "Order" not in names  # interfaces are not yet mapped to a SymbolType
    assert "Status" not in names  # neither are enums


def test_resolver_links_inheritance_across_same_file(tmp_path):
    pf = _parse(tmp_path)
    resolved = resolve_relationships(pf.symbols, pf.relationships)
    inherit = next(r for r in resolved if r.relationship_type.value == "inherits")
    assert inherit.target_id == "mypkg.mod.BaseService"
    assert inherit.confidence == 0.75


def test_tsx_file_with_jsx_parses_without_error(tmp_path):
    tsx_source = """import React from 'react';

interface Props {
  label: string;
}

export default function Button({ label }: Props) {
  const handleClick = () => {
    console.log(label);
  };
  return <button onClick={handleClick}>{label}</button>;
}
"""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    f = pkg / "Button.tsx"
    f.write_text(tsx_source, encoding="utf-8")
    pf = TypeScriptParser().parse_file(f, tmp_path)
    assert pf.parse_errors == []
    functions = {s.qualified_name for s in pf.symbols if s.symbol_type.value == "function"}
    assert "mypkg.Button.Button" in functions


def test_malformed_file_does_not_crash_parser(tmp_path):
    bad_file = tmp_path / "broken.ts"
    bad_file.write_text("function f(: {\n", encoding="utf-8")  # invalid syntax
    parser = TypeScriptParser()
    pf = parser.parse_file(bad_file, tmp_path)
    # Tree-sitter is error-tolerant, so this should still return a ParsedFile
    # rather than raising -- worst case it just extracts less structure.
    assert pf.file_path == "broken.ts"
