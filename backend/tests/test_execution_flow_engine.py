from analysis.execution_flow.engine import (
    _build_children,
    _build_proposed_tree,
    _component_maps,
    _leaf_terminal_reason,
    _layer_skip_pairs,
    _terminal_kind_for,
)
from analysis.execution_flow.models import FlowHop
from analysis.reconstruction.models import ArchitectureComponent, ArchitectureModel, ComponentRelationship


def _component(id_, role, files):
    return ArchitectureComponent(
        id=id_, name=id_, role=role, file_count=len(files), symbol_count=len(files), files=files,
        confidence=0.8, confidence_label="Confirmed", evidence=[],
    )


def test_terminal_kind_flags_data_access_component():
    model = ArchitectureModel(
        repo_id="r1",
        components=[_component("app/data", "data_access", ["app/data/repo.py"])],
        relationships=[], truncated=False,
    )
    file_to_component, role_by_component = _component_maps(model)
    meta = {"sym1": ("Foo.find", "app/data/repo.py")}
    assert _terminal_kind_for("sym1", meta, file_to_component, role_by_component) == "database"


def test_terminal_kind_none_for_service_component():
    model = ArchitectureModel(
        repo_id="r1", components=[_component("app/services", "service", ["app/services/svc.py"])],
        relationships=[], truncated=False,
    )
    file_to_component, role_by_component = _component_maps(model)
    meta = {"sym1": ("Foo.run", "app/services/svc.py")}
    assert _terminal_kind_for("sym1", meta, file_to_component, role_by_component) is None


def test_build_children_labels_role_but_does_not_stop_traversal_there():
    """A callee classified data_access still gets its architecture role
    attached (terminal_kind) but traversal only actually stops where there
    really is no further resolved evidence -- here "db" genuinely has no
    outgoing calls in `adjacency`, so it's a leaf for that reason, not
    because of its role."""
    model = ArchitectureModel(
        repo_id="r1",
        components=[
            _component("app/api", "api", ["app/api/controller.py"]),
            _component("app/data", "data_access", ["app/data/repo.py"]),
        ],
        relationships=[], truncated=False,
    )
    file_to_component, role_by_component = _component_maps(model)
    component_name_by_id = {c.id: c.name for c in model.components}
    meta = {
        "entry": ("Controller.handle", "app/api/controller.py"),
        "db": ("Repo.find", "app/data/repo.py"),
        "other": ("Controller.helper", "app/api/controller.py"),
    }
    adjacency = {
        "entry": [("other", 0.5, "controller.py", 5), ("db", 0.9, "controller.py", 6)],
    }
    budget = [100]
    children, reason, omitted = _build_children(
        "entry", "Controller.handle", 0, frozenset({"entry"}), adjacency, meta,
        file_to_component, role_by_component, budget, component_name_by_id,
    )

    assert reason is None  # "entry" itself has children, so it isn't terminal
    assert omitted == 0
    assert [c.callee_uid for c in children] == ["db", "other"]  # highest confidence first
    db_hop = next(c for c in children if c.callee_uid == "db")
    assert db_hop.terminal_kind == "database"  # still labeled with its architecture role
    assert db_hop.terminal_reason == "NO_RESOLVED_CALLEES"  # but stopped for evidence reasons, not role
    assert db_hop.children == []
    assert db_hop.callee_file_path == "app/data/repo.py"
    assert db_hop.component_id == "app/data"
    assert db_hop.component_role == "data_access"
    assert db_hop.component_name == "app/data"


def test_build_children_traverses_through_external_integration_component():
    """TEST 1 (root-cause regression test): a component classified
    external_integration that DOES have further resolved calls within the
    same repository must still be traversed into -- this is exactly the
    pallets/flask bug (render_template -> deeper Flask internals) the fix
    addresses. Architectural role must never gate recursion on its own."""
    model = ArchitectureModel(
        repo_id="r1",
        components=[
            _component("examples/app", "api", ["examples/app/views.py"]),
            _component("src/flask", "external_integration", ["src/flask/templating.py"]),
        ],
        relationships=[], truncated=False,
    )
    file_to_component, role_by_component = _component_maps(model)
    component_name_by_id = {c.id: c.name for c in model.components}
    meta = {
        "view": ("views.index", "examples/app/views.py"),
        "render": ("templating.render_template", "src/flask/templating.py"),
        "deeper": ("templating._render", "src/flask/templating.py"),
    }
    adjacency = {
        "view": [("render", 0.75, "views.py", 10)],
        "render": [("deeper", 0.75, "templating.py", 50)],  # further resolved call INSIDE the same repo
    }
    budget = [100]
    children, _, _ = _build_children(
        "view", "views.index", 0, frozenset({"view"}), adjacency, meta,
        file_to_component, role_by_component, budget, component_name_by_id,
    )

    render_hop = children[0]
    assert render_hop.callee_uid == "render"
    assert render_hop.terminal_kind == "external_service"  # role is still reported...
    assert render_hop.children != []  # ...but traversal continued past it
    assert render_hop.children[0].callee_uid == "deeper"
    assert render_hop.terminal_reason is None  # not terminal -- it has a child


def test_leaf_terminal_reason_no_unresolved_targets():
    assert _leaf_terminal_reason("sym1", {}, {}, {}, {}) == "NO_RESOLVED_CALLEES"


def test_leaf_terminal_reason_standard_library():
    """TEST 3: a call whose object prefix ("sqlite3") is both an actual
    import of the file AND a real Python stdlib module -> STANDARD_LIBRARY."""
    meta = {"sym1": ("get_db", "app/db.py")}
    languages = {"sym1": "python"}
    unresolved = {"sym1": ["sqlite3.connect"]}
    file_imports = {"app/db.py": ["sqlite3", "datetime"]}
    assert _leaf_terminal_reason("sym1", meta, languages, unresolved, file_imports) == "STANDARD_LIBRARY"


def test_leaf_terminal_reason_external_dependency():
    """TEST 2: a call whose object prefix is a real import but not stdlib -> EXTERNAL_DEPENDENCY."""
    meta = {"sym1": ("fetch_price", "app/pricing.py")}
    languages = {"sym1": "python"}
    unresolved = {"sym1": ["requests.get"]}
    file_imports = {"app/pricing.py": ["requests"]}
    assert _leaf_terminal_reason("sym1", meta, languages, unresolved, file_imports) == "EXTERNAL_DEPENDENCY"


def test_leaf_terminal_reason_unresolved_when_prefix_not_a_real_import():
    """TEST 4: a call target whose prefix ISN'T among the file's actual
    imports (e.g. a local variable like Flask's `g`) must not be guessed as
    a module -- it's genuinely unresolved, not a confirmed external call."""
    meta = {"sym1": ("get_db", "app/db.py")}
    languages = {"sym1": "python"}
    unresolved = {"sym1": ["g.pop"]}
    file_imports = {"app/db.py": ["sqlite3"]}  # "g" is not imported here
    assert _leaf_terminal_reason("sym1", meta, languages, unresolved, file_imports) == "UNRESOLVED"


def test_build_children_depth_limit_reason():
    """TEST 5."""
    adjacency = {"a": [("b", 1.0, "f.py", 1)], "b": [("c", 1.0, "f.py", 2)]}
    meta = {"a": ("A", "f.py"), "b": ("B", "f.py"), "c": ("C", "f.py")}
    budget = [100]
    children, _, _ = _build_children("a", "A", 4, frozenset({"a"}), adjacency, meta, {}, {}, budget)
    assert children[0].callee_uid == "b"
    assert children[0].children == []
    assert children[0].terminal_reason == "DEPTH_LIMIT"


def test_build_children_avoids_infinite_recursion_on_cycles():
    adjacency = {"a": [("b", 1.0, "f.py", 1)], "b": [("a", 1.0, "f.py", 2)]}
    meta = {"a": ("A.run", "f.py"), "b": ("B.run", "f.py")}
    budget = [100]
    children, _, _ = _build_children("a", "A.run", 0, frozenset({"a"}), adjacency, meta, {}, {}, budget)
    # b's call back to a must not recurse forever
    assert children[0].callee_uid == "b"
    assert all(c.callee_uid != "a" for c in children[0].children)


def test_build_children_respects_total_hop_budget():
    adjacency = {"a": [(f"n{i}", 1.0, "f.py", i) for i in range(10)]}
    meta = {f"n{i}": (f"N{i}", "f.py") for i in range(10)}
    budget = [2]
    children, _, _ = _build_children("a", "A", 0, frozenset({"a"}), adjacency, meta, {}, {}, budget)
    assert len(children) <= 2
    assert budget[0] == 0


def test_build_children_reports_branch_limit_omission():
    """TEST 6: more resolved calls exist than the per-hop branch cap allows
    -- the count must be disclosed on the parent hop, not silently dropped."""
    adjacency = {"a": [(f"n{i}", 1.0 - i * 0.01, "f.py", i) for i in range(6)]}
    meta = {f"n{i}": (f"N{i}", "f.py") for i in range(6)}
    budget = [100]
    children, reason, omitted = _build_children("a", "A", 0, frozenset({"a"}), adjacency, meta, {}, {}, budget)
    assert reason is None
    assert len(children) == 3  # _MAX_BRANCHES_PER_HOP
    assert omitted == 3  # the other 3 resolved calls exist but weren't included


def test_layer_skip_pairs_uses_largest_service_component():
    model = ArchitectureModel(
        repo_id="r1",
        components=[
            _component("app/api", "api", ["app/api/c.py"]),
            _component("app/data", "data_access", ["app/data/r.py"]),
            _component("app/services", "service", ["app/services/a.py", "app/services/b.py"]),
        ],
        relationships=[
            ComponentRelationship(
                source_id="app/api", target_id="app/data", call_count=2, confidence=0.9,
                confidence_label="Confirmed", evidence=["e.g. app/api/c.py:10"],
            )
        ],
        truncated=False,
    )
    pairs = _layer_skip_pairs(model)
    assert pairs.get(("app/api", "app/data")) == "app/services"


def test_build_proposed_tree_splices_service_hop_and_labels_it():
    file_to_component = {"app/api/c.py": "app/api", "app/data/r.py": "app/data"}
    meta = {"entry": ("Controller.handle", "app/api/c.py"), "db": ("Repo.find", "app/data/r.py")}
    skip_pairs = {("app/api", "app/data"): "PaymentService"}

    leaf = FlowHop(
        label="OBSERVED", caller_qualified_name="Controller.handle", callee_qualified_name="Repo.find",
        callee_uid="db", relationship_type="CALLS", source_file="app/data/r.py", source_line=10,
        confidence=0.9, terminal_kind="database", caller_uid="entry", children=[],
    )
    root = FlowHop(
        label="OBSERVED", caller_qualified_name="", callee_qualified_name="Controller.handle",
        callee_uid="entry", relationship_type="ENTRY", source_file="app/api/c.py", source_line=1,
        confidence=1.0, terminal_kind=None, caller_uid=None, children=[leaf],
    )

    proposed, spliced = _build_proposed_tree(root, meta, file_to_component, skip_pairs)
    assert spliced is True
    synthetic = proposed.children[0]
    assert synthetic.label == "PROPOSED"
    assert "PaymentService" in synthetic.callee_qualified_name
    assert synthetic.children[0].callee_uid == "db"  # the original call still happens, just after the bridge


def test_build_proposed_tree_no_splice_when_no_matching_pair():
    leaf = FlowHop(
        label="OBSERVED", caller_qualified_name="Controller.handle", callee_qualified_name="Service.run",
        callee_uid="svc", relationship_type="CALLS", source_file="app/api/c.py", source_line=10,
        confidence=0.9, terminal_kind=None, caller_uid="entry", children=[],
    )
    root = FlowHop(
        label="OBSERVED", caller_qualified_name="", callee_qualified_name="Controller.handle",
        callee_uid="entry", relationship_type="ENTRY", source_file="app/api/c.py", source_line=1,
        confidence=1.0, terminal_kind=None, caller_uid=None, children=[leaf],
    )
    _, spliced = _build_proposed_tree(root, {}, {}, {})
    assert spliced is False
