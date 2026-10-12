from analysis.smells.graph_algorithms import find_cycle_path, strongly_connected_components


def test_detects_simple_two_node_cycle():
    adjacency = {"A": ["B"], "B": ["A"]}
    components = strongly_connected_components(adjacency)
    cycles = [c for c in components if len(c) > 1]
    assert len(cycles) == 1
    assert set(cycles[0]) == {"A", "B"}


def test_no_false_positive_on_dag():
    adjacency = {"A": ["B"], "B": ["C"], "C": []}
    components = strongly_connected_components(adjacency)
    assert all(len(c) == 1 for c in components)


def test_three_node_cycle_grouped_together():
    adjacency = {"A": ["B"], "B": ["C"], "C": ["A"]}
    components = strongly_connected_components(adjacency)
    cycles = [c for c in components if len(c) > 1]
    assert len(cycles) == 1
    assert set(cycles[0]) == {"A", "B", "C"}


def test_disjoint_cycle_and_chain_are_separate_components():
    adjacency = {"A": ["B"], "B": ["A"], "X": ["Y"], "Y": ["Z"], "Z": []}
    components = strongly_connected_components(adjacency)
    cycles = [c for c in components if len(c) > 1]
    assert len(cycles) == 1
    assert set(cycles[0]) == {"A", "B"}


# --- find_cycle_path (Architecture Analysis V2 §7: explicit cycle evidence) -


def test_find_cycle_path_returns_the_two_node_cycle():
    adjacency = {"A": ["B"], "B": ["A"]}
    path = find_cycle_path(adjacency, {"A", "B"})
    assert path == ["A", "B", "A"]


def test_find_cycle_path_returns_a_three_node_cycle_starting_from_the_smallest_member():
    adjacency = {"A": ["B"], "B": ["C"], "C": ["A"]}
    path = find_cycle_path(adjacency, {"A", "B", "C"})
    assert path is not None
    assert path[0] == path[-1] == "A"  # deterministic start: min(members)
    assert set(path[:-1]) == {"A", "B", "C"}
    # Every consecutive pair in the returned path must be a real edge.
    for a, b in zip(path, path[1:]):
        assert b in adjacency.get(a, [])


def test_find_cycle_path_is_deterministic_across_repeated_calls():
    adjacency = {"C": ["A"], "A": ["B", "C"], "B": ["A"]}
    members = {"A", "B", "C"}
    results = {tuple(find_cycle_path(adjacency, members)) for _ in range(5)}
    assert len(results) == 1


def test_find_cycle_path_ignores_edges_leaving_the_member_set():
    adjacency = {"A": ["B", "Z"], "B": ["A"], "Z": ["A"]}
    path = find_cycle_path(adjacency, {"A", "B"})
    assert path == ["A", "B", "A"]
    assert "Z" not in path
