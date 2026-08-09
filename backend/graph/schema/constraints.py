"""Neo4j schema: uniqueness constraints for the node types CodeSage writes.

`uid` (repo_id + repo-local symbol id) is the real primary key everywhere —
symbol ids from the parser are only unique within one repository.
"""
from graph.neo4j.client import get_driver

_CONSTRAINTS = [
    "CREATE CONSTRAINT repository_id IF NOT EXISTS FOR (r:Repository) REQUIRE r.id IS UNIQUE",
    "CREATE CONSTRAINT symbol_uid IF NOT EXISTS FOR (s:Symbol) REQUIRE s.uid IS UNIQUE",
]


def ensure_schema() -> None:
    with get_driver().session() as session:
        for stmt in _CONSTRAINTS:
            session.run(stmt)
