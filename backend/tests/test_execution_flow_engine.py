from analysis.execution_flow.engine import (
    _build_children,
    _build_proposed_tree,
    _component_maps,
    _layer_skip_pairs,
    _terminal_kind_for,
)
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


def test_build_children_stops_at_terminal_and_follows_confidence_order():
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
    children = _build_children(
        "entry", "Controller.handle", 0, frozenset({"entry"}), adjacency, meta,
        file_to_component, role_by_component, budget, component_name_by_id,
    )

    assert [c.callee_uid for c in children] == ["db", "other"]  # highest confidence first
    db_hop = next(c for c in children if c.callee_uid == "db")
    assert db_hop.terminal_kind == "database"
    assert db_hop.children == []  # traversal stops at a terminal
    assert db_hop.callee_file_path == "app/data/repo.py"
    assert db_hop.component_id == "app/data"
    assert db_hop.component_role == "data_access"
    assert db_hop.component_name == "app/data"


def test_build_children_avoids_infinite_recursion_on_cycles():
    adjacency = {"a": [("b", 1.0, "f.py", 1)], "b": [("a", 1.0, "f.py", 2)]}
    meta = {"a": ("A.run", "f.py"), "b": ("B.run", "f.py")}
    budget = [100]
    children = _build_children("a", "A.run", 0, frozenset({"a"}), adjacency, meta, {}, {}, budget)
    # b's call back to a must not recurse forever
    assert children[0].callee_uid == "b"
    assert all(c.callee_uid != "a" for c in children[0].children)


def test_build_children_respects_total_hop_budget():
    adjacency = {"a": [(f"n{i}", 1.0, "f.py", i) for i in range(10)]}
    meta = {f"n{i}": (f"N{i}", "f.py") for i in range(10)}
    budget = [2]
    children = _build_children("a", "A", 0, frozenset({"a"}), adjacency, meta, {}, {}, budget)
    assert len(children) <= 2
    assert budget[0] == 0


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
    from analysis.execution_flow.models import FlowHop

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
    from analysis.execution_flow.models import FlowHop

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
