"""Tree-sitter-based Python parser: source file -> normalized IR.

Extracts files, classes, functions, methods, imports, calls and decorators
per CLAUDE.md §34 Phase 2. Call/inheritance targets are emitted with
target_id=None here — cross-file resolution happens once in
parsing.ir.resolver, after every file in the repo has been parsed.
"""
from __future__ import annotations

from pathlib import Path

from tree_sitter import Node

from app.core.languages import Language
from parsing.ir.models import ParsedFile, Relationship, RelationshipType, Symbol, SymbolType
from parsing.parsers.base import LanguageParser
from parsing.tree_sitter.loader import get_ts_parser

_DOCSTRING_MAX_LEN = 500
_DEF_TYPES = {"function_definition", "class_definition", "decorated_definition"}


class PythonParser(LanguageParser):
    language = Language.PYTHON

    def parse_file(self, file_path: Path, repo_root: Path) -> ParsedFile:
        rel_path = file_path.relative_to(repo_root).as_posix()
        module_name = rel_path[:-3].replace("/", ".") if rel_path.endswith(".py") else rel_path.replace("/", ".")
        source = file_path.read_bytes()

        symbols: list[Symbol] = []
        relationships: list[Relationship] = []
        errors: list[str] = []

        def text(node: Node) -> str:
            return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

        def docstring_of(def_node: Node) -> str | None:
            body = def_node.child_by_field_name("body")
            if not body or not body.children:
                return None
            first = body.children[0]
            if first.type != "expression_statement" or not first.children:
                return None
            expr = first.children[0]
            if expr.type != "string":
                return None
            return text(expr)[:_DOCSTRING_MAX_LEN]

        def module_docstring(root_node: Node) -> str | None:
            if not root_node.children:
                return None
            first = root_node.children[0]
            if first.type != "expression_statement" or not first.children:
                return None
            expr = first.children[0]
            if expr.type != "string":
                return None
            return text(expr)[:_DOCSTRING_MAX_LEN]

        def call_target_name(func_node: Node) -> str:
            if func_node.type == "identifier":
                return text(func_node)
            if func_node.type == "attribute":
                obj = func_node.child_by_field_name("object")
                attr = func_node.child_by_field_name("attribute")
                attr_text = text(attr) if attr else "?"
                if obj is not None and obj.type == "identifier":
                    return f"{text(obj)}.{attr_text}"
                return attr_text
            return text(func_node)[:80]

        def collect_calls(node: Node, source_symbol_id: str) -> None:
            for child in node.children:
                if child.type in _DEF_TYPES:
                    continue  # nested defs collect their own calls when visited structurally
                if child.type == "call":
                    func_node = child.child_by_field_name("function")
                    if func_node is not None:
                        relationships.append(
                            Relationship(
                                source_id=source_symbol_id,
                                target_id=None,
                                target_name=call_target_name(func_node),
                                relationship_type=RelationshipType.CALLS,
                                source_file=rel_path,
                                source_line=child.start_point[0] + 1,
                                confidence=0.5,
                            )
                        )
                collect_calls(child, source_symbol_id)

        def add_import(dotted: str, node: Node, container_id: str) -> None:
            sid = f"{rel_path}::import::{dotted}::{node.start_point[0]}"
            symbols.append(
                Symbol(
                    id=sid,
                    name=dotted,
                    qualified_name=dotted,
                    symbol_type=SymbolType.IMPORT,
                    file_path=rel_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language=Language.PYTHON,
                )
            )
            relationships.append(
                Relationship(
                    source_id=container_id,
                    target_id=None,
                    target_name=dotted,
                    relationship_type=RelationshipType.IMPORTS,
                    source_file=rel_path,
                    source_line=node.start_point[0] + 1,
                    confidence=1.0,
                )
            )

        def handle_import(node: Node, container_id: str) -> None:
            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        add_import(text(child), node, container_id)
                    elif child.type == "aliased_import":
                        name_node = child.child_by_field_name("name")
                        if name_node is not None:
                            add_import(text(name_node), node, container_id)
            elif node.type == "import_from_statement":
                module_node = node.child_by_field_name("module_name")
                module_prefix = text(module_node) if module_node else ""
                for child in node.children:
                    if child is module_node:
                        continue
                    if child.type == "dotted_name":
                        add_import(f"{module_prefix}.{text(child)}" if module_prefix else text(child), node, container_id)
                    elif child.type == "aliased_import":
                        name_node = child.child_by_field_name("name")
                        if name_node is not None:
                            imported = text(name_node)
                            add_import(f"{module_prefix}.{imported}" if module_prefix else imported, node, container_id)
                    elif child.type == "wildcard_import":
                        add_import(f"{module_prefix}.*", node, container_id)

        def visit(node: Node, container_id: str, qualified_prefix: str, in_class: bool, decorators: list[str] | None = None) -> None:
            if node.type == "decorated_definition":
                decs = [text(d) for d in node.children if d.type == "decorator"]
                definition = node.child_by_field_name("definition")
                if definition is not None:
                    visit(definition, container_id, qualified_prefix, in_class, decorators=decs)
                return

            if node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                name = text(name_node) if name_node else "<anonymous>"
                qname = f"{qualified_prefix}.{name}" if qualified_prefix else name
                sid = qname
                symbols.append(
                    Symbol(
                        id=sid, name=name, qualified_name=qname, symbol_type=SymbolType.CLASS,
                        file_path=rel_path, start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                        language=Language.PYTHON, decorators=decorators or [], docstring=docstring_of(node),
                    )
                )
                relationships.append(
                    Relationship(source_id=container_id, target_id=sid, target_name=name,
                                  relationship_type=RelationshipType.CONTAINS, source_file=rel_path,
                                  source_line=node.start_point[0] + 1, confidence=1.0)
                )
                superclasses = node.child_by_field_name("superclasses")
                if superclasses is not None:
                    for arg in superclasses.children:
                        if arg.type in ("identifier", "attribute"):
                            relationships.append(
                                Relationship(source_id=sid, target_id=None, target_name=text(arg),
                                              relationship_type=RelationshipType.INHERITS, source_file=rel_path,
                                              source_line=arg.start_point[0] + 1, confidence=0.6)
                            )
                body = node.child_by_field_name("body")
                if body is not None:
                    for child in body.children:
                        visit(child, sid, qname, in_class=True)
                return

            if node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                name = text(name_node) if name_node else "<anonymous>"
                qname = f"{qualified_prefix}.{name}" if qualified_prefix else name
                sid = qname
                symbol_type = SymbolType.METHOD if in_class else SymbolType.FUNCTION
                symbols.append(
                    Symbol(
                        id=sid, name=name, qualified_name=qname, symbol_type=symbol_type,
                        file_path=rel_path, start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                        language=Language.PYTHON, decorators=decorators or [], docstring=docstring_of(node),
                    )
                )
                relationships.append(
                    Relationship(source_id=container_id, target_id=sid, target_name=name,
                                  relationship_type=RelationshipType.CONTAINS, source_file=rel_path,
                                  source_line=node.start_point[0] + 1, confidence=1.0)
                )
                body = node.child_by_field_name("body")
                if body is not None:
                    collect_calls(body, sid)
                    for child in body.children:
                        visit(child, sid, qname, in_class=False)
                return

            if node.type in ("import_statement", "import_from_statement"):
                handle_import(node, container_id)
                return

            # Structural pass-through: keep looking for defs/imports inside
            # control-flow wrappers (if/try/with at module or class level).
            for child in node.children:
                visit(child, container_id, qualified_prefix, in_class)

        try:
            parser = get_ts_parser(Language.PYTHON)
            tree = parser.parse(source)
            line_count = source.count(b"\n") + 1

            file_symbol_id = module_name
            symbols.append(
                Symbol(
                    id=file_symbol_id, name=file_path.name, qualified_name=module_name,
                    symbol_type=SymbolType.FILE, file_path=rel_path, start_line=1, end_line=line_count,
                    language=Language.PYTHON, docstring=module_docstring(tree.root_node),
                )
            )
            for child in tree.root_node.children:
                visit(child, file_symbol_id, module_name, in_class=False)

        except Exception as exc:  # a single malformed file must not abort the repo parse
            errors.append(str(exc))

        return ParsedFile(
            file_path=rel_path, language=Language.PYTHON, symbols=symbols,
            relationships=relationships, parse_errors=errors,
        )
