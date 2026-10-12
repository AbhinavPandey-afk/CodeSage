"""Tree-sitter-based Java parser: source file -> normalized IR.

Extracts files, classes (with `extends` inheritance, including nested
classes), constructors and methods, imports (including static and wildcard
imports), calls (`method_invocation`), `new` expressions
(`object_creation_expression`), and annotations (Java's decorator-equivalent,
attached to Symbol.decorators the same way Python's decorators are) per
CLAUDE.md §34 Phase 6.

Verified against the actual tree-sitter-java grammar shape before writing
extraction logic: `method_invocation` exposes clean `object`/`name`/
`arguments` fields (much simpler than JS/TS's member_expression traversal),
but `modifiers` (which holds annotations) is not a named field on
class/method declarations and must be found by scanning children.

Known limitations (disclosed, not silently missing) -- the same
simplifications already made for the TypeScript parser: interfaces and enums
are parsed by Tree-sitter but not yet mapped into the IR (no matching
SymbolType); `implements` clauses are parsed but not emitted as a
relationship (RelationshipType has no IMPLEMENTS variant yet). Field
declarations are not extracted as symbols -- Java has no arrow-function-
valued fields the way JS/TS do, so there's nothing callable to extract there.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from tree_sitter import Node

from app.core.languages import Language
from parsing.ir.models import ParsedFile, Relationship, RelationshipType, Symbol, SymbolType
from parsing.parsers.base import LanguageParser, dedupe_symbol_id
from parsing.tree_sitter.loader import get_ts_parser

_ANNOTATION_TYPES = {"marker_annotation", "annotation"}
_CALLABLE_DECL_TYPES = {"method_declaration", "constructor_declaration", "class_declaration"}


class JavaParser(LanguageParser):
    language = Language.JAVA

    def parse_file(self, file_path: Path, repo_root: Path) -> ParsedFile:
        rel_path = file_path.relative_to(repo_root).as_posix()
        module_name = rel_path.rsplit(".", 1)[0].replace("/", ".")
        source = file_path.read_bytes()

        symbols: list[Symbol] = []
        relationships: list[Relationship] = []
        errors: list[str] = []
        seen_ids: dict[str, int] = {}

        def text(node: Node) -> str:
            return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

        def annotations_of(node: Node) -> list[str]:
            mods = next((c for c in node.children if c.type == "modifiers"), None)
            if mods is None:
                return []
            return [text(c) for c in mods.children if c.type in _ANNOTATION_TYPES]

        def call_target_name(node: Node) -> str:
            if node.type == "method_invocation":
                obj = node.child_by_field_name("object")
                name_node = node.child_by_field_name("name")
                name = text(name_node) if name_node else "?"
                return f"{text(obj)}.{name}" if obj is not None else name
            if node.type == "object_creation_expression":
                type_node = node.child_by_field_name("type")
                return text(type_node) if type_node is not None else "?"
            return text(node)[:80]

        def add_import(dotted: str, node: Node, container_id: str) -> None:
            sid = f"{rel_path}::import::{dotted}::{node.start_point[0]}"
            symbols.append(
                Symbol(
                    id=sid, name=dotted, qualified_name=dotted, symbol_type=SymbolType.IMPORT,
                    file_path=rel_path, start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                    language=Language.JAVA,
                )
            )
            relationships.append(
                Relationship(
                    source_id=container_id, target_id=None, target_name=dotted,
                    relationship_type=RelationshipType.IMPORTS, source_file=rel_path,
                    source_line=node.start_point[0] + 1, confidence=1.0,
                )
            )

        def handle_import(node: Node, container_id: str) -> None:
            scoped = next((c for c in node.children if c.type in ("scoped_identifier", "identifier")), None)
            if scoped is None:
                return
            dotted = text(scoped)
            if any(c.type == "asterisk" for c in node.children):
                dotted += ".*"
            add_import(dotted, node, container_id)

        # ---- declared-type evidence (Symbol.declared_types) ---------------------------------------
        def java_type(node: Node | None) -> str | None:
            """Plain class reference for a declared type; None for primitives, arrays, `var`, wildcards."""
            if node is None:
                return None
            if node.type in ("type_identifier", "scoped_type_identifier"):
                name = text(node)
                return None if name == "var" else name
            if node.type == "generic_type":  # `Page<Owner>` -> `Page` (type arguments are not used)
                base = next((c for c in node.children if c.type in ("type_identifier", "scoped_type_identifier")), None)
                return text(base) if base is not None else None
            return None

        def created_type(value: Node | None) -> str | None:
            if value is not None and value.type == "object_creation_expression":
                return java_type(value.child_by_field_name("type"))
            return None

        def declarator_facts(type_node: Node | None, declarators: list[Node], out: dict[str, list[str]]) -> None:
            declared = java_type(type_node)
            is_var = type_node is not None and type_node.type == "type_identifier" and text(type_node) == "var"
            for decl in declarators:
                name_node = decl.child_by_field_name("name")
                if name_node is None:
                    continue
                if declared is not None:
                    out[text(name_node)].append(declared)
                elif is_var:
                    ctor = created_type(decl.child_by_field_name("value"))
                    out[text(name_node)].append(f"new:{ctor}" if ctor else "?")
                else:
                    out[text(name_node)].append("?")

        def merge_java(facts: list[str]) -> str:
            if "?" in facts:
                return "?"
            declared = {f for f in facts if not f.startswith("new:")}
            constructed = {f[4:] for f in facts if f.startswith("new:")}
            if len(declared) == 1 and constructed <= declared:
                return next(iter(declared))
            if not declared and len(constructed) == 1:
                return "new:" + next(iter(constructed))
            return "?"

        def collect_locals(node: Node, out: dict[str, list[str]]) -> None:
            for child in node.children:
                t = child.type
                if t in ("class_body", "class_declaration"):
                    continue  # anonymous/local classes bind their own names
                if t == "local_variable_declaration":
                    declarator_facts(child.child_by_field_name("type"), [c for c in child.children if c.type == "variable_declarator"], out)
                elif t == "enhanced_for_statement":
                    name_node = child.child_by_field_name("name")
                    if name_node is not None:
                        declared = java_type(child.child_by_field_name("type"))
                        out[text(name_node)].append(declared or "?")
                elif t == "resource":
                    name_node = child.child_by_field_name("name")
                    if name_node is not None:
                        declared = java_type(child.child_by_field_name("type"))
                        out[text(name_node)].append(declared or "?")
                elif t == "catch_formal_parameter":
                    name_node = child.child_by_field_name("name")
                    types = [c for c in next((c for c in child.children if c.type == "catch_type"), child).children
                             if c.type in ("type_identifier", "scoped_type_identifier")]
                    if name_node is not None:
                        out[text(name_node)].append(java_type(types[0]) if len(types) == 1 else "?")
                elif t == "lambda_expression":
                    params = child.child_by_field_name("parameters")
                    if params is not None and params.type == "identifier":
                        out[text(params)].append("?")
                    elif params is not None and params.type == "inferred_parameters":
                        for c in params.children:
                            if c.type == "identifier":
                                out[text(c)].append("?")
                    elif params is not None and params.type == "formal_parameters":
                        for c in params.children:
                            if c.type == "formal_parameter" and c.child_by_field_name("name") is not None:
                                out[text(c.child_by_field_name("name"))].append(java_type(c.child_by_field_name("type")) or "?")
                collect_locals(child, out)

        def method_types(node: Node) -> dict[str, str]:
            facts: dict[str, list[str]] = defaultdict(list)
            params = node.child_by_field_name("parameters")
            for c in (params.children if params is not None else []):
                if c.type == "formal_parameter" and c.child_by_field_name("name") is not None:
                    facts[text(c.child_by_field_name("name"))].append(java_type(c.child_by_field_name("type")) or "?")
                elif c.type == "spread_parameter":
                    for d in c.children:
                        if d.type == "variable_declarator" and d.child_by_field_name("name") is not None:
                            facts[text(d.child_by_field_name("name"))].append("?")
            body = node.child_by_field_name("body")
            if body is not None:
                collect_locals(body, facts)
            return {name: merge_java(fs) for name, fs in facts.items()}

        def field_types(class_node: Node) -> dict[str, str]:
            facts: dict[str, list[str]] = defaultdict(list)
            body = class_node.child_by_field_name("body")
            for member in (body.children if body is not None else []):
                if member.type == "field_declaration":
                    declarator_facts(member.child_by_field_name("type"), [c for c in member.children if c.type == "variable_declarator"], facts)
            return {name: merge_java(fs) for name, fs in facts.items()}

        def collect_calls(node: Node, source_symbol_id: str) -> None:
            for child in node.children:
                if child.type in _CALLABLE_DECL_TYPES:
                    continue  # nested defs collect their own calls when visited structurally
                if child.type in ("method_invocation", "object_creation_expression"):
                    relationships.append(
                        Relationship(
                            source_id=source_symbol_id, target_id=None, target_name=call_target_name(child),
                            relationship_type=RelationshipType.CALLS, source_file=rel_path,
                            source_line=child.start_point[0] + 1, confidence=0.5,
                        )
                    )
                collect_calls(child, source_symbol_id)

        def visit_callable(node: Node, container_id: str, qualified_prefix: str) -> None:
            name_node = node.child_by_field_name("name")
            name = text(name_node) if name_node else "<anonymous>"
            qname = f"{qualified_prefix}.{name}" if qualified_prefix else name
            sid = dedupe_symbol_id(seen_ids, qname)
            symbols.append(
                Symbol(
                    id=sid, name=name, qualified_name=qname, symbol_type=SymbolType.METHOD,
                    file_path=rel_path, start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                    language=Language.JAVA, decorators=annotations_of(node),
                    declared_types=method_types(node),
                )
            )
            relationships.append(
                Relationship(
                    source_id=container_id, target_id=sid, target_name=name,
                    relationship_type=RelationshipType.CONTAINS, source_file=rel_path,
                    source_line=node.start_point[0] + 1, confidence=1.0,
                )
            )
            body = node.child_by_field_name("body")
            if body is not None:
                collect_calls(body, sid)

        def superclass_name(node: Node) -> str | None:
            wrapper = node.child_by_field_name("superclass")
            if wrapper is None:
                return None
            type_node = next((c for c in wrapper.children if c.type != "extends"), None)
            return text(type_node) if type_node is not None else None

        def visit_class(node: Node, container_id: str, qualified_prefix: str) -> None:
            name_node = node.child_by_field_name("name")
            name = text(name_node) if name_node else "<anonymous>"
            qname = f"{qualified_prefix}.{name}" if qualified_prefix else name
            sid = dedupe_symbol_id(seen_ids, qname)
            symbols.append(
                Symbol(
                    id=sid, name=name, qualified_name=qname, symbol_type=SymbolType.CLASS,
                    file_path=rel_path, start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                    language=Language.JAVA, decorators=annotations_of(node),
                    declared_types=field_types(node),
                )
            )
            relationships.append(
                Relationship(
                    source_id=container_id, target_id=sid, target_name=name,
                    relationship_type=RelationshipType.CONTAINS, source_file=rel_path,
                    source_line=node.start_point[0] + 1, confidence=1.0,
                )
            )
            superclass = superclass_name(node)
            if superclass is not None:
                relationships.append(
                    Relationship(
                        source_id=sid, target_id=None, target_name=superclass,
                        relationship_type=RelationshipType.INHERITS, source_file=rel_path,
                        source_line=node.start_point[0] + 1, confidence=0.6,
                    )
                )

            body = node.child_by_field_name("body")
            if body is None:
                return
            for child in body.children:
                if child.type in ("method_declaration", "constructor_declaration"):
                    visit_callable(child, sid, qname)
                elif child.type == "class_declaration":
                    visit_class(child, sid, qname)  # nested/inner class

        declared_package: dict[str, str] = {}

        def visit(node: Node, container_id: str, qualified_prefix: str) -> None:
            if node.type == "package_declaration":
                name_node = next((c for c in node.children if c.type in ("scoped_identifier", "identifier")), None)
                if name_node is not None:
                    declared_package["name"] = text(name_node)
                return
            if node.type == "class_declaration":
                visit_class(node, container_id, qualified_prefix)
                return
            if node.type == "import_declaration":
                handle_import(node, container_id)
                return
            # Structural pass-through: package declarations, interfaces, enums,
            # and annotation-type declarations fall through here too -- nothing
            # inside them matches a branch above, so they're safely skipped
            # (disclosed limitation) rather than crashing.
            for child in node.children:
                visit(child, container_id, qualified_prefix)

        try:
            parser = get_ts_parser(Language.JAVA)
            tree = parser.parse(source)
            line_count = source.count(b"\n") + 1

            file_symbol_id = module_name
            file_symbol = Symbol(
                id=file_symbol_id, name=file_path.name, qualified_name=module_name,
                symbol_type=SymbolType.FILE, file_path=rel_path, start_line=1, end_line=line_count,
                language=Language.JAVA,
            )
            symbols.append(file_symbol)
            for child in tree.root_node.children:
                visit(child, file_symbol_id, module_name)
            # A Java package spans source roots (src/main/java and src/test/java), so the declared package,
            # not the directory, decides which classes are visible without an import.
            file_symbol.bound_path = declared_package.get("name")

        except Exception as exc:  # a single malformed file must not abort the repo parse
            errors.append(str(exc))

        return ParsedFile(
            file_path=rel_path, language=Language.JAVA, symbols=symbols,
            relationships=relationships, parse_errors=errors,
        )
