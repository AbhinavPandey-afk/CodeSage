"""Tree-sitter-based JavaScript parser: source file -> normalized IR.

Extracts files, classes, functions (declarations, `const`-assigned
arrow/function expressions, and arrow-valued class fields), methods,
imports (both ES modules and CommonJS `require()`), calls, `new`
expressions, and inheritance (`extends`), per CLAUDE.md §34 Phase 6.
Call/inheritance targets are emitted with target_id=None here -- cross-file
resolution happens once in parsing.ir.resolver, after every file in the repo
has been parsed, exactly as for the Python parser.

Known limitations (disclosed per CLAUDE.md §7's "don't overclaim support"
rule): JSDoc comments are not attached as docstrings; decorators (a stage-3
proposal, uncommon outside TypeScript/Babel setups) are not extracted; and
unlike Python's decorator-based route registration, Express-style API
routes (`app.get('/path', handler)`) are not detected as entry points --
that requires call-argument-callback analysis, a separate future increment.
"""
from __future__ import annotations

from pathlib import Path

from tree_sitter import Node

from app.core.languages import Language
from parsing.ir.models import ParsedFile, Relationship, RelationshipType, Symbol, SymbolType
from parsing.parsers.base import LanguageParser, dedupe_symbol_id
from parsing.tree_sitter.loader import get_ts_parser

# Node types that define their own scope -- the naive call-collector must not
# descend into them (nested defs collect their own calls when visited
# structurally), mirroring the Python parser's _DEF_TYPES.
_SCOPE_TYPES = {
    "function_declaration", "generator_function_declaration", "function_expression",
    "generator_function", "arrow_function", "method_definition", "class_declaration",
}
_CALLABLE_VALUE_TYPES = {"arrow_function", "function_expression", "generator_function"}
_EXPORTABLE_DEF_TYPES = {"function_declaration", "generator_function_declaration", "class_declaration"}


class JavaScriptParser(LanguageParser):
    language = Language.JAVASCRIPT

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
                return f"?.{prop_text}"  # unknown receiver expression
            return text(func_node)[:80]

        def add_import(dotted: str, node: Node, container_id: str) -> None:
            sid = f"{rel_path}::import::{dotted}::{node.start_point[0]}"
            symbols.append(
                Symbol(
                    id=sid, name=dotted, qualified_name=dotted, symbol_type=SymbolType.IMPORT,
                    file_path=rel_path, start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                    language=Language.JAVASCRIPT,
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
            sid = dedupe_symbol_id(seen_ids, qname)
            symbols.append(
                Symbol(
                    id=sid, name=name, qualified_name=qname, symbol_type=SymbolType.FUNCTION,
                    file_path=rel_path, start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                    language=Language.JAVASCRIPT,
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
                # Expression-bodied arrow function (`(x) => helper(x)`) -- body
                # IS the expression, not a container of statements, so scan the
                # whole callable node's children rather than descending into
                # `body` (which would just re-check the same single expression
                # without ever matching it, since collect_calls only checks
                # *children* of the node it's given).
                collect_calls(node, sid)

        def emit_method(
            name: str, def_node: Node, callable_node: Node, body: Node | None,
            container_id: str, qualified_prefix: str,
        ) -> None:
            qname = f"{qualified_prefix}.{name}"
            sid = dedupe_symbol_id(seen_ids, qname)
            symbols.append(
                Symbol(
                    id=sid, name=name, qualified_name=qname, symbol_type=SymbolType.METHOD,
                    file_path=rel_path, start_line=def_node.start_point[0] + 1, end_line=def_node.end_point[0] + 1,
                    language=Language.JAVASCRIPT,
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

        def visit_method(node: Node, container_id: str, qualified_prefix: str) -> None:
            name_node = node.child_by_field_name("name")
            name = text(name_node) if name_node else "<anonymous>"
            emit_method(name, node, node, node.child_by_field_name("body"), container_id, qualified_prefix)

        def visit_class(node: Node, container_id: str, qualified_prefix: str) -> None:
            name_node = node.child_by_field_name("name")
            name = text(name_node) if name_node else "<anonymous>"
            qname = f"{qualified_prefix}.{name}" if qualified_prefix else name
            sid = dedupe_symbol_id(seen_ids, qname)
            symbols.append(
                Symbol(
                    id=sid, name=name, qualified_name=qname, symbol_type=SymbolType.CLASS,
                    file_path=rel_path, start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                    language=Language.JAVASCRIPT,
                )
            )
            relationships.append(
                Relationship(
                    source_id=container_id, target_id=sid, target_name=name,
                    relationship_type=RelationshipType.CONTAINS, source_file=rel_path,
                    source_line=node.start_point[0] + 1, confidence=1.0,
                )
            )
            heritage = next((c for c in node.children if c.type == "class_heritage"), None)
            if heritage is not None:
                superclass = next(
                    (c for c in heritage.children if c.type in ("identifier", "member_expression")), None
                )
                if superclass is not None:
                    relationships.append(
                        Relationship(
                            source_id=sid, target_id=None, target_name=call_target_name(superclass),
                            relationship_type=RelationshipType.INHERITS, source_file=rel_path,
                            source_line=superclass.start_point[0] + 1, confidence=0.6,
                        )
                    )
            body = node.child_by_field_name("body")
            if body is None:
                return
            for child in body.children:
                if child.type == "method_definition":
                    visit_method(child, sid, qname)
                elif child.type == "field_definition":
                    value = child.child_by_field_name("value")
                    if value is not None and value.type in _CALLABLE_VALUE_TYPES:
                        name_node = child.child_by_field_name("property")
                        name = text(name_node) if name_node else "<anonymous>"
                        emit_method(name, child, value, value.child_by_field_name("body"), sid, qname)

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
                        # Not a function/arrow assignment -- still scan the
                        # initializer for calls, e.g. `const x = require('./y')`.
                        collect_calls(decl, container_id)
                return
            # Structural pass-through: keep looking for defs/imports inside
            # control-flow wrappers and other statement containers.
            for child in node.children:
                visit(child, container_id, qualified_prefix)

        try:
            parser = get_ts_parser(Language.JAVASCRIPT)
            tree = parser.parse(source)
            line_count = source.count(b"\n") + 1

            file_symbol_id = module_name
            symbols.append(
                Symbol(
                    id=file_symbol_id, name=file_path.name, qualified_name=module_name,
                    symbol_type=SymbolType.FILE, file_path=rel_path, start_line=1, end_line=line_count,
                    language=Language.JAVASCRIPT,
                )
            )
            for child in tree.root_node.children:
                visit(child, file_symbol_id, module_name)

        except Exception as exc:  # a single malformed file must not abort the repo parse
            errors.append(str(exc))

        return ParsedFile(
            file_path=rel_path, language=Language.JAVASCRIPT, symbols=symbols,
            relationships=relationships, parse_errors=errors,
        )
