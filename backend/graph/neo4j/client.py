"""Single shared Neo4j driver instance. Every graph module goes through this —
nothing else opens its own connection.
"""
from functools import lru_cache

from neo4j import Driver, GraphDatabase

from app.core.config import settings


@lru_cache(maxsize=1)
def get_driver() -> Driver:
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )


def verify_connectivity() -> bool:
    try:
        get_driver().verify_connectivity()
        return True
    except Exception:
        return False
