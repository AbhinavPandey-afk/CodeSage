"""Tree-sitter-based TypeScript parser: source file -> normalized IR.

Extracts the same structural shape as the JavaScript parser (files, classes
with `extends` inheritance, functions/methods including arrow-valued class
fields, ES module and CommonJS imports, calls/`new` expressions) plus two
things TypeScript's grammar makes possible that plain JS's can't: real
decorators (`@Injectable()`, `@Get('/x')`) attached to Symbol.decorators, and
`.tsx` files parsed with the dedicated TSX grammar (`.ts`/`.tsx` are NOT
interchangeable -- `<Foo>` is ambiguous between a JSX element and a type
assertion). This is what lets NestJS/Angular-style bare route decorators
work with the same is_api_endpoint check Python's Flask/FastAPI decorators
use, once the regex was extended in analysis/impact/classifiers.py.

Per CLAUDE.md §34 Phase 6. Deliberately not extracted in this first pass
(disclosed, not silently missing): interfaces, type aliases, enums, and
generic type parameters are structurally present in the tree but don't map
to any existing IR SymbolType -- extending the IR to represent them is a
separate, larger increment. `implements` clauses are parsed but not emitted
as a relationship, since RelationshipType has no IMPLEMENTS variant yet.
"""
from __future__ import annotations

from pathlib import Path

from tree_sitter import Node

from app.core.languages import Language
from parsing.ir.models import ParsedFile, Relationship, RelationshipType, Symbol, SymbolType
from parsing.parsers.base import LanguageParser
from parsing.tree_sitter.loader import get_ts_parser, get_tsx_parser

_SCOPE_TYPES = {
    "function_declaration", "generator_function_declaration", "function_expression",
    "generator_function", "arrow_function", "method_definition", "class_declaration",
}
_CALLABLE_VALUE_TYPES = {"arrow_function", "function_expression", "generator_function"}
_EXPORTABLE_DEF_TYPES = {"function_declaration", "generator_function_declaration", "class_declaration"}


class TypeScriptParser(LanguageParser):
    language = Language.TYPESCRIPT

    def parse_file(self, file_path: Path, repo_root: Path) -> ParsedFile:
        rel_path = file_path.relative_to(repo_root).as_posix()
        module_name = rel_path.rsplit(".", 1)[0].replace("/", ".")
        source = file_path.read_bytes()
        is_tsx = file_path.suffix.lower() == ".tsx"

        symbols: list[Symbol] = []
        relationships: list[Relationship] = []
        errors: list[str] = []

        def text(node: Node) -> str:
            return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

        def string_value(node: Node | None) -> str | None:
            if node is None or node.type != "string":
                return None
            fragment = next((c for c in node.children if c.type == "string_fragment"), None)
            return text(fragment) if fragment is not None else ""

        def call_target_name(func_node: Node) -> str:
            if func_node.type == "identifier":
                return text(func_node)
            if func_node.type == "member_expression":
                obj = func_node.child_by_field_name("object")
                prop = func_node.child_by_field_name("property")
                prop_text = text(prop) if prop else "?"
                if obj is not None and obj.type in ("identifier", "this"):
                    return f"{text(obj)}.{prop_text}"
                return prop_text
            return text(func_node)[:80]

        def add_import(dotted: str, node: Node, container_id: str) -> None:
            sid = f"{rel_path}::import::{dotted}::{node.start_point[0]}"
            symbols.append(
                Symbol(
                    id=sid, name=dotted, qualified_name=dotted, symbol_type=SymbolType.IMPORT,
                    file_path=rel_path, start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                    language=Language.TYPESCRIPT,
                )
            )
            relationships.append(
                Relationship(
                    source_id=container_id, target_id=None, target_name=dotted,
                    relationship_type=RelationshipType.IMPORTS, source_file=rel_path,
                    source_line=node.start_point[0] + 1, confidence=1.0,
                )
            )

        def handle_import_statement(node: Node, container_id: str) -> None:
            module = string_value(node.child_by_field_name("source"))
            if module:
                add_import(module, node, container_id)

        def collect_calls(node: Node, source_symbol_id: str) -> None:
            for child in node.children:
                if child.type in _SCOPE_TYPES:
                    continue
                if child.type == "call_expression":
                    func_node = child.child_by_field_name("function")
                    args_node = child.child_by_field_name("arguments")
                    if (
                        func_node is not None and func_node.type == "identifier"
                        and text(func_node) == "require" and args_node is not None
                    ):
                        first_arg = next((a for a in args_node.children if a.type == "string"), None)
                        module = string_value(first_arg)
                        if module:
                            add_import(module, child, source_symbol_id)
                            collect_calls(child, source_symbol_id)
                            continue
                    if func_node is not None:
                        relationships.append(
                            Relationship(
                                source_id=source_symbol_id, target_id=None,
                                target_name=call_target_name(func_node), relationship_type=RelationshipType.CALLS,
                                source_file=rel_path, source_line=child.start_point[0] + 1, confidence=0.5,
                            )
                        )
                elif child.type == "new_expression":
                    ctor_node = child.child_by_field_name("constructor")
                    if ctor_node is not None:
                        relationships.append(
                            Relationship(
                                source_id=source_symbol_id, target_id=None,
                                target_name=call_target_name(ctor_node), relationship_type=RelationshipType.CALLS,
                                source_file=rel_path, source_line=child.start_point[0] + 1, confidence=0.5,
                            )
                        )
                collect_calls(child, source_symbol_id)

        def visit_function(
            node: Node, container_id: str, qualified_prefix: str, name_override: str | None = None
        ) -> None:
            name_node = node.child_by_field_name("name")
            name = name_override or (text(name_node) if name_node else "<anonymous>")
            qname = f"{qualified_prefix}.{name}" if qualified_prefix else name
            sid = qname
            symbols.append(
                Symbol(
                    id=sid, name=name, qualified_name=qname, symbol_type=SymbolType.FUNCTION,
                    file_path=rel_path, start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                    language=Language.TYPESCRIPT,
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
            if body is None:
                return
            if body.type == "statement_block":
                collect_calls(body, sid)
                for child in body.children:
                    visit(child, sid, qname)
            else:
                collect_calls(node, sid)  # expression-bodied arrow function

        def emit_method(
            name: str, def_node: Node, callable_node: Node, body: Node | None,
            container_id: str, qualified_prefix: str, decorators: list[str],
        ) -> None:
            qname = f"{qualified_prefix}.{name}"
            sid = qname
            symbols.append(
                Symbol(
                    id=sid, name=name, qualified_name=qname, symbol_type=SymbolType.METHOD,
                    file_path=rel_path, start_line=def_node.start_point[0] + 1, end_line=def_node.end_point[0] + 1,
                    language=Language.TYPESCRIPT, decorators=decorators,
                )
            )
            relationships.append(
                Relationship(
                    source_id=container_id, target_id=sid, target_name=name,
                    relationship_type=RelationshipType.CONTAINS, source_file=rel_path,
                    source_line=def_node.start_point[0] + 1, confidence=1.0,
                )
            )
            if body is None:
                return
            if body.type == "statement_block":
                collect_calls(body, sid)
                for child in body.children:
                    visit(child, sid, qname)
            else:
                collect_calls(callable_node, sid)

        def visit_method(node: Node, container_id: str, qualified_prefix: str, decorators: list[str]) -> None:
            name_node = node.child_by_field_name("name")
            name = text(name_node) if name_node else "<anonymous>"
            emit_method(name, node, node, node.child_by_field_name("body"), container_id, qualified_prefix, decorators)

        def superclass_name(node: Node) -> str | None:
            heritage = next((c for c in node.children if c.type == "class_heritage"), None)
            if heritage is None:
                return None
            extends_clause = next((c for c in heritage.children if c.type == "extends_clause"), None)
            if extends_clause is None:
                return None
            superclass = extends_clause.child_by_field_name("value")
            if superclass is None:
                return None
            return call_target_name(superclass)

        def visit_class(node: Node, container_id: str, qualified_prefix: str) -> None:
            name_node = node.child_by_field_name("name")
            name = text(name_node) if name_node else "<anonymous>"
            qname = f"{qualified_prefix}.{name}" if qualified_prefix else name
            sid = qname
            class_decorators = [text(c) for c in node.children if c.type == "decorator"]
            symbols.append(
                Symbol(
                    id=sid, name=name, qualified_name=qname, symbol_type=SymbolType.CLASS,
                    file_path=rel_path, start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                    language=Language.TYPESCRIPT, decorators=class_decorators,
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
            # Decorators on methods/fields are preceding siblings within the
            # class body (not children of the method/field itself), unlike
            # class-level decorators -- buffer them until the next member.
            pending_decorators: list[str] = []
            for child in body.children:
                if child.type == "decorator":
                    pending_decorators.append(text(child))
                    continue
                if child.type == "method_definition":
                    visit_method(child, sid, qname, pending_decorators)
                    pending_decorators = []
                elif child.type == "public_field_definition":
                    value = child.child_by_field_name("value")
                    if value is not None and value.type in _CALLABLE_VALUE_TYPES:
                        field_name_node = child.child_by_field_name("name")
                        field_name = text(field_name_node) if field_name_node else "<anonymous>"
                        emit_method(
                            field_name, child, value, value.child_by_field_name("body"),
                            sid, qname, pending_decorators,
                        )
                    pending_decorators = []
                else:
                    pending_decorators = []

        def visit(node: Node, container_id: str, qualified_prefix: str) -> None:
            if node.type in ("function_declaration", "generator_function_declaration"):
                visit_function(node, container_id, qualified_prefix)
                return
            if node.type == "class_declaration":
                visit_class(node, container_id, qualified_prefix)
                return
            if node.type == "import_statement":
                handle_import_statement(node, container_id)
                return
            if node.type == "export_statement":
                declaration = node.child_by_field_name("declaration")
                if declaration is not None:
                    visit(declaration, container_id, qualified_prefix)
                    return
                value = node.child_by_field_name("value")
                if value is not None and value.type in _EXPORTABLE_DEF_TYPES:
                    visit(value, container_id, qualified_prefix)
                return  # bare re-export / export list -- nothing to extract
            if node.type in ("lexical_declaration", "variable_declaration"):
                for decl in node.children:
                    if decl.type != "variable_declarator":
                        continue
                    name_node = decl.child_by_field_name("name")
                    value_node = decl.child_by_field_name("value")
                    if value_node is None:
                        continue
                    if (
                        name_node is not None and name_node.type == "identifier"
                        and value_node.type in _CALLABLE_VALUE_TYPES
                    ):
                        visit_function(value_node, container_id, qualified_prefix, name_override=text(name_node))
                    else:
                        collect_calls(decl, container_id)
                return
            # Structural pass-through: keep looking for defs/imports inside
            # control-flow wrappers and other statement containers. Interfaces,
            # type aliases, and enums fall through here too -- nothing inside
            # them matches a branch above, so they're safely skipped.
            for child in node.children:
                visit(child, container_id, qualified_prefix)

        try:
            parser = get_tsx_parser() if is_tsx else get_ts_parser(Language.TYPESCRIPT)
            tree = parser.parse(source)
            line_count = source.count(b"\n") + 1

            file_symbol_id = module_name
            symbols.append(
                Symbol(
                    id=file_symbol_id, name=file_path.name, qualified_name=module_name,
                    symbol_type=SymbolType.FILE, file_path=rel_path, start_line=1, end_line=line_count,
                    language=Language.TYPESCRIPT,
                )
            )
            for child in tree.root_node.children:
                visit(child, file_symbol_id, module_name)

        except Exception as exc:  # a single malformed file must not abort the repo parse
            errors.append(str(exc))

        return ParsedFile(
            file_path=rel_path, language=Language.TYPESCRIPT, symbols=symbols,
            relationships=relationships, parse_errors=errors,
        )
