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
    r"|@(get|post|put|delete|patch|all)\s*\("
    # Spring (Java/Kotlin) annotations: @GetMapping, @PostMapping, @RequestMapping, ...
    r"|@(get|post|put|delete|patch|request)mapping\b",
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

# Java's reversed-domain import convention (java.sql.*, org.hibernate.*, ...)
# means the *first* segment alone (java/javax/org/com) is too generic to
# classify -- these are matched against the first two dotted segments instead.
_DB_PACKAGE_TWO_SEGMENT_PREFIXES = {
    "java.sql", "javax.persistence", "org.hibernate", "org.mybatis",
    "com.mongodb", "redis.clients", "org.jooq",
}

_STDLIB_MODULES = set(sys.stdlib_module_names)

# Node.js built-in modules -- the JS equivalent of Python's stdlib exclusion,
# so `require('fs')` isn't misclassified as an external service dependency.
_NODE_BUILTIN_MODULES = {
    "fs", "path", "http", "https", "crypto", "os", "url", "events", "stream",
    "util", "child_process", "net", "querystring", "assert", "buffer", "zlib",
    "readline", "process", "cluster", "dns", "tls", "worker_threads", "timers",
}

# Java standard/platform namespaces -- the JDK equivalent of Python's stdlib
# exclusion (checked only when a two-segment DB prefix above didn't already
# match, so e.g. "javax.persistence" is still classified as "database").
_JAVA_STDLIB_PREFIXES = {"java", "javax"}


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
    parts = dotted_name.split(".")
    top_level = parts[0]
    top_two = ".".join(parts[:2]) if len(parts) >= 2 else top_level

    if top_level in _DB_PACKAGE_PREFIXES or top_two in _DB_PACKAGE_TWO_SEGMENT_PREFIXES:
        return "database"
    if top_level in _STDLIB_MODULES or top_level in _NODE_BUILTIN_MODULES or top_level in _JAVA_STDLIB_PREFIXES:
        return None
    if not top_level or top_level.startswith("_"):
        return None
    return "external_service"
