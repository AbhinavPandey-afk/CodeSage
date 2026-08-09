"""Isolated per-repository workspace: allocation, file walking, size limits, cleanup."""
from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings
from app.core.languages import EXTENSION_LANGUAGE_MAP, Language

# Directories that are never structurally interesting and can be large (build
# artifacts, dependency trees, VCS internals) — skipped during both file-count
# limiting and language detection.
IGNORED_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build",
    ".next", ".nuxt", "target", ".idea", ".vscode", "vendor", "site-packages",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "coverage", ".tox", "egg-info",
}


class WorkspaceLimitExceeded(RuntimeError):
    pass


@dataclass
class WorkspaceScan:
    file_count: int = 0
    total_size_bytes: int = 0
    languages: dict[Language, int] = field(default_factory=dict)


def allocate_workspace(repo_id: str | None = None) -> tuple[str, Path]:
    """Reserve a fresh, isolated directory for a clone. repo_id is never user input."""
    rid = repo_id or str(uuid.uuid4())
    path = settings.workspace_dir / rid
    return rid, path


def scan_workspace(path: Path) -> WorkspaceScan:
    """Walk a cloned repo, counting files/bytes and detecting languages by extension.

    Raises WorkspaceLimitExceeded as soon as a configured limit is crossed so
    oversized repositories are rejected without fully materializing costs
    (embeddings, parsing) downstream.
    """
    scan = WorkspaceScan()
    for item in path.rglob("*"):
        if any(part in IGNORED_DIRS for part in item.parts):
            continue
        if not item.is_file():
            continue

        scan.file_count += 1
        if scan.file_count > settings.max_repo_files:
            raise WorkspaceLimitExceeded(
                f"Repository exceeds {settings.max_repo_files} files."
            )

        scan.total_size_bytes += item.stat().st_size
        if scan.total_size_bytes > settings.max_repo_size_mb * 1024 * 1024:
            raise WorkspaceLimitExceeded(
                f"Repository exceeds {settings.max_repo_size_mb}MB."
            )

        lang = EXTENSION_LANGUAGE_MAP.get(item.suffix.lower())
        if lang is not None:
            scan.languages[lang] = scan.languages.get(lang, 0) + 1

    return scan


def cleanup_workspace(path: Path) -> None:
    """Best-effort teardown of a workspace directory, e.g. after a failed/rejected clone."""
    shutil.rmtree(path, ignore_errors=True)
