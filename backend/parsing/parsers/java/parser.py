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

from pathlib import Path

from tree_sitter import Node

from app.core.languages import Language
from parsing.ir.models import ParsedFile, Relationship, RelationshipType, Symbol, SymbolType
from parsing.parsers.base import LanguageParser
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
            sid = qname
            symbols.append(
                Symbol(
                    id=sid, name=name, qualified_name=qname, symbol_type=SymbolType.METHOD,
                    file_path=rel_path, start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                    language=Language.JAVA, decorators=annotations_of(node),
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
            sid = qname
            symbols.append(
                Symbol(
                    id=sid, name=name, qualified_name=qname, symbol_type=SymbolType.CLASS,
                    file_path=rel_path, start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                    language=Language.JAVA, decorators=annotations_of(node),
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

        def visit(node: Node, container_id: str, qualified_prefix: str) -> None:
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
            symbols.append(
                Symbol(
                    id=file_symbol_id, name=file_path.name, qualified_name=module_name,
                    symbol_type=SymbolType.FILE, file_path=rel_path, start_line=1, end_line=line_count,
                    language=Language.JAVA,
                )
            )
            for child in tree.root_node.children:
                visit(child, file_symbol_id, module_name)

        except Exception as exc:  # a single malformed file must not abort the repo parse
            errors.append(str(exc))

        return ParsedFile(
            file_path=rel_path, language=Language.JAVA, symbols=symbols,
            relationships=relationships, parse_errors=errors,
        )
