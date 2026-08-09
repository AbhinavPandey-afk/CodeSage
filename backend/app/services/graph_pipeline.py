"""Parsing + graph-build stage of the pipeline: workspace -> IR -> Neo4j.

Dispatches by file extension through PARSER_REGISTRY, so adding a language
(Phase II) means registering a parser here — nothing else in this module
changes.
"""
from pathlib import Path

from app.core.languages import EXTENSION_LANGUAGE_MAP, IMPLEMENTED_PARSERS, Language
from app.core.logging import get_logger
from app.models.repository import RepositoryStatus
from app.repositories.repository_store import repository_store
from embeddings.registry import new_store, set_store
from embeddings.vector_store.base import EmbeddingItem
from graph.loader import load_repository_graph
from ingestion.repository_manager.workspace import IGNORED_DIRS
from parsing.ir.models import ParsedFile, SymbolType
from parsing.parsers.base import LanguageParser
from parsing.parsers.python.parser import PythonParser

logger = get_logger(__name__)

PARSER_REGISTRY: dict[Language, LanguageParser] = {
    Language.PYTHON: PythonParser(),
}


_EMBEDDABLE_TYPES = {SymbolType.FILE, SymbolType.CLASS, SymbolType.FUNCTION, SymbolType.METHOD}


def _embedding_items(repo_id: str, parsed_files: list[ParsedFile]) -> list[EmbeddingItem]:
    items: list[EmbeddingItem] = []
    for pf in parsed_files:
        for s in pf.symbols:
            if s.symbol_type not in _EMBEDDABLE_TYPES:
                continue
            text = f"{s.qualified_name}\n{' '.join(s.decorators)}\n{s.docstring or ''}".strip()
            if not text:
                continue
            items.append(
                EmbeddingItem(
                    symbol_uid=f"{repo_id}:{s.id}",
                    text=text,
                    symbol_type=s.symbol_type.value,
                    name=s.name,
                    qualified_name=s.qualified_name,
                    file_path=s.file_path,
                    start_line=s.start_line,
                    end_line=s.end_line,
                )
            )
    return items


def _parse_workspace(repo_root: Path) -> list[ParsedFile]:
    parsed_files: list[ParsedFile] = []
    for file_path in repo_root.rglob("*"):
        if any(part in IGNORED_DIRS for part in file_path.parts) or not file_path.is_file():
            continue
        lang = EXTENSION_LANGUAGE_MAP.get(file_path.suffix.lower())
        if lang is None or lang not in IMPLEMENTED_PARSERS:
            continue
        parser = PARSER_REGISTRY[lang]
        parsed_files.append(parser.parse_file(file_path, repo_root))
    return parsed_files


def build_graph_for_repository(repo_id: str) -> None:
    record = repository_store.get(repo_id)
    if record is None or record.workspace_path is None:
        return

    record.status = RepositoryStatus.PARSING
    repository_store.update(record)
    parsed_files = _parse_workspace(Path(record.workspace_path))
    parse_errors = sum(len(pf.parse_errors) for pf in parsed_files)
    logger.info("pipeline.parsed", repo_id=repo_id, files=len(parsed_files), parse_errors=parse_errors)

    record.status = RepositoryStatus.BUILDING_GRAPH
    repository_store.update(record)
    result = load_repository_graph(
        repo_id=repo_id,
        owner=record.owner,
        name=record.name,
        url=record.url,
        default_branch=record.default_branch,
        commit_sha=record.commit_sha,
        parsed_files=parsed_files,
    )
    record.symbol_count = result.symbol_count
    record.relationship_count = result.relationship_count
    repository_store.update(record)

    record.status = RepositoryStatus.EMBEDDING
    repository_store.update(record)
    store = new_store()
    store.build(_embedding_items(repo_id, parsed_files))
    set_store(repo_id, store)

    record.status = RepositoryStatus.READY
    repository_store.update(record)
