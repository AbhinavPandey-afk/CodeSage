"""Scope-aware CALLS/INHERITS resolution (parsing/ir/resolver.py).

Python cases are driven through the real parser so the import/receiver encoding the resolver relies on is
exercised too; Java, JavaScript and C++ cases check the language-specific visibility rules.
"""
from pathlib import Path

from parsing.ir.models import RelationshipType, SymbolType
from parsing.ir.resolver import resolve_relationships
from parsing.parsers.cpp.parser import CppParser
from parsing.parsers.java.parser import JavaParser
from parsing.parsers.javascript.parser import JavaScriptParser
from parsing.parsers.python.parser import PythonParser


def _resolve(tmp_path: Path, files: dict[str, str], parser=None):
    parser = parser or PythonParser()
    symbols, rels = [], []
    for rel_path, source in files.items():
        target = tmp_path / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
        pf = parser.parse_file(target, tmp_path)
        symbols += pf.symbols
        rels += pf.relationships
    by_id = {s.id: s for s in symbols}
    resolved = resolve_relationships(symbols, rels)
    return by_id, resolved


def _calls(resolved, by_id, caller_suffix: str):
    return [r for r in resolved if r.relationship_type == RelationshipType.CALLS
            and by_id[r.source_id].qualified_name.endswith(caller_suffix)]


def _only(resolved, by_id, caller_suffix, target_name):
    matches = [r for r in _calls(resolved, by_id, caller_suffix) if r.target_name == target_name]
    assert len(matches) == 1, (caller_suffix, target_name, [r.target_name for r in _calls(resolved, by_id, caller_suffix)])
    return matches[0]


def _target_qn(by_id, rel):
    return by_id[rel.target_id].qualified_name if rel.target_id else None


# ---- the false-positive pattern that motivated the change ---------------------------------------------


def test_generic_name_on_unknown_receiver_is_not_bound_to_unique_repo_method(tmp_path):
    by_id, resolved = _resolve(tmp_path, {
        "app/util.py": "def update(x):\n    return x\n",
        "app/main.py": "def configure(config):\n    config.update({'a': 1})\n",
    })
    call = _only(resolved, by_id, "app.main.configure", "config.update")
    assert call.target_id is None
    assert call.confidence <= 0.35  # unresolved, not a name-based guess


def test_chained_receiver_is_not_mistaken_for_a_bare_call(tmp_path):
    by_id, resolved = _resolve(tmp_path, {
        "app/main.py": "def close():\n    pass\n\ndef run(client):\n    client.get().close()\n",
    })
    call = _only(resolved, by_id, "app.main.run", "?.close")
    assert call.target_id is None  # `.close()` on a call result is not the module-level close()
    assert _target_qn(by_id, _only(resolved, by_id, "app.main.run", "client.get")) is None


# ---- self / cls ------------------------------------------------------------------------------------------


def test_self_and_cls_calls_resolve_within_the_enclosing_class(tmp_path):
    by_id, resolved = _resolve(tmp_path, {
        "app/svc.py": (
            "class Service:\n"
            "    def helper(self):\n        pass\n\n"
            "    @classmethod\n    def make(cls):\n        return cls.build()\n\n"
            "    @classmethod\n    def build(cls):\n        pass\n\n"
            "    def run(self):\n        self.helper()\n        self.missing()\n"
        ),
    })
    assert _target_qn(by_id, _only(resolved, by_id, "Service.run", "self.helper")) == "app.svc.Service.helper"
    assert _target_qn(by_id, _only(resolved, by_id, "Service.make", "cls.build")) == "app.svc.Service.build"
    missing = _only(resolved, by_id, "Service.run", "self.missing")
    assert missing.target_id is None  # not a method of the class or its bases


def test_self_call_resolves_to_inherited_method_across_files(tmp_path):
    by_id, resolved = _resolve(tmp_path, {
        "lib/base.py": "class Base:\n    def shared(self):\n        pass\n",
        "app/child.py": "from lib.base import Base\n\nclass Child(Base):\n    def go(self):\n        self.shared()\n",
    })
    inherit = next(r for r in resolved if r.relationship_type == RelationshipType.INHERITS)
    assert _target_qn(by_id, inherit) == "lib.base.Base"
    call = _only(resolved, by_id, "Child.go", "self.shared")
    assert _target_qn(by_id, call) == "lib.base.Base.shared"
    assert call.confidence == 0.85  # inherited member, below an own-class member


def test_same_name_method_in_unrelated_class_is_not_used_for_self_call(tmp_path):
    by_id, resolved = _resolve(tmp_path, {
        "app/a.py": "class A:\n    def go(self):\n        self.ping()\n",
        "app/b.py": "class B:\n    def ping(self):\n        pass\n",
    })
    assert _only(resolved, by_id, "A.go", "self.ping").target_id is None


# ---- imports, aliases, relative imports, re-exports ------------------------------------------------------


def test_imported_function_resolves_to_the_definition_not_the_import_statement(tmp_path):
    by_id, resolved = _resolve(tmp_path, {
        "pkg/util.py": "def helper(x):\n    return x\n",
        "app/main.py": "from pkg.util import helper\n\ndef go():\n    helper(1)\n",
    })
    call = _only(resolved, by_id, "app.main.go", "helper")
    assert _target_qn(by_id, call) == "pkg.util.helper"
    assert by_id[call.target_id].symbol_type == SymbolType.FUNCTION
    assert call.confidence == 0.9


def test_import_aliases_resolve(tmp_path):
    by_id, resolved = _resolve(tmp_path, {
        "pkg/util.py": "def helper(x):\n    return x\n",
        "app/main.py": (
            "from pkg.util import helper as h\nimport pkg.util as u\n\n"
            "def go():\n    h(1)\n    u.helper(2)\n"
        ),
    })
    assert _target_qn(by_id, _only(resolved, by_id, "app.main.go", "h")) == "pkg.util.helper"
    assert _target_qn(by_id, _only(resolved, by_id, "app.main.go", "u.helper")) == "pkg.util.helper"


def test_relative_imports_resolve(tmp_path):
    by_id, resolved = _resolve(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/util.py": "def helper(x):\n    return x\n",
        "pkg/main.py": "from . import util\nfrom .util import helper\n\ndef go():\n    util.helper(1)\n    helper(2)\n",
    })
    assert _target_qn(by_id, _only(resolved, by_id, "pkg.main.go", "util.helper")) == "pkg.util.helper"
    assert _target_qn(by_id, _only(resolved, by_id, "pkg.main.go", "helper")) == "pkg.util.helper"


def test_reexport_through_package_init_is_followed(tmp_path):
    by_id, resolved = _resolve(tmp_path, {
        "src/pkg/__init__.py": "from .impl import thing as thing\n",
        "src/pkg/impl.py": "def thing():\n    pass\n",
        "tests/test_it.py": "import pkg\nfrom pkg import thing\n\ndef test_x():\n    thing()\n    pkg.thing()\n",
    })
    assert _target_qn(by_id, _only(resolved, by_id, "tests.test_it.test_x", "thing")) == "src.pkg.impl.thing"
    assert _target_qn(by_id, _only(resolved, by_id, "tests.test_it.test_x", "pkg.thing")) == "src.pkg.impl.thing"


def test_stdlib_import_is_not_bound_to_a_repository_package_of_the_same_name(tmp_path):
    # The repo has its own `app/json` package; `import json` in a sibling module is the stdlib one.
    by_id, resolved = _resolve(tmp_path, {
        "app/__init__.py": "",
        "app/json/__init__.py": "def dumps(x):\n    return x\n",
        "app/other.py": "import json\n\ndef go(x):\n    json.dumps(x)\n",
    })
    assert _only(resolved, by_id, "app.other.go", "json.dumps").target_id is None


def test_name_imported_from_outside_the_repo_is_never_rescued_by_a_same_named_repo_symbol(tmp_path):
    by_id, resolved = _resolve(tmp_path, {
        "internal/redirect.py": "def redirect(x):\n    return x\n",
        "app/main.py": "from werkzeug.utils import redirect\n\ndef go():\n    redirect('/')\n",
    })
    assert _only(resolved, by_id, "app.main.go", "redirect").target_id is None


def test_external_base_class_is_not_replaced_by_unrelated_repo_class_of_same_name(tmp_path):
    by_id, resolved = _resolve(tmp_path, {
        "internal/models.py": "class Base:\n    pass\n",
        "app/main.py": "from sqlalchemy.orm import Base\n\nclass Model(Base):\n    pass\n",
    })
    inherit = next(r for r in resolved if r.relationship_type == RelationshipType.INHERITS
                   and by_id[r.source_id].name == "Model")
    assert inherit.target_id is None


# ---- same module / lexical scope / ambiguity -------------------------------------------------------------


def test_same_module_nested_and_recursive_calls_resolve(tmp_path):
    by_id, resolved = _resolve(tmp_path, {
        "app/mod.py": (
            "def top():\n    pass\n\n"
            "def outer():\n"
            "    def inner():\n        pass\n"
            "    inner()\n    top()\n    outer()\n"
        ),
    })
    assert _target_qn(by_id, _only(resolved, by_id, "app.mod.outer", "inner")) == "app.mod.outer.inner"
    assert _target_qn(by_id, _only(resolved, by_id, "app.mod.outer", "top")) == "app.mod.top"
    assert _target_qn(by_id, _only(resolved, by_id, "app.mod.outer", "outer")) == "app.mod.outer"


def test_class_scope_is_not_visible_to_bare_names_in_python_methods(tmp_path):
    by_id, resolved = _resolve(tmp_path, {
        "app/mod.py": "class K:\n    def helper(self):\n        pass\n    def run(self):\n        helper()\n",
    })
    assert _only(resolved, by_id, "K.run", "helper").target_id is None


def test_ambiguous_definitions_stay_unresolved(tmp_path):
    by_id, resolved = _resolve(tmp_path, {
        "app/mod.py": (
            "if True:\n    def pick():\n        return 1\nelse:\n    def pick():\n        return 2\n\n"
            "def go():\n    pick()\n"
        ),
    })
    call = _only(resolved, by_id, "app.mod.go", "pick")
    assert call.target_id is None
    assert call.confidence == 0.3  # ambiguous marker, not a guess


# ---- other languages -------------------------------------------------------------------------------------


def test_java_same_package_class_and_explicit_import_resolve(tmp_path):
    by_id, resolved = _resolve(tmp_path, {
        "src/main/java/com/acme/app/Main.java": (
            "package com.acme.app;\nimport com.acme.util.Tool;\n"
            "public class Main {\n  void go() {\n    new Helper();\n    new Tool();\n    this.local();\n    other.run();\n  }\n"
            "  void local() {}\n}\n"
        ),
        "src/main/java/com/acme/app/Helper.java": "package com.acme.app;\npublic class Helper {}\n",
        "src/main/java/com/acme/util/Tool.java": "package com.acme.util;\npublic class Tool {}\n",
    }, parser=JavaParser())
    assert _target_qn(by_id, _only(resolved, by_id, "Main.go", "Helper")).endswith("com.acme.app.Helper.Helper")
    assert _target_qn(by_id, _only(resolved, by_id, "Main.go", "Tool")).endswith("com.acme.util.Tool.Tool")
    assert _target_qn(by_id, _only(resolved, by_id, "Main.go", "this.local")).endswith("Main.local")
    assert _only(resolved, by_id, "Main.go", "other.run").target_id is None  # unknown receiver


def test_javascript_relative_import_makes_that_modules_definitions_visible(tmp_path):
    by_id, resolved = _resolve(tmp_path, {
        "web/util.js": "export function helper() {}\n",
        "web/main.js": "import { helper } from './util';\nexport function go() {\n  helper();\n  unknown();\n}\n",
    }, parser=JavaScriptParser())
    call = _only(resolved, by_id, "web.main.go", "helper")
    assert _target_qn(by_id, call) == "web.util.helper"
    assert call.confidence == 0.8
    assert _only(resolved, by_id, "web.main.go", "unknown").target_id is None


def test_cpp_this_receiver_resolves_to_class_member(tmp_path):
    by_id, resolved = _resolve(tmp_path, {
        "src/svc.cpp": (
            "class Service {\n public:\n  void helper() {}\n  void run() { this->helper(); other.helper(); }\n};\n"
        ),
    }, parser=CppParser())
    assert _target_qn(by_id, _only(resolved, by_id, "Service.run", "this.helper")).endswith("Service.helper")
    assert _only(resolved, by_id, "Service.run", "other.helper").target_id is None


# ---- parser-side evidence the resolver depends on --------------------------------------------------------


def test_python_import_symbols_record_local_name_and_resolved_bound_path(tmp_path):
    parser = PythonParser()
    pkg = tmp_path / "pkg" / "sub"
    pkg.mkdir(parents=True)
    (pkg / "mod.py").write_text(
        "import a.b\nimport c.d as e\nfrom x.y import z\nfrom x.y import w as v\nfrom . import sib\nfrom ..up import thing\n",
        encoding="utf-8",
    )
    pf = parser.parse_file(pkg / "mod.py", tmp_path)
    imports = {s.name: (s.local_name, s.bound_path) for s in pf.symbols if s.symbol_type == SymbolType.IMPORT}
    assert imports["a.b"] == ("a", "a")
    assert imports["c.d"] == ("e", "c.d")
    assert imports["x.y.z"] == ("z", "x.y.z")
    assert imports["x.y.w"] == ("v", "x.y.w")
    assert imports["..sib"] == ("sib", "pkg.sub.sib")
    assert imports["..up.thing"] == ("thing", "pkg.up.thing")


def test_python_from_import_emits_one_import_symbol_per_imported_name(tmp_path):
    parser = PythonParser()
    (tmp_path / "m.py").write_text("from flask.helpers import url_for\n", encoding="utf-8")
    pf = parser.parse_file(tmp_path / "m.py", tmp_path)
    names = [s.name for s in pf.symbols if s.symbol_type == SymbolType.IMPORT]
    assert names == ["flask.helpers.url_for"]  # previously also emitted a bogus "flask.helpers.flask.helpers"
