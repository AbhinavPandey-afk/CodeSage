"""Golden-repo-style tests for the Java parser -> IR pipeline (CLAUDE.md §34 Phase 6)."""
from pathlib import Path

from parsing.ir.resolver import resolve_relationships
from parsing.parsers.java.parser import JavaParser

SOURCE = """package com.example.payments;

import com.example.services.BaseService;
import java.util.List;
import static com.example.util.Helpers.helper;

class BaseService {}

@Service
public class PaymentService extends BaseService {

    public PaymentService(PaymentGateway gateway) {
        this.gateway = gateway;
    }

    @GetMapping("/pay")
    public Result charge(Order order) {
        Receipt r = new Receipt();
        return this.gateway.charge(order);
    }

    private int helper(int x) {
        return x + 1;
    }
}

interface Chargeable {
    Result charge(Order order);
}
"""


def _parse(tmp_path: Path):
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "PaymentService.java").write_text(SOURCE, encoding="utf-8")
    parser = JavaParser()
    return parser.parse_file(pkg / "PaymentService.java", tmp_path)


def test_file_symbol_uses_dotted_module_path(tmp_path):
    pf = _parse(tmp_path)
    file_symbol = next(s for s in pf.symbols if s.symbol_type.value == "file")
    assert file_symbol.qualified_name == "mypkg.PaymentService"


def test_classes_and_inheritance_extracted(tmp_path):
    pf = _parse(tmp_path)
    classes = {s.name: s for s in pf.symbols if s.symbol_type.value == "class"}
    assert {"BaseService", "PaymentService"} <= set(classes)

    inherits = [r for r in pf.relationships if r.relationship_type.value == "inherits"]
    assert len(inherits) == 1
    assert inherits[0].source_id == "mypkg.PaymentService.PaymentService"
    assert inherits[0].target_name == "BaseService"


def test_class_annotation_captured(tmp_path):
    pf = _parse(tmp_path)
    service = next(s for s in pf.symbols if s.qualified_name == "mypkg.PaymentService.PaymentService")
    assert any("@Service" in d for d in service.decorators)


def test_method_annotation_captured_and_detected_as_api_endpoint(tmp_path):
    from analysis.impact.classifiers import is_api_endpoint

    pf = _parse(tmp_path)
    charge = next(s for s in pf.symbols if s.qualified_name == "mypkg.PaymentService.PaymentService.charge")
    assert charge.symbol_type.value == "method"
    assert any("@GetMapping" in d for d in charge.decorators)
    assert is_api_endpoint(charge.decorators)


def test_constructor_extracted_as_method(tmp_path):
    pf = _parse(tmp_path)
    ctor = next(
        s for s in pf.symbols
        if s.qualified_name == "mypkg.PaymentService.PaymentService.PaymentService"
    )
    assert ctor.symbol_type.value == "method"


def test_method_invocation_and_new_expression_extracted_as_calls(tmp_path):
    pf = _parse(tmp_path)
    calls = [r for r in pf.relationships if r.relationship_type.value == "calls"]
    charge_calls = [c for c in calls if c.source_id == "mypkg.PaymentService.PaymentService.charge"]
    assert any(c.target_name == "this.gateway.charge" for c in charge_calls)
    assert any(c.target_name == "Receipt" for c in charge_calls)


def test_imports_extracted_including_static(tmp_path):
    pf = _parse(tmp_path)
    imports = {s.name for s in pf.symbols if s.symbol_type.value == "import"}
    assert "com.example.services.BaseService" in imports
    assert "com.example.util.Helpers.helper" in imports


def test_interfaces_do_not_crash_and_are_not_extracted_as_symbols(tmp_path):
    pf = _parse(tmp_path)
    assert pf.parse_errors == []
    names = {s.name for s in pf.symbols}
    assert "Chargeable" not in names


def test_resolver_links_inheritance_across_same_file(tmp_path):
    pf = _parse(tmp_path)
    resolved = resolve_relationships(pf.symbols, pf.relationships)
    inherit = next(r for r in resolved if r.relationship_type.value == "inherits")
    assert inherit.target_id == "mypkg.PaymentService.BaseService"
    assert inherit.confidence == 0.95  # same-file lexical scope (was name-based 0.75)


def test_malformed_file_does_not_crash_parser(tmp_path):
    bad_file = tmp_path / "Broken.java"
    bad_file.write_text("class Broken {\n  public void f(\n", encoding="utf-8")  # invalid syntax
    parser = JavaParser()
    pf = parser.parse_file(bad_file, tmp_path)
    # Tree-sitter is error-tolerant, so this should still return a ParsedFile
    # rather than raising -- worst case it just extracts less structure.
    assert pf.file_path == "Broken.java"
