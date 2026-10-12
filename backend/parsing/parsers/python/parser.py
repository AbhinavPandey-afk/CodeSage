"""Tree-sitter-based Python parser: source file -> normalized IR.

Extracts files, classes, functions, methods, imports, calls and decorators
per CLAUDE.md §34 Phase 2. Call/inheritance targets are emitted with
target_id=None here — cross-file resolution happens once in
parsing.ir.resolver, after every file in the repo has been parsed.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from tree_sitter import Node

from app.core.languages import Language
from parsing.ir.models import ParsedFile, Relationship, RelationshipType, Symbol, SymbolType
from parsing.parsers.base import LanguageParser, dedupe_symbol_id
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
        seen_ids: dict[str, int] = {}

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
                if obj is not None and obj.type == "attribute":
                    # `self.repo.save()` / `cls.repo.save()`: keep the field so its declared type can be used.
                    inner_obj = obj.child_by_field_name("object")
                    inner_attr = obj.child_by_field_name("attribute")
                    if (inner_obj is not None and inner_obj.type == "identifier"
                            and text(inner_obj) in ("self", "cls") and inner_attr is not None):
                        return f"{text(inner_obj)}.{text(inner_attr)}.{attr_text}"
                # Receiver is an expression (call result, subscript, nested attribute):
                # keep the attribute but mark the receiver unknown so the resolver can
                # tell `foo().bar()` apart from a bare call to a function named `bar`.
                return f"?.{attr_text}"
            return text(func_node)[:80]

        # ---- declared-type evidence (Symbol.declared_types) ---------------------------------------
        type_name_re = re.compile(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)*")

        def normalise_type(raw: str | None) -> str | None:
            """Annotation text -> plain class reference, or None when it is not a single named type
            (unions of several types, generics, callables and literals are not trusted)."""
            if raw is None:
                return None
            t = raw.strip().strip("\"'").strip()
            m = re.fullmatch(r"(?:\w+\.)?Optional\[(.+)\]", t)
            if m:
                t = m.group(1).strip().strip("\"'").strip()
            parts = [p.strip() for p in t.split("|") if p.strip() not in ("None", "")]
            if len(parts) != 1:
                return None
            t = parts[0].strip("\"'").strip()
            return t if type_name_re.fullmatch(t) else None

        def dotted_callee(node: Node) -> str | None:
            """`Foo` / `mod.Foo` when a call's function is a plain dotted name, else None."""
            if node.type == "identifier":
                return text(node)
            if node.type == "attribute":
                obj, attr = node.child_by_field_name("object"), node.child_by_field_name("attribute")
                inner = dotted_callee(obj) if obj is not None else None
                return f"{inner}.{text(attr)}" if inner and attr is not None else None
            return None

        def assignment_fact(node: Node) -> tuple[str, str | None]:
            """('ann', type) | ('ctor', callee) | ('other', None) for `target[: T] = value` statements."""
            annotation = node.child_by_field_name("type")
            if annotation is not None:
                norm = normalise_type(text(annotation))
                return ("ann", norm) if norm else ("other", None)
            right = node.child_by_field_name("right")
            if right is not None and right.type == "call":
                fn = right.child_by_field_name("function")
                callee = dotted_callee(fn) if fn is not None else None
                if callee:
                    return ("ctor", callee)
            return ("other", None)

        def target_names(node: Node | None) -> list[str]:
            """Plain names bound by an assignment/for target. `obj.attr` and `obj[i]` targets bind no name."""
            if node is None:
                return []
            if node.type == "identifier":
                return [text(node)]
            if node.type in ("attribute", "subscript"):
                return []
            return [n for c in node.children for n in target_names(c)]

        def collect_bindings(node: Node, out: dict[str, list[tuple[str, str | None]]]) -> None:
            """Every way a plain name can be bound inside one function body (nested defs are not entered)."""
            for child in node.children:
                t = child.type
                if t in ("function_definition", "class_definition"):
                    nm = child.child_by_field_name("name")
                    if nm is not None:
                        out[text(nm)].append(("def", None))
                    continue
                if t == "decorated_definition":
                    definition = child.child_by_field_name("definition")
                    nm = definition.child_by_field_name("name") if definition is not None else None
                    if nm is not None:
                        out[text(nm)].append(("def", None))
                    continue
                if t == "assignment":
                    left = child.child_by_field_name("left")
                    if left is not None and left.type == "identifier":
                        out[text(left)].append(assignment_fact(child))
                    else:
                        for nm in target_names(left):
                            out[nm].append(("other", None))
                elif t == "augmented_assignment":
                    for nm in target_names(child.child_by_field_name("left")):
                        out[nm].append(("other", None))
                elif t in ("for_statement", "for_in_clause"):
                    for nm in target_names(child.child_by_field_name("left")):
                        out[nm].append(("other", None))
                elif t in ("import_statement", "import_from_statement"):
                    # A function-local import binds a module/definition (found through the import lookup),
                    # so it is not an untyped variable; it still shadows an outer variable of the same name.
                    module_node = child.child_by_field_name("module_name")
                    for part in child.children:
                        if part == module_node or part.type not in ("dotted_name", "aliased_import"):
                            continue
                        if part.type == "aliased_import":
                            alias = part.child_by_field_name("alias")
                            name = alias if alias is not None else part.child_by_field_name("name")
                        else:
                            name = part
                        if name is not None:
                            out[text(name).split(".")[0]].append(("def", None))
                elif t in ("as_pattern_target", "named_expression", "lambda_parameters",
                           "global_statement", "nonlocal_statement"):
                    for nm in target_names(child):
                        out[nm].append(("other", None))
                elif t == "except_clause":
                    for nm in target_names(next((c for c in child.children if c.type == "as_pattern_target"), None)):
                        out[nm].append(("other", None))
                collect_bindings(child, out)

        def merge_facts(facts: list[tuple[str, str | None]]) -> str:
            if any(k == "def" for k, _ in facts):  # a nested def/class: found by lexical lookup, not a typed variable
                return "def" if all(k == "def" for k, _ in facts) else "?"
            anns = {v for k, v in facts if k == "ann"}
            if anns and all(k == "ann" for k, _ in facts) and len(anns) == 1:
                return next(iter(anns))
            ctors = {v for k, v in facts if k == "ctor"}
            if len(facts) == 1 and len(ctors) == 1:
                return "new:" + next(iter(ctors))
            return "?"

        def function_types(def_node: Node) -> dict[str, str]:
            bindings: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
            params = def_node.child_by_field_name("parameters")
            for p in (params.children if params is not None else []):
                if p.type == "identifier":
                    bindings[text(p)].append(("other", None))
                elif p.type in ("typed_parameter", "typed_default_parameter"):
                    nm = p.child_by_field_name("name") or next((c for c in p.children if c.type == "identifier"), None)
                    ann = p.child_by_field_name("type")
                    norm = normalise_type(text(ann)) if ann is not None else None
                    for n in target_names(nm):
                        bindings[n].append(("ann", norm) if norm else ("other", None))
                elif p.type in ("default_parameter", "list_splat_pattern", "dictionary_splat_pattern"):
                    for n in target_names(p.child_by_field_name("name") or p):
                        bindings[n].append(("other", None))
            body = def_node.child_by_field_name("body")
            if body is not None:
                collect_bindings(body, bindings)
            return {name: merge_facts(facts) for name, facts in bindings.items()}

        def class_field_types(class_node: Node) -> dict[str, str]:
            facts: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
            body = class_node.child_by_field_name("body")
            for member in (body.children if body is not None else []):
                if member.type == "expression_statement":
                    stmt = member.children[0] if member.children else None
                    if stmt is not None and stmt.type == "assignment":
                        left = stmt.child_by_field_name("left")
                        if left is not None and left.type == "identifier" and stmt.child_by_field_name("type") is not None:
                            facts[text(left)].append(assignment_fact(stmt))
                    continue
                fn = member
                if member.type == "decorated_definition":
                    if any("staticmethod" in text(d) for d in member.children if d.type == "decorator"):
                        continue
                    fn = member.child_by_field_name("definition") or member
                if fn.type != "function_definition":
                    continue
                params = fn.child_by_field_name("parameters")
                first = next((c for c in (params.children if params is not None else []) if c.type == "identifier"), None)
                fbody = fn.child_by_field_name("body")
                if first is None or fbody is None:
                    continue
                receiver = text(first)

                def scan(node: Node, receiver: str = receiver) -> None:
                    for c in node.children:
                        if c.type in ("function_definition", "class_definition", "decorated_definition", "lambda"):
                            continue
                        if c.type in ("assignment", "augmented_assignment"):
                            left = c.child_by_field_name("left")
                            if left is not None and left.type == "attribute":
                                obj, attr = left.child_by_field_name("object"), left.child_by_field_name("attribute")
                                if obj is not None and attr is not None and obj.type == "identifier" and text(obj) == receiver:
                                    facts[text(attr)].append(assignment_fact(c) if c.type == "assignment" else ("other", None))
                        scan(c)

                scan(fbody)
            result: dict[str, str] = {}
            for name, fs in facts.items():
                anns = {v for k, v in fs if k == "ann"}
                if anns:  # declared annotations win over unannotated assignments, if the annotations agree
                    result[name] = next(iter(anns)) if len(anns) == 1 else "?"
                elif all(k == "ctor" for k, _ in fs) and len({v for _, v in fs}) == 1:
                    result[name] = "new:" + fs[0][1]
                else:
                    result[name] = "?"
            return result

        def module_types(root: Node) -> dict[str, str]:
            facts: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
            for stmt in root.children:
                if stmt.type == "expression_statement" and stmt.children and stmt.children[0].type == "assignment":
                    left = stmt.children[0].child_by_field_name("left")
                    if left is not None and left.type == "identifier":
                        facts[text(left)].append(assignment_fact(stmt.children[0]))
            return {name: merge_facts(fs) for name, fs in facts.items()}

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

        package_parts = module_name.split(".")[:-1]

        def absolute_module(prefix: str) -> str:
            """Resolve the module part of a `from <prefix> import ...` statement. Absolute
            prefixes are returned unchanged; relative ones (".", "..helpers") are resolved
            against this file's package into repo-path form, which is how qualified names
            are written."""
            level = len(prefix) - len(prefix.lstrip("."))
            if level == 0:
                return prefix
            keep = len(package_parts) - (level - 1)
            base = package_parts[:keep] if keep > 0 else []
            rest = prefix.lstrip(".")
            return ".".join([*base, *([rest] if rest else [])])

        def add_import(
            dotted: str, node: Node, container_id: str,
            local_name: str | None = None, bound_path: str | None = None,
        ) -> None:
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
                    local_name=local_name,
                    bound_path=bound_path,
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
                        dotted = text(child)
                        # `import a.b.c` binds only the top-level name `a`.
                        root = dotted.split(".")[0]
                        add_import(dotted, node, container_id, local_name=root, bound_path=root)
                    elif child.type == "aliased_import":
                        name_node = child.child_by_field_name("name")
                        alias_node = child.child_by_field_name("alias")
                        if name_node is not None:
                            dotted = text(name_node)
                            alias = text(alias_node) if alias_node is not None else dotted.split(".")[0]
                            bound = dotted if alias_node is not None else dotted.split(".")[0]
                            add_import(dotted, node, container_id, local_name=alias, bound_path=bound)
            elif node.type == "import_from_statement":
                module_node = node.child_by_field_name("module_name")
                module_prefix = text(module_node) if module_node else ""
                module_abs = absolute_module(module_prefix)
                for child in node.children:
                    if child == module_node:  # tree-sitter nodes compare by value; `is` never matched
                        continue
                    if child.type == "dotted_name":
                        imported = text(child)
                        add_import(
                            f"{module_prefix}.{imported}" if module_prefix else imported, node, container_id,
                            local_name=imported.split(".")[0],
                            bound_path=f"{module_abs}.{imported}" if module_abs else imported,
                        )
                    elif child.type == "aliased_import":
                        name_node = child.child_by_field_name("name")
                        alias_node = child.child_by_field_name("alias")
                        if name_node is not None:
                            imported = text(name_node)
                            add_import(
                                f"{module_prefix}.{imported}" if module_prefix else imported, node, container_id,
                                local_name=text(alias_node) if alias_node is not None else imported,
                                bound_path=f"{module_abs}.{imported}" if module_abs else imported,
                            )
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
                sid = dedupe_symbol_id(seen_ids, qname)
                symbols.append(
                    Symbol(
                        id=sid, name=name, qualified_name=qname, symbol_type=SymbolType.CLASS,
                        file_path=rel_path, start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                        language=Language.PYTHON, decorators=decorators or [], docstring=docstring_of(node),
                        declared_types=class_field_types(node),
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
                sid = dedupe_symbol_id(seen_ids, qname)
                symbol_type = SymbolType.METHOD if in_class else SymbolType.FUNCTION
                symbols.append(
                    Symbol(
                        id=sid, name=name, qualified_name=qname, symbol_type=symbol_type,
                        file_path=rel_path, start_line=node.start_point[0] + 1, end_line=node.end_point[0] + 1,
                        language=Language.PYTHON, decorators=decorators or [], docstring=docstring_of(node),
                        declared_types=function_types(node),
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
                    declared_types=module_types(tree.root_node),
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
