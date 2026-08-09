from analysis.smells.graph_algorithms import strongly_connected_components


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
