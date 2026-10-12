"""Declared-type evidence for receivers (Symbol.declared_types) and the resolver rules built on it.

Python and Java are driven through the real parsers. The central safety property throughout: a receiver is
bound only when its type resolves to exactly one repository class that has the method; everything else
(untyped, conflicting, external, ambiguous, shadowed, expression receivers) stays unresolved.
"""
from pathlib import Path

from parsing.ir.models import RelationshipType, SymbolType
from parsing.ir.resolver import resolve_relationships
from parsing.parsers.java.parser import JavaParser
from parsing.parsers.python.parser import PythonParser


def _resolve(tmp_path: Path, files: dict[str, str], parser):
    symbols, rels = [], []
    for rel_path, source in files.items():
        target = tmp_path / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
        pf = parser.parse_file(target, tmp_path)
        symbols += pf.symbols
        rels += pf.relationships
    return {s.id: s for s in symbols}, resolve_relationships(symbols, rels), symbols


def _py(tmp_path, files):
    return _resolve(tmp_path, files, PythonParser())


def _java(tmp_path, files):
    return _resolve(tmp_path, files, JavaParser())


def _call(resolved, by_id, caller_suffix, target_name):
    matches = [r for r in resolved if r.relationship_type == RelationshipType.CALLS
               and by_id[r.source_id].qualified_name.endswith(caller_suffix) and r.target_name == target_name]
    assert len(matches) == 1, (caller_suffix, target_name, [r.target_name for r in resolved if r.relationship_type == RelationshipType.CALLS])
    return matches[0]


def _qn(by_id, rel):
    return by_id[rel.target_id].qualified_name if rel.target_id else None


SVC = "class Service:\n    def run(self):\n        pass\n\n    def helper(self):\n        pass\n"


# ---- Python: what the parser records ----------------------------------------------------------------------


def test_python_declared_types_for_params_locals_fields_and_module_variables(tmp_path):
    _, _, symbols = _py(tmp_path, {"m.py": (
        "from typing import Optional\n"
        "cfg: Config = load()\napp = Flask(__name__)\n"
        "class Svc:\n    repo: Repo\n"
        "    def __init__(self, a: 'Repo2', b: Optional[Thing] = None, c=1, d: int | str = 0):\n"
        "        self.x = Foo()\n        self.y: Bar = make()\n        self.z = 1\n        self.z = Foo()\n"
        "    def run(self, k: Flask):\n        app = Flask(1)\n        j = other()\n        j = Foo()\n        for q in z: pass\n"
    )})
    types = {s.qualified_name: s.declared_types for s in symbols if s.declared_types}
    assert types["m"] == {"cfg": "Config", "app": "new:Flask"}
    assert types["m.Svc"] == {"repo": "Repo", "x": "new:Foo", "y": "Bar", "z": "?"}  # z: conflicting -> unknown
    assert types["m.Svc.__init__"]["a"] == "Repo2" and types["m.Svc.__init__"]["b"] == "Thing"  # quotes / Optional stripped
    assert types["m.Svc.__init__"]["c"] == "?" and types["m.Svc.__init__"]["d"] == "?"  # untyped / union
    assert "x" not in types["m.Svc.__init__"]  # `self.x = ...` binds no plain name
    run = types["m.Svc.run"]
    assert run["k"] == "Flask" and run["app"] == "new:Flask" and run["j"] == "?" and run["q"] == "?"


def test_python_self_field_method_target_keeps_the_field(tmp_path):
    by_id, resolved, _ = _py(tmp_path, {"m.py": "class A:\n    def go(self):\n        self.repo.save()\n        other().save()\n"})
    names = {r.target_name for r in resolved if r.relationship_type == RelationshipType.CALLS}
    assert "self.repo.save" in names and "?.save" in names


# ---- Python: resolution --------------------------------------------------------------------------------------


def test_annotated_parameter_resolves_to_the_declared_class_method(tmp_path):
    by_id, resolved, _ = _py(tmp_path, {
        "app/svc.py": SVC,
        "app/use.py": "from app.svc import Service\n\ndef go(s: Service):\n    s.run()\n    s.missing()\n",
    })
    call = _call(resolved, by_id, "app.use.go", "s.run")
    assert _qn(by_id, call) == "app.svc.Service.run" and call.confidence == 0.85
    assert _call(resolved, by_id, "app.use.go", "s.missing").target_id is None  # not a member of the class


def test_constructor_assignment_resolves_with_lower_confidence_and_through_aliases(tmp_path):
    by_id, resolved, _ = _py(tmp_path, {
        "pkg/svc.py": SVC,
        "app/use.py": "import pkg.svc as m\nfrom pkg.svc import Service as S\n\ndef go():\n    a = m.Service()\n    a.run()\n    b = S()\n    b.helper()\n",
    })
    assert _qn(by_id, _call(resolved, by_id, "app.use.go", "a.run")) == "pkg.svc.Service.run"
    call = _call(resolved, by_id, "app.use.go", "b.helper")
    assert _qn(by_id, call) == "pkg.svc.Service.helper" and call.confidence == 0.8


def test_constructor_of_a_function_is_not_a_class_and_stays_unresolved(tmp_path):
    by_id, resolved, _ = _py(tmp_path, {
        "app/mod.py": "def make():\n    pass\n\nclass K:\n    def run(self):\n        pass\n\ndef go():\n    x = make()\n    x.run()\n",
    })
    assert _call(resolved, by_id, "app.mod.go", "x.run").target_id is None


def test_conflicting_or_unknown_assignments_leave_the_receiver_unresolved(tmp_path):
    by_id, resolved, _ = _py(tmp_path, {
        "app/mod.py": SVC + "\ndef go(flag, other):\n    a = Service()\n    a = other\n    a.run()\n"
                            "    for b in other:\n        b.run()\n    c = Service()\n    c.run()\n",
    })
    assert _call(resolved, by_id, "app.mod.go", "a.run").target_id is None  # reassigned
    assert _call(resolved, by_id, "app.mod.go", "b.run").target_id is None  # loop variable
    assert _qn(by_id, _call(resolved, by_id, "app.mod.go", "c.run")) == "app.mod.Service.run"


def test_untyped_parameter_shadows_a_module_level_variable_of_the_same_name(tmp_path):
    by_id, resolved, _ = _py(tmp_path, {
        "app/mod.py": SVC + "\nsvc = Service()\n\ndef uses_global():\n    svc.run()\n\ndef shadowed(svc):\n    svc.run()\n",
    })
    assert _qn(by_id, _call(resolved, by_id, "app.mod.uses_global", "svc.run")) == "app.mod.Service.run"
    assert _call(resolved, by_id, "app.mod.shadowed", "svc.run").target_id is None


def test_self_field_with_declared_type_resolves_and_inherited_fields_are_found(tmp_path):
    by_id, resolved, _ = _py(tmp_path, {
        "lib/repo.py": "class Repo:\n    def save(self):\n        pass\n",
        "lib/base.py": "from lib.repo import Repo\n\nclass Base:\n    repo: Repo\n",
        "app/svc.py": (
            "from lib.repo import Repo\nfrom lib.base import Base\n\n"
            "class Svc(Base):\n    def __init__(self, other):\n        self.own = Repo()\n        self.dyn = other.thing()\n"
            "    def go(self):\n        self.own.save()\n        self.repo.save()\n        self.dyn.save()\n"
        ),
    })
    assert _qn(by_id, _call(resolved, by_id, "Svc.go", "self.own.save")) == "lib.repo.Repo.save"
    assert _qn(by_id, _call(resolved, by_id, "Svc.go", "self.repo.save")) == "lib.repo.Repo.save"  # field of base class
    assert _call(resolved, by_id, "Svc.go", "self.dyn.save").target_id is None  # unknown field type


def test_module_level_annotated_variable_is_followed_through_an_import(tmp_path):
    by_id, resolved, _ = _py(tmp_path, {
        "src/pkg/__init__.py": "",
        "src/pkg/app.py": "class Flask:\n    def url_for(self):\n        pass\n",
        "src/pkg/globals.py": "from .app import Flask\n\ncurrent_app: Flask = proxy()\n",
        "src/pkg/helpers.py": "from .globals import current_app\n\ndef go():\n    current_app.url_for()\n",
    })
    assert _qn(by_id, _call(resolved, by_id, "helpers.go", "current_app.url_for")) == "src.pkg.app.Flask.url_for"


def test_external_or_unresolvable_declared_types_stay_unresolved(tmp_path):
    by_id, resolved, _ = _py(tmp_path, {
        "internal/redirect.py": "class Response:\n    def send(self):\n        pass\n",
        "app/use.py": "from werkzeug.wrappers import Response\n\ndef go(r: Response, q: 'Nope', lst: list[Response]):\n    r.send()\n    q.send()\n    lst.send()\n",
    })
    assert _call(resolved, by_id, "app.use.go", "r.send").target_id is None  # imported from outside the repository
    assert _call(resolved, by_id, "app.use.go", "q.send").target_id is None  # no such class
    assert _call(resolved, by_id, "app.use.go", "lst.send").target_id is None  # generic container: not trusted


def test_nested_class_and_local_import_are_not_treated_as_untyped_variables(tmp_path):
    by_id, resolved, _ = _py(tmp_path, {
        "pkg/util.py": "def helper():\n    pass\n",
        "app/use.py": "def go():\n    class Local:\n        @staticmethod\n        def make():\n            pass\n    Local.make()\n"
                      "    from pkg import util\n    util.helper()\n",
    })
    assert _qn(by_id, _call(resolved, by_id, "app.use.go", "Local.make")) == "app.use.go.Local.make"
    assert _qn(by_id, _call(resolved, by_id, "app.use.go", "util.helper")) == "pkg.util.helper"


# ---- Java ----------------------------------------------------------------------------------------------------

OWNER = "package org.x.owner;\npublic class Owner extends Person {\n  public void addPet(Pet p) {}\n  public void setCity(String c) {}\n}\n"
PERSON = "package org.x.model;\npublic class Person {\n  public String getLastName() { return null; }\n  public void setId(int id) {}\n}\n"


def test_java_declared_types_for_params_locals_fields_and_lambdas(tmp_path):
    _, _, symbols = _java(tmp_path, {"A.java": (
        "class A {\n  private final Repo repo; java.util.List<Pet> pets; Foo[] arr;\n"
        "  void m(Owner o, int k, Page<Owner> pg) {\n    Pet p = new Pet(); var q = new Vet<>(); var w = make();\n"
        "    for (Pet x : pets) {}\n    lam(z -> z.k());\n    String repo = \"shadow\";\n  }\n}\n"
    )})
    types = {s.qualified_name: s.declared_types for s in symbols if s.declared_types}
    assert types["A.A"]["repo"] == "Repo" and types["A.A"]["pets"] == "java.util.List" and types["A.A"]["arr"] == "?"
    m = types["A.A.m"]
    assert m["o"] == "Owner" and m["pg"] == "Page" and m["k"] == "?"
    assert m["p"] == "Pet" and m["q"] == "new:Vet" and m["w"] == "?" and m["x"] == "Pet"
    assert m["z"] == "?" and m["repo"] == "String"  # lambda parameter, and a local that shadows the field


def test_java_typed_local_parameter_and_inherited_method_resolve_across_packages(tmp_path):
    by_id, resolved, _ = _java(tmp_path, {
        "src/main/java/org/x/owner/Owner.java": OWNER.replace("package org.x.owner;", "package org.x.owner;\nimport org.x.model.Person;"),
        "src/main/java/org/x/model/Person.java": PERSON,
        "src/main/java/org/x/owner/Controller.java": (
            "package org.x.owner;\npublic class Controller {\n  void go(Owner owner) {\n    owner.addPet(null);\n    owner.getLastName();\n"
            "    Owner local = new Owner();\n    local.setCity(\"x\");\n    local.setId(1);\n    owner.nothing();\n  }\n}\n"
        ),
    })
    assert _qn(by_id, _call(resolved, by_id, "Controller.go", "owner.addPet")).endswith("owner.Owner.Owner.addPet")
    inherited = _call(resolved, by_id, "Controller.go", "owner.getLastName")
    assert _qn(by_id, inherited).endswith("model.Person.Person.getLastName") and inherited.confidence == 0.8  # 0.85 - inherited
    assert _qn(by_id, _call(resolved, by_id, "Controller.go", "local.setCity")).endswith("Owner.Owner.setCity")
    assert _call(resolved, by_id, "Controller.go", "owner.nothing").target_id is None


def test_java_same_package_visibility_spans_source_roots(tmp_path):
    by_id, resolved, _ = _java(tmp_path, {
        "src/main/java/org/x/owner/Owner.java": OWNER.replace("extends Person ", ""),
        "src/test/java/org/x/owner/OwnerTests.java": (
            "package org.x.owner;\npublic class OwnerTests {\n  private Owner shared;\n  void t() {\n    Owner o = new Owner();\n    o.setCity(\"x\");\n    shared.addPet(null);\n  }\n}\n"
        ),
    })
    ctor = _call(resolved, by_id, "OwnerTests.t", "Owner")
    assert _qn(by_id, ctor).endswith("src.main.java.org.x.owner.Owner.Owner")
    assert _qn(by_id, _call(resolved, by_id, "OwnerTests.t", "o.setCity")).endswith("Owner.Owner.setCity")
    assert _qn(by_id, _call(resolved, by_id, "OwnerTests.t", "shared.addPet")).endswith("Owner.Owner.addPet")


def test_java_this_field_calls_use_the_field_type_and_unknown_receivers_stay_unresolved(tmp_path):
    by_id, resolved, _ = _java(tmp_path, {
        "src/main/java/org/x/Repo.java": "package org.x;\npublic class Repo {\n  public void save() {}\n}\n",
        "src/main/java/org/x/Svc.java": (
            "package org.x;\npublic class Svc {\n  private final Repo repo;\n  private final Missing ext;\n"
            "  void go(Object o) {\n    this.repo.save();\n    repo.save();\n    this.ext.save();\n    o.save();\n    other().save();\n  }\n}\n"
        ),
    })
    assert _qn(by_id, _call(resolved, by_id, "Svc.go", "this.repo.save")).endswith("Repo.Repo.save")
    assert _qn(by_id, _call(resolved, by_id, "Svc.go", "repo.save")).endswith("Repo.Repo.save")  # bare field receiver
    assert _call(resolved, by_id, "Svc.go", "this.ext.save").target_id is None  # type not in the repository
    assert _call(resolved, by_id, "Svc.go", "o.save").target_id is None  # Object is not a repository class


def test_java_lambda_parameter_and_local_shadow_a_field_of_the_same_name(tmp_path):
    by_id, resolved, _ = _java(tmp_path, {
        "src/main/java/org/x/Repo.java": "package org.x;\npublic class Repo {\n  public void save() {}\n}\n",
        "src/main/java/org/x/Svc.java": (
            "package org.x;\npublic class Svc {\n  private Repo repo;\n"
            "  void a() { run(repo -> repo.save()); }\n  void b() { String repo = \"\"; repo.save(); }\n  void c() { repo.save(); }\n}\n"
        ),
    })
    assert _call(resolved, by_id, "Svc.a", "repo.save").target_id is None
    assert _call(resolved, by_id, "Svc.b", "repo.save").target_id is None
    assert _qn(by_id, _call(resolved, by_id, "Svc.c", "repo.save")).endswith("Repo.Repo.save")


def test_java_overloaded_methods_stay_ambiguous(tmp_path):
    by_id, resolved, _ = _java(tmp_path, {
        "src/main/java/org/x/Box.java": "package org.x;\npublic class Box {\n  public void put(int a) {}\n  public void put(String a) {}\n}\n",
        "src/main/java/org/x/Use.java": "package org.x;\npublic class Use {\n  void go(Box b) { b.put(1); }\n}\n",
    })
    call = _call(resolved, by_id, "Use.go", "b.put")
    assert call.target_id is None and call.confidence == 0.3


def test_diamond_constructor_resolves_to_the_class(tmp_path):
    by_id, resolved, _ = _java(tmp_path, {
        "src/main/java/org/x/Box.java": "package org.x;\npublic class Box<T> {\n  public void put(T a) {}\n}\n",
        "src/main/java/org/x/Use.java": "package org.x;\npublic class Use {\n  void go() { var b = new Box<>(); b.put(1); }\n}\n",
    })
    assert _qn(by_id, _call(resolved, by_id, "Use.go", "Box<>")).endswith("Box.Box")
    assert _qn(by_id, _call(resolved, by_id, "Use.go", "b.put")).endswith("Box.Box.put")


def test_no_short_name_fallback_was_reintroduced(tmp_path):
    # A uniquely-named method must NOT be bound just because no other class defines it.
    by_id, resolved, _ = _py(tmp_path, {
        "app/a.py": "class Only:\n    def unique_name(self):\n        pass\n",
        "app/b.py": "def go(thing):\n    thing.unique_name()\n    make().unique_name()\n",
    })
    assert _call(resolved, by_id, "app.b.go", "thing.unique_name").target_id is None
    assert _call(resolved, by_id, "app.b.go", "?.unique_name").target_id is None


def test_symbol_type_variable_is_never_created_for_declared_types(tmp_path):
    # declared_types is metadata on existing symbols; it must not introduce VARIABLE symbols into the graph.
    _, _, symbols = _py(tmp_path, {"m.py": "x: Foo = bar()\n\ndef f(a: Foo):\n    b = Foo()\n"})
    assert all(s.symbol_type != SymbolType.VARIABLE for s in symbols)
