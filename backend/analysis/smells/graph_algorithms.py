"""Pure graph algorithms with no Neo4j dependency, so they're independently testable."""


def strongly_connected_components(adjacency: dict[str, list[str]]) -> list[list[str]]:
    """Kosaraju's algorithm, iterative (no recursion-depth risk on large graphs).

    Returns every strongly connected component, including singletons — callers
    filter for size > 1 to find actual cycles.
    """
    nodes: set[str] = set(adjacency.keys())
    for targets in adjacency.values():
        nodes.update(targets)

    visited: set[str] = set()
    finish_order: list[str] = []

    for start in nodes:
        if start in visited:
            continue
        stack: list[tuple[str, iter]] = [(start, iter(adjacency.get(start, [])))]
        visited.add(start)
        while stack:
            node, neighbors = stack[-1]
            advanced = False
            for nxt in neighbors:
                if nxt not in visited:
                    visited.add(nxt)
                    stack.append((nxt, iter(adjacency.get(nxt, []))))
                    advanced = True
                    break
            if not advanced:
                finish_order.append(node)
                stack.pop()

    reverse_adjacency: dict[str, list[str]] = {}
    for u, targets in adjacency.items():
        for v in targets:
            reverse_adjacency.setdefault(v, []).append(u)

    visited2: set[str] = set()
    components: list[list[str]] = []
    for node in reversed(finish_order):
        if node in visited2:
            continue
        stack = [node]
        visited2.add(node)
        component = []
        while stack:
            n = stack.pop()
            component.append(n)
            for nb in reverse_adjacency.get(n, []):
                if nb not in visited2:
                    visited2.add(nb)
                    stack.append(nb)
        components.append(component)

    return components
