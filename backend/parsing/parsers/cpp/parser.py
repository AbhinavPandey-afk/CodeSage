"""Tree-sitter-based C++ parser: source file -> normalized IR.

Extracts files, classes/structs (with `public`/`private`/`protected`
multiple inheritance), free functions, methods -- both defined inline in the
class body and out-of-line (`ReturnType ClassName::method(...) { ... }`, the
common header/impl split) -- `#include` directives (both `<system>` and
`"local"` forms), calls, and `new` expressions, per CLAUDE.md §34 Phase 6.

Out-of-line method resolution is same-scope-only (disclosed limitation, not
silently missing): `ClassName::method` is attached under
`{current qualified_prefix}.ClassName.method`, which matches the class's own
qualified name when the class is declared in the same file (or the same
namespace across files sharing the same repo-relative path structure) --
there is no cross-file/header-vs-impl symbol table here. Field declarations
(data members) are not extracted as symbols -- C++ has no computed/callable
field initializers the way JS/TS class fields do. Namespace nesting is
folded into the qualified-name prefix the same way a class or module would
be, so `namespace a { namespace b { ... } }` and `namespace a::b { ... }`
both produce an `a.b.*` prefix.
"""
from __future__ import annotations

from pathlib import Path

from tree_sitter import Node

from app.core.languages import Language
from parsing.ir.models import ParsedFile, Relationship, RelationshipType, Symbol, SymbolType
from parsing.parsers.base import LanguageParser, dedupe_symbol_id
from parsing.tree_sitter.loader import get_ts_parser

_CLASS_TYPES = {"class_specifier", "struct_specifier"}
_SCOPE_TYPES = {"function_definition", *_CLASS_TYPES}
_UNWRAP_DECLARATOR_TYPES = {"pointer_declarator", "reference_declarator"}


class CppParser(LanguageParser):
    language = Language.CPP

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

        def include_path(node: Node) -> str | None:
            path = node.child_by_field_name("path")
            if path is None:
                return None
            if path.type == "system_lib_string":
                return text(path)[1:-1]  # strip < >
            if path.type == "string_literal":
                content = next((c for c in path.children if c.type == "string_content"), None)
                return text(content) if content is not None else text(path).strip('"')
            return text(path)

        def flatten_qualified(node: Node) -> str:
            """`A::B::c` (a qualified_identifier) -> "A.B.c"."""
            scope = node.child_by_field_name("scope")
            name_node = node.child_by_field_name("name")
            name = text(name_node) if name_node is not None else "?"
            if scope is None:
                return name
            if scope.type == "qualified_identifier":
                return f"{flatten_qualified(scope)}.{name}"
            return f"{text(scope)}.{name}"

        def call_target_name(node: Node) -> str:
            if node.type in ("identifier", "field_identifier", "type_identifier"):
                return text(node)
            if node.type == "field_expression":
                obj = node.child_by_field_name("argument")
                field = node.child_by_field_name("field")
                field_text = text(field) if field else "?"
                if obj is not None and obj.type in ("identifier", "this"):
                    return f"{text(obj)}.{field_text}"
                return f"?.{field_text}"  # unknown receiver expression
            if node.type == "qualified_identifier":
                return flatten_qualified(node)
            return text(node)[:80]

        def declarator_name_parts(node: Node) -> list[str]:
            """Unwraps pointer/reference declarators to the real name, then
            returns its dotted path segments (["helper"] for a plain name,
            ["PaymentService", "helper"] for an out-of-line `A::helper`)."""
            current = node
            while current.type in _UNWRAP_DECLARATOR_TYPES:
                inner = current.child_by_field_name("declarator")
                if inner is None:
                    break
                current = inner
            if current.type in ("identifier", "field_identifier"):
                return [text(current)]
            if current.type == "qualified_identifier":
                return flatten_qualified(current).split(".")
            return [text(current)[:80]]

        def add_import(dotted: str, node: Node, container_id: str) -> None:
            sid = f"{rel_path}::import::{dotted}::{node.start_point[0]}"
            symbols.append(
                Symbol(
                    id=sid, name=dotted, qualified_name=dotted, symbol_type=SymbolType.IMPORT,
                    file_path=rel_path, start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                    language=Language.CPP,
                )
            )
            relationships.append(
                Relationship(
                    source_id=container_id, target_id=None, target_name=dotted,
                    relationship_type=RelationshipType.IMPORTS, source_file=rel_path,
                    source_line=node.start_point[0] + 1, confidence=1.0,
                )
            )

        def collect_calls(node: Node, source_symbol_id: str) -> None:
            for child in node.children:
                if child.type in _SCOPE_TYPES:
                    continue
                if child.type in ("call_expression", "new_expression"):
                    func_or_type = child.child_by_field_name("function") or child.child_by_field_name("type")
                    if func_or_type is not None:
                        relationships.append(
                            Relationship(
                                source_id=source_symbol_id, target_id=None,
                                target_name=call_target_name(func_or_type), relationship_type=RelationshipType.CALLS,
                                source_file=rel_path, source_line=child.start_point[0] + 1, confidence=0.5,
                            )
                        )
                collect_calls(child, source_symbol_id)

        def emit_function(
            def_node: Node, parts: list[str], container_id: str,
            qualified_prefix: str, default_type: SymbolType, body: Node | None,
        ) -> None:
            if len(parts) > 1:
                # Out-of-line definition, e.g. `int PaymentService::helper(...)`.
                class_qname = f"{qualified_prefix}.{'.'.join(parts[:-1])}" if qualified_prefix else ".".join(parts[:-1])
                qname = f"{class_qname}.{parts[-1]}"
                container_id = class_qname
                symbol_type = SymbolType.METHOD
            else:
                qname = f"{qualified_prefix}.{parts[-1]}" if qualified_prefix else parts[-1]
                symbol_type = default_type
            sid = dedupe_symbol_id(seen_ids, qname)
            symbols.append(
                Symbol(
                    id=sid, name=parts[-1], qualified_name=qname, symbol_type=symbol_type,
                    file_path=rel_path, start_line=def_node.start_point[0] + 1, end_line=def_node.end_point[0] + 1,
                    language=Language.CPP,
                )
            )
            relationships.append(
                Relationship(
                    source_id=container_id, target_id=sid, target_name=parts[-1],
                    relationship_type=RelationshipType.CONTAINS, source_file=rel_path,
                    source_line=def_node.start_point[0] + 1, confidence=1.0,
                )
            )
            if body is not None:
                collect_calls(body, sid)

        def visit_function_definition(
            node: Node, container_id: str, qualified_prefix: str, default_type: SymbolType
        ) -> None:
            declarator = node.child_by_field_name("declarator")
            if declarator is None or declarator.type != "function_declarator":
                return
            inner = declarator.child_by_field_name("declarator")
            if inner is None:
                return
            parts = declarator_name_parts(inner)
            emit_function(node, parts, container_id, qualified_prefix, default_type, node.child_by_field_name("body"))

        def visit_class(node: Node, container_id: str, qualified_prefix: str) -> None:
            name_node = node.child_by_field_name("name")
            name = text(name_node) if name_node else "<anonymous>"
            qname = f"{qualified_prefix}.{name}" if qualified_prefix else name
            sid = dedupe_symbol_id(seen_ids, qname)
            symbols.append(
                Symbol(
                    id=sid, name=name, qualified_name=qname, symbol_type=SymbolType.CLASS,
                    file_path=rel_path, start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                    language=Language.CPP,
                )
            )
            relationships.append(
                Relationship(
                    source_id=container_id, target_id=sid, target_name=name,
                    relationship_type=RelationshipType.CONTAINS, source_file=rel_path,
                    source_line=node.start_point[0] + 1, confidence=1.0,
                )
            )
            for base_clause in (c for c in node.children if c.type == "base_class_clause"):
                for base in base_clause.children:
                    if base.type in ("type_identifier", "qualified_identifier"):
                        relationships.append(
                            Relationship(
                                source_id=sid, target_id=None, target_name=call_target_name(base),
                                relationship_type=RelationshipType.INHERITS, source_file=rel_path,
                                source_line=base.start_point[0] + 1, confidence=0.6,
                            )
                        )

            body = node.child_by_field_name("body")
            if body is None:
                return
            for child in body.children:
                if child.type == "function_definition":
                    visit_function_definition(child, sid, qname, SymbolType.METHOD)
                elif child.type == "field_declaration":
                    declarator = child.child_by_field_name("declarator")
                    if declarator is not None and declarator.type == "function_declarator":
                        # A method declared without a body here (pure virtual,
                        # or declared in a header and defined out-of-line).
                        inner = declarator.child_by_field_name("declarator")
                        if inner is not None:
                            parts = declarator_name_parts(inner)
                            emit_function(child, parts, sid, qname, SymbolType.METHOD, body=None)
                elif child.type in _CLASS_TYPES:
                    visit_class(child, sid, qname)  # nested class/struct

        def visit(node: Node, container_id: str, qualified_prefix: str) -> None:
            if node.type in _CLASS_TYPES:
                visit_class(node, container_id, qualified_prefix)
                return
            if node.type == "function_definition":
                visit_function_definition(node, container_id, qualified_prefix, SymbolType.FUNCTION)
                return
            if node.type == "preproc_include":
                path = include_path(node)
                if path:
                    add_import(path, node, container_id)
                return
            if node.type == "namespace_definition":
                name_node = node.child_by_field_name("name")
                ns_name = text(name_node) if name_node is not None else None
                new_prefix = (
                    f"{qualified_prefix}.{ns_name}" if ns_name and qualified_prefix
                    else (ns_name or qualified_prefix)
                )
                body = node.child_by_field_name("body")
                if body is not None:
                    for child in body.children:
                        visit(child, container_id, new_prefix)
                return
            # Structural pass-through: keep looking for defs/includes inside
            # `extern "C"` blocks and other wrapping constructs.
            for child in node.children:
                visit(child, container_id, qualified_prefix)

        try:
            parser = get_ts_parser(Language.CPP)
            tree = parser.parse(source)
            line_count = source.count(b"\n") + 1

            file_symbol_id = module_name
            symbols.append(
                Symbol(
                    id=file_symbol_id, name=file_path.name, qualified_name=module_name,
                    symbol_type=SymbolType.FILE, file_path=rel_path, start_line=1, end_line=line_count,
                    language=Language.CPP,
                )
            )
            for child in tree.root_node.children:
                visit(child, file_symbol_id, module_name)

        except Exception as exc:  # a single malformed file must not abort the repo parse
            errors.append(str(exc))

        return ParsedFile(
            file_path=rel_path, language=Language.CPP, symbols=symbols,
            relationships=relationships, parse_errors=errors,
        )
