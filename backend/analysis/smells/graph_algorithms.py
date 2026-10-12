"""Pure graph algorithms with no Neo4j dependency, so they're independently testable."""

# A cycle path longer than this is not worth returning in full -- the point
# is "here is a concrete, followable example," not an exhaustive trace, and
# an unbounded DFS on a pathological SCC could otherwise take a while.
_MAX_CYCLE_PATH_LENGTH = 20


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


def find_cycle_path(adjacency: dict[str, list[str]], members: set[str]) -> list[str] | None:
    """One concrete, explicit cycle within an already-known SCC -- e.g.
    [A, B, C, A] -- rather than only the unordered member set.

    A strongly connected component can contain multiple actual cycles (any
    two members are mutually reachable, but not necessarily via a single
    simple loop); this returns *one* real simple cycle that exists in the
    graph, found via DFS restricted to `members`. This is a static fact
    about the CALLS graph, not a runtime execution order.

    Deterministic: both the starting node and each node's neighbor list are
    sorted before traversal, so the same member set (the only thing that can
    vary is *how* Kosaraju's algorithm above visits it, e.g. due to Neo4j
    row ordering) always yields the same returned path, regardless of
    adjacency dict insertion order.

    Returns None if no simple cycle within `_MAX_CYCLE_PATH_LENGTH` hops is
    found (e.g. a pathologically large/tangled SCC) -- callers must
    represent that as an explicit limitation, never silently drop it.
    """
    start = min(members)
    path: list[str] = [start]
    on_path = {start}

    def dfs(node: str) -> list[str] | None:
        if len(path) > _MAX_CYCLE_PATH_LENGTH:
            return None
        for neighbor in sorted(adjacency.get(node, [])):
            if neighbor not in members:
                continue
            if neighbor == start and len(path) > 1:
                return [*path, start]
            if neighbor in on_path:
                continue
            path.append(neighbor)
            on_path.add(neighbor)
            result = dfs(neighbor)
            if result is not None:
                return result
            path.pop()
            on_path.discard(neighbor)
        return None

    return dfs(start)
