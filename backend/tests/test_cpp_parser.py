"""Golden-repo-style tests for the C++ parser -> IR pipeline (CLAUDE.md §34 Phase 6)."""
from pathlib import Path

from parsing.ir.resolver import resolve_relationships
from parsing.parsers.cpp.parser import CppParser

SOURCE = """#include <iostream>
#include "Gateway.h"

namespace payments {

class BaseService {};

class PaymentService : public BaseService {
public:
    Result charge(Order order) {
        Receipt* r = new Receipt();
        return gateway_->charge(order);
    }

    int helper(int x);

private:
    Gateway* gateway_;
};

int PaymentService::helper(int x) {
    return x + 1;
}

}
"""


def _parse(tmp_path: Path):
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "payment_service.cpp").write_text(SOURCE, encoding="utf-8")
    parser = CppParser()
    return parser.parse_file(pkg / "payment_service.cpp", tmp_path)


def test_file_symbol_uses_dotted_module_path(tmp_path):
    pf = _parse(tmp_path)
    file_symbol = next(s for s in pf.symbols if s.symbol_type.value == "file")
    assert file_symbol.qualified_name == "mypkg.payment_service"


def test_classes_and_inheritance_extracted_inside_namespace(tmp_path):
    pf = _parse(tmp_path)
    classes = {s.qualified_name: s for s in pf.symbols if s.symbol_type.value == "class"}
    assert "mypkg.payment_service.payments.BaseService" in classes
    assert "mypkg.payment_service.payments.PaymentService" in classes

    inherits = [r for r in pf.relationships if r.relationship_type.value == "inherits"]
    assert len(inherits) == 1
    assert inherits[0].source_id == "mypkg.payment_service.payments.PaymentService"
    assert inherits[0].target_name == "BaseService"


def test_inline_method_call_and_new_expression_extracted(tmp_path):
    pf = _parse(tmp_path)
    charge = next(
        s for s in pf.symbols
        if s.qualified_name == "mypkg.payment_service.payments.PaymentService.charge"
    )
    assert charge.symbol_type.value == "method"

    calls = [r for r in pf.relationships if r.relationship_type.value == "calls" and r.source_id == charge.id]
    assert any(c.target_name == "gateway_.charge" for c in calls)
    assert any(c.target_name == "Receipt" for c in calls)


def test_method_declared_without_body_is_still_extracted(tmp_path):
    pf = _parse(tmp_path)
    declared = next(
        s for s in pf.symbols
        if s.qualified_name == "mypkg.payment_service.payments.PaymentService.helper"
    )
    assert declared.symbol_type.value == "method"


def test_out_of_line_method_definition_attached_to_its_class(tmp_path):
    pf = _parse(tmp_path)
    contains = [r for r in pf.relationships if r.relationship_type.value == "contains"]
    assert any(
        r.source_id == "mypkg.payment_service.payments.PaymentService" and r.target_name == "helper"
        for r in contains
    )


def test_includes_extracted_both_forms(tmp_path):
    pf = _parse(tmp_path)
    imports = {s.name for s in pf.symbols if s.symbol_type.value == "import"}
    assert "iostream" in imports
    assert "Gateway.h" in imports


def test_resolver_links_inheritance_across_same_file(tmp_path):
    pf = _parse(tmp_path)
    resolved = resolve_relationships(pf.symbols, pf.relationships)
    inherit = next(r for r in resolved if r.relationship_type.value == "inherits")
    assert inherit.target_id == "mypkg.payment_service.payments.BaseService"
    assert inherit.confidence == 0.95  # same-file lexical scope (was name-based 0.75)


def test_malformed_file_does_not_crash_parser(tmp_path):
    bad_file = tmp_path / "broken.cpp"
    bad_file.write_text("class Broken {\n  void f(\n", encoding="utf-8")  # invalid syntax
    parser = CppParser()
    pf = parser.parse_file(bad_file, tmp_path)
    # Tree-sitter is error-tolerant, so this should still return a ParsedFile
    # rather than raising -- worst case it just extracts less structure.
    assert pf.file_path == "broken.cpp"
