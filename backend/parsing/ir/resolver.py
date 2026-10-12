"""Resolves CALLS/INHERITS relationship targets across the whole repository.

Parsers work one file at a time and can't know whether `Foo` in file B is the
`Foo` defined in file A, so they emit target_id=None + a raw target_name.
This runs once per repo, after every file is parsed, with the full symbol
table available -- the only place cross-file linking can happen correctly.

CALLS / INHERITS are bound only on *scope evidence*, never on a name merely
being unique in the repository (that rule bound `config.update(...)` to an
unrelated repository method called `update`):

  * `self.m()` / `cls.m()` / `this.m()`  -> member `m` of the enclosing class, then its
    resolved base classes (closest definition wins).
  * bare `f()`  -> nearest lexical scope (nested defs, module level; class scope too in
    languages with an implicit `this`), then a name bound by an import of the same file.
  * `X.m()` where X is a class or imported module/class that is visible by the same rules
    -> member `m`. Re-exports (`from .helpers import url_for` inside a package
    `__init__`) are followed a few hops.
  * Python absolute imports match repository paths only through a source root, i.e. the
    path prefix in front of the import path must not itself be a package. This is what
    keeps `import json` from binding to the repository's own `flask/json` package.
  * Java: a class in the same directory (= package) is visible without an import.
    JS/TS: a relative-specifier import makes that file's top-level definitions visible
    (their parsers record the module path only, not the imported names).
  * A receiver that is anything else (a local variable, a call result `?.m`, `a.b.m`) is
    NOT resolved: without type information there is no evidence of its target.

A name that an import binds to something outside the repository is external: it stays
unresolved and is never rescued by a name match. Several equally good candidates leave the
reference unresolved with the ambiguous marker (confidence 0.3), never a guess.

Confidence is the rule that produced the binding (not a probability):
  0.95 own-scope / own-class definition      0.90 import-bound definition
  0.85 member inherited from a base class    0.80 same-package / imported-module visibility
  0.75 INHERITS fallback: the only class repo-wide with that name (name-based)
Other relationship types (CONTAINS, IMPORTS) keep the original exact-qualified-name rule.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from parsing.ir.models import Relationship, RelationshipType, Symbol, SymbolType

_RESOLVABLE_TARGETS = {SymbolType.CLASS, SymbolType.FUNCTION, SymbolType.METHOD}
_IDENT = re.compile(r"^[A-Za-z_$][\w$]*$")

_SELF_NAMES = {"python": {"self", "cls"}, "javascript": {"this"}, "typescript": {"this"}, "java": {"this"}, "cpp": {"this"}}
# Languages where a bare call inside a method can name a member of the enclosing class.
_IMPLICIT_THIS = {"java", "cpp"}

CONF_SCOPE = 0.95
CONF_IMPORT = 0.90
CONF_INHERITED = 0.85
CONF_VISIBLE = 0.80
CONF_INHERITS_NAME_ONLY = 0.75
CONF_AMBIGUOUS = 0.3
CONF_UNRESOLVED_CAP = 0.35
_MAX_REEXPORT_HOPS = 3


@dataclass(frozen=True)
class _Found:
    """Result of looking a name up: a definition, a module (file) or nothing usable."""
    kind: str  # "def" | "module" | "ambiguous" | "external" | "none"
    ident: str | None = None
    confidence: float = 0.0


_NONE = _Found("none")
_EXTERNAL = _Found("external")
_AMBIGUOUS = _Found("ambiguous")


def _import_path(qualified_name: str, file_path: str, language: str = "") -> str:
    """Path as another file would write it in an import statement.

    Python: `pkg.__init__.f` is imported as `pkg.f`.
    Java: qualified names carry the file module twice (`com.acme.Tool.Tool`: file `Tool.java`, class
    `Tool`), whereas the import is `com.acme.Tool`.
    """
    if language == "java":
        module = file_path.rsplit(".", 1)[0].replace("/", ".")
        if qualified_name.startswith(module + "."):
            return module.rpartition(".")[0] + ("." if "." in module else "") + qualified_name[len(module) + 1:]
        return qualified_name
    if file_path.endswith("__init__.py"):
        parts = qualified_name.split(".")
        if "__init__" in parts:
            parts.remove("__init__")
        return ".".join(parts)
    return qualified_name


class _Index:
    def __init__(self, symbols: list[Symbol], relationships: list[Relationship]) -> None:
        self.by_id = {s.id: s for s in symbols}
        self.parent: dict[str, str] = {}
        for r in relationships:
            if r.relationship_type == RelationshipType.CONTAINS and r.target_id is not None:
                self.parent[r.target_id] = r.source_id

        self.children: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        self.def_table: dict[str, list[tuple[str, str]]] = defaultdict(list)  # last segment -> (import path, id)
        self.module_table: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self.module_by_qn: dict[str, str] = {}
        self.files_by_dir: dict[str, list[str]] = defaultdict(list)
        self.package_dirs: set[str] = set()
        self.imports_by_file: dict[str, list[Symbol]] = defaultdict(list)
        self.file_id_by_path: dict[str, str] = {}

        for s in symbols:
            if s.symbol_type in _RESOLVABLE_TARGETS:
                parent_id = self.parent.get(s.id)
                if parent_id is not None:
                    self.children[parent_id][s.name].append(s.id)
                path = _import_path(s.qualified_name, s.file_path, s.language.value)
                self.def_table[path.rsplit(".", 1)[-1]].append((path, s.id))
            elif s.symbol_type == SymbolType.FILE:
                self.file_id_by_path[s.file_path] = s.id
                path = _import_path(s.qualified_name, s.file_path)
                self.module_table[path.rsplit(".", 1)[-1]].append((path, s.id))
                self.module_by_qn[s.qualified_name] = s.id
                self.files_by_dir[s.file_path.rpartition("/")[0]].append(s.id)
                if s.file_path.endswith("__init__.py"):
                    self.package_dirs.add(path)
            elif s.symbol_type == SymbolType.IMPORT:
                self.imports_by_file[s.file_path].append(s)

        self.bases: dict[str, list[str]] = defaultdict(list)
        self._names_cache: dict[str, dict[str, str]] = {}
        self._modules_cache: dict[str, list[str]] = {}

    # ---- import evidence ---------------------------------------------------------------------
    def import_names(self, file_path: str) -> dict[str, str]:
        """local name -> dotted path it is bound to, for this file."""
        cached = self._names_cache.get(file_path)
        if cached is not None:
            return cached
        names: dict[str, str] = {}
        for imp in self.imports_by_file.get(file_path, []):
            if imp.local_name is not None and imp.bound_path:
                names[imp.local_name] = imp.bound_path
            elif imp.language.value == "java" and not imp.name.endswith("*"):
                names[imp.name.rsplit(".", 1)[-1]] = imp.name
        self._names_cache[file_path] = names
        return names

    def imported_modules(self, file_path: str) -> list[str]:
        """JS/TS: repository files named by relative import specifiers of this file."""
        cached = self._modules_cache.get(file_path)
        if cached is not None:
            return cached
        found: list[str] = []
        directory = file_path.rpartition("/")[0]
        for imp in self.imports_by_file.get(file_path, []):
            if imp.language.value not in ("javascript", "typescript") or not imp.name.startswith("."):
                continue
            segments = [seg for seg in directory.split("/") if seg]
            for seg in imp.name.split("/"):
                if seg == "..":
                    if segments:
                        segments.pop()
                elif seg not in (".", ""):
                    segments.append(seg)
            stem = "/".join(segments)
            for ext in (".js", ".jsx", ".mjs", ".ts", ".tsx"):
                if stem.endswith(ext):
                    stem = stem[: -len(ext)]
            base = stem.replace("/", ".")
            for candidate in (base, base + ".index"):
                file_id = self.module_by_qn.get(candidate)
                if file_id is not None and file_id not in found:
                    found.append(file_id)
                    break
        self._modules_cache[file_path] = found
        return found

    def _suffix_matches(self, wanted: str, table: dict[str, list[tuple[str, str]]]) -> list[str]:
        exact, suffix = [], []
        for path, ident in table.get(wanted.rsplit(".", 1)[-1], []):
            if path == wanted:
                exact.append(ident)
            elif path.endswith("." + wanted) and path[: -len(wanted) - 1] not in self.package_dirs:
                # An absolute import reaches the repository only through a source root; a
                # prefix that is itself a package would make this a *relative* location.
                suffix.append(ident)
        return exact or suffix

    def resolve_bound(self, bound: str, depth: int = 0) -> _Found:
        """Dotted import path -> repository definition or module (following re-exports)."""
        if depth > _MAX_REEXPORT_HOPS or not bound:
            return _NONE
        defs = self._suffix_matches(bound, self.def_table)
        if len(defs) == 1:
            return _Found("def", defs[0], CONF_IMPORT)
        if len(defs) > 1:
            return _AMBIGUOUS
        modules = self._suffix_matches(bound, self.module_table)
        if len(modules) == 1:
            return _Found("module", modules[0], CONF_IMPORT)
        if len(modules) > 1:
            return _AMBIGUOUS
        if "." in bound:
            head, name = bound.rsplit(".", 1)
            heads = self._suffix_matches(head, self.module_table)
            if len(heads) == 1:
                return self.module_member(heads[0], name, depth + 1)
            if len(heads) > 1:
                return _AMBIGUOUS
        return _NONE

    def module_member(self, file_id: str, name: str, depth: int = 0) -> _Found:
        own = self.children.get(file_id, {}).get(name, [])
        if len(own) == 1:
            return _Found("def", own[0], CONF_IMPORT)
        if len(own) > 1:
            return _AMBIGUOUS
        file_path = self.by_id[file_id].file_path
        bound = self.import_names(file_path).get(name)
        if bound is not None:  # re-export: `from .x import name` inside this module
            return self.resolve_bound(bound, depth + 1)
        return _NONE

    # ---- class membership ----------------------------------------------------------------------
    def member_lookup(self, class_id: str, name: str, seen: frozenset[str] = frozenset()) -> tuple[list[str], bool]:
        own = self.children.get(class_id, {}).get(name)
        if own:
            return list(own), False
        for base in self.bases.get(class_id, []):
            if base in seen or base == class_id:
                continue
            found, _ = self.member_lookup(base, name, seen | {class_id})
            if found:
                return found, True
        return [], False

    def enclosing_class(self, symbol_id: str) -> str | None:
        current: str | None = symbol_id
        while current is not None:
            sym = self.by_id.get(current)
            if sym is None:
                return None
            if sym.symbol_type == SymbolType.CLASS:
                return current
            current = self.parent.get(current)
        return None

    # ---- name lookup ---------------------------------------------------------------------------
    def _lexical(self, start_id: str | None, name: str, lang: str) -> _Found:
        current = start_id
        while current is not None:
            sym = self.by_id.get(current)
            if sym is None:
                break
            if sym.symbol_type == SymbolType.CLASS:
                if lang in _IMPLICIT_THIS:
                    ids, inherited = self.member_lookup(current, name)
                    if ids:
                        return self._pick(ids, CONF_INHERITED if inherited else CONF_SCOPE)
            else:
                ids = self.children.get(current, {}).get(name)
                if ids:
                    return self._pick(list(ids), CONF_SCOPE)
            current = self.parent.get(current)
        return _NONE

    @staticmethod
    def _pick(ids: list[str], confidence: float) -> _Found:
        return _Found("def", ids[0], confidence) if len(ids) == 1 else _AMBIGUOUS

    def lookup_name(self, start_id: str | None, file_path: str, name: str, lang: str) -> _Found:
        found = self._lexical(start_id, name, lang)
        if found.kind != "none":
            return found
        bound = self.import_names(file_path).get(name)
        if bound is not None:
            resolved = self.resolve_bound(bound)
            return _EXTERNAL if resolved.kind == "none" else resolved
        # Visibility without a named import: same Java package, or an imported JS/TS module.
        candidates: list[str] = []
        if lang == "java":
            directory = file_path.rpartition("/")[0]
            for file_id in self.files_by_dir.get(directory, []):
                if self.by_id[file_id].file_path != file_path:
                    candidates += [i for i in self.children.get(file_id, {}).get(name, [])
                                   if self.by_id[i].symbol_type == SymbolType.CLASS]
        elif lang in ("javascript", "typescript"):
            for file_id in self.imported_modules(file_path):
                candidates += self.children.get(file_id, {}).get(name, [])
        if len(candidates) == 1:
            return _Found("def", candidates[0], CONF_VISIBLE)
        if len(candidates) > 1:
            return _AMBIGUOUS
        return _NONE

    # ---- relationship resolution ---------------------------------------------------------------
    def resolve_call(self, rel: Relationship) -> _Found:
        src = self.by_id.get(rel.source_id)
        if src is None:
            return _NONE
        lang = src.language.value
        parts = rel.target_name.split(".")

        if len(parts) == 1:
            if not _IDENT.match(parts[0]):
                return _NONE
            return self.lookup_name(src.id, src.file_path, parts[0], lang)

        if len(parts) != 2 or not _IDENT.match(parts[0]) or not _IDENT.match(parts[1]):
            return _NONE  # unknown receiver expression (`?.m`, `a.b.m`, `f().m`)
        recv, attr = parts

        if recv in _SELF_NAMES.get(lang, ()):
            cls = self.enclosing_class(src.id)
            if cls is None:
                return _NONE
            ids, inherited = self.member_lookup(cls, attr)
            return self._pick(ids, CONF_INHERITED if inherited else CONF_SCOPE) if ids else _NONE

        target = self.lookup_name(src.id, src.file_path, recv, lang)
        if target.kind == "module" and target.ident:
            return self.module_member(target.ident, attr)
        if target.kind == "def" and target.ident and self.by_id[target.ident].symbol_type == SymbolType.CLASS:
            ids, inherited = self.member_lookup(target.ident, attr)
            if ids:
                return self._pick(ids, CONF_INHERITED if inherited else min(target.confidence, CONF_IMPORT))
            return _NONE
        return _AMBIGUOUS if target.kind == "ambiguous" else _NONE

    def resolve_inherits(self, rel: Relationship, by_short_class: dict[str, list[str]]) -> _Found:
        src = self.by_id.get(rel.source_id)
        if src is None:
            return _NONE
        lang = src.language.value
        parts = rel.target_name.split(".")
        start = self.parent.get(src.id)  # a class's own members are not in scope for its bases
        found = _NONE
        if all(_IDENT.match(p) for p in parts):
            if len(parts) == 1:
                found = self.lookup_name(start, src.file_path, parts[0], lang)
            else:
                head = self.import_names(src.file_path).get(parts[0])
                if head is not None:
                    found = self.resolve_bound(head + "." + ".".join(parts[1:]))
                    if found.kind == "none":
                        found = _EXTERNAL
                else:
                    outer = self.lookup_name(start, src.file_path, parts[0], lang)
                    if outer.kind == "def" and outer.ident and self.by_id[outer.ident].symbol_type == SymbolType.CLASS:
                        ids, _ = self.member_lookup(outer.ident, parts[1]) if len(parts) == 2 else ([], False)
                        found = self._pick(ids, CONF_SCOPE) if ids else _NONE
        if found.kind == "def" and found.ident and self.by_id[found.ident].symbol_type != SymbolType.CLASS:
            found = _NONE
        if found.kind in ("none",) and len(parts) == 1:
            # Not in scope and not import-bound: fall back to the only class with that name.
            candidates = by_short_class.get(parts[0], [])
            if len(candidates) == 1:
                return _Found("def", candidates[0], CONF_INHERITS_NAME_ONLY)
            if len(candidates) > 1:
                return _AMBIGUOUS
        return found


def _legacy_resolve(rel: Relationship, by_qualified_name: dict[str, str], by_short_name: dict[str, list[str]]) -> Relationship:
    """Original name-based rule, kept for relationship types other than CALLS/INHERITS."""
    exact = by_qualified_name.get(rel.target_name)
    if exact:
        return rel.model_copy(update={"target_id": exact, "confidence": 0.95})
    short_name = rel.target_name.rsplit(".", 1)[-1]
    candidates = by_short_name.get(short_name, [])
    if len(candidates) == 1:
        return rel.model_copy(update={"target_id": candidates[0], "confidence": 0.75})
    if len(candidates) > 1:
        return rel.model_copy(update={"confidence": 0.3})
    return rel.model_copy(update={"confidence": min(rel.confidence, 0.35)})


def _apply(rel: Relationship, found: _Found) -> Relationship:
    if found.kind == "def" and found.ident is not None:
        return rel.model_copy(update={"target_id": found.ident, "confidence": found.confidence})
    if found.kind == "ambiguous":
        # Genuinely uncertain, not a resolver bug. Surface it as such rather than guessing.
        return rel.model_copy(update={"confidence": CONF_AMBIGUOUS})
    return rel.model_copy(update={"confidence": min(rel.confidence, CONF_UNRESOLVED_CAP)})


def resolve_relationships(symbols: list[Symbol], relationships: list[Relationship]) -> list[Relationship]:
    by_qualified_name = {s.qualified_name: s.id for s in symbols}
    by_short_name: dict[str, list[str]] = {}
    by_short_class: dict[str, list[str]] = {}
    for s in symbols:
        if s.symbol_type in _RESOLVABLE_TARGETS:
            by_short_name.setdefault(s.name, []).append(s.id)
        if s.symbol_type == SymbolType.CLASS:
            by_short_class.setdefault(s.name, []).append(s.id)

    index = _Index(symbols, relationships)
    resolved: list[Relationship | None] = [None] * len(relationships)

    # Inheritance first: member lookup through base classes needs the resolved bases.
    for i, rel in enumerate(relationships):
        if rel.target_id is None and rel.relationship_type == RelationshipType.INHERITS:
            out = _apply(rel, index.resolve_inherits(rel, by_short_class))
            resolved[i] = out
            if out.target_id is not None:
                index.bases[rel.source_id].append(out.target_id)

    for i, rel in enumerate(relationships):
        if resolved[i] is not None:
            continue
        if rel.target_id is not None:
            resolved[i] = rel
        elif rel.relationship_type == RelationshipType.CALLS:
            resolved[i] = _apply(rel, index.resolve_call(rel))
        else:
            resolved[i] = _legacy_resolve(rel, by_qualified_name, by_short_name)
    return [r for r in resolved if r is not None]
