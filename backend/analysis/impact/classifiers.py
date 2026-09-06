"""Deterministic heuristics used to classify a dependent symbol.

None of these require full execution-flow/API-route reconstruction (that's
a separate, larger milestone) — they're pattern-matches over data we already
extract (decorators, naming convention, file path, import names), which is
enough to give an honest, evidence-based approximation. Every heuristic is
named so the UI can disclose exactly what rule fired.
"""
import re
import sys

_API_DECORATOR_RE = re.compile(
    r"\.(route|get|post|put|delete|patch|websocket)\s*\(|@api_view|@action\b"
    # NestJS/Angular-style bare route decorators (@Get('/x'), @Post(), ...) --
    # no dot-access, since the decorator itself IS the route registration.
    r"|@(get|post|put|delete|patch|all)\s*\(",
    re.IGNORECASE,
)

_SERVICE_SUFFIXES = ("Service", "Repository", "Controller", "Manager", "Client", "Gateway", "Handler")

_DB_PACKAGE_PREFIXES = {
    # Python
    "sqlalchemy", "django", "psycopg2", "pymongo", "redis", "sqlite3", "peewee",
    "tortoise", "asyncpg", "pymysql", "sqlmodel", "mongoengine", "sqlalchemy_utils",
    # JavaScript / Node.js -- classify_import is language-agnostic (it only looks
    # at the raw import string), so the same function serves both parsers.
    "pg", "mongoose", "mysql2", "sequelize", "knex", "prisma", "ioredis", "typeorm",
}

_STDLIB_MODULES = set(sys.stdlib_module_names)

# Node.js built-in modules -- the JS equivalent of Python's stdlib exclusion,
# so `require('fs')` isn't misclassified as an external service dependency.
_NODE_BUILTIN_MODULES = {
    "fs", "path", "http", "https", "crypto", "os", "url", "events", "stream",
    "util", "child_process", "net", "querystring", "assert", "buffer", "zlib",
    "readline", "process", "cluster", "dns", "tls", "worker_threads", "timers",
}


def is_api_endpoint(decorators: list[str]) -> bool:
    """A function/method decorated with a common web-framework route decorator."""
    return any(_API_DECORATOR_RE.search(d) for d in decorators)


def is_service_component(qualified_name: str, symbol_type: str) -> bool:
    """A class (or a method on one) whose name follows a service-layer naming
    convention (FooService, FooRepository, ...) — the same convention
    CLAUDE.md's own examples use (PaymentService, TransactionRepository)."""
    parts = qualified_name.split(".")
    if symbol_type == "class":
        candidate = parts[-1] if parts else ""
    elif symbol_type == "method":
        candidate = parts[-2] if len(parts) >= 2 else ""
    else:
        return False
    return candidate.endswith(_SERVICE_SUFFIXES)


def is_test(file_path: str, name: str) -> bool:
    """Same heuristic the smell detector uses: test-path or test_-prefixed name."""
    return "test" in file_path.lower() or name.startswith("test_")


def classify_import(dotted_name: str) -> str | None:
    """Categorize a raw import target as 'database', 'external_service', or
    None (stdlib / not externally interesting)."""
    top_level = dotted_name.split(".")[0]
    if top_level in _DB_PACKAGE_PREFIXES:
        return "database"
    if top_level in _STDLIB_MODULES or top_level in _NODE_BUILTIN_MODULES:
        return None
    if not top_level or top_level.startswith("_"):
        return None
    return "external_service"
