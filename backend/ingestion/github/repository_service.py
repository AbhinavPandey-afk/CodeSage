"""GitHubRepositoryService — the single entry point for turning a GitHub URL
into a validated, size-checked, language-profiled local workspace.

This is the first stage of the pipeline described in CLAUDE.md §26:
    GitHub URL -> validation -> clone -> metadata -> language detection
"""
from __future__ import annotations

from pathlib import Path

from app.core.logging import get_logger
from app.models.repository import RepositoryRecord, RepositoryStatus
from app.repositories.repository_store import RepositoryStore, repository_store
from ingestion.cloning.clone import CloneError, shallow_clone
from ingestion.github.validation import InvalidRepositoryUrlError, validate_github_url
from ingestion.repository_manager.workspace import (
    WorkspaceLimitExceeded,
    allocate_workspace,
    cleanup_workspace,
    scan_workspace,
)

logger = get_logger(__name__)


class GitHubRepositoryService:
    def __init__(self, store: RepositoryStore | None = None) -> None:
        self._store = store or repository_store

    def register(self, url: str) -> RepositoryRecord:
        """Validate the URL and create a PENDING record. Does not clone yet —
        callers (the API layer) trigger `ingest` as a background task so the
        HTTP request returns immediately, per CLAUDE.md §27."""
        parsed = validate_github_url(url)
        repo_id, workspace_path = allocate_workspace()
        record = RepositoryRecord(
            id=repo_id,
            url=parsed.clone_url,
            owner=parsed.owner,
            name=parsed.repo,
            status=RepositoryStatus.PENDING,
            workspace_path=str(workspace_path),
        )
        return self._store.create(record)

    def ingest(self, repo_id: str) -> RepositoryRecord:
        """Clone + scan a previously registered repository. Safe to run in a
        background task/thread; mutates and persists the record as it progresses."""
        record = self._store.get(repo_id)
        if record is None:
            raise ValueError(f"Unknown repository id: {repo_id}")

        if record.workspace_path is None:
            raise ValueError(f"Repository {repo_id} is missing a workspace_path.")
        parsed = validate_github_url(record.url)
        workspace_path = Path(record.workspace_path)

        try:
            record.status = RepositoryStatus.CLONING
            self._store.update(record)
            logger.info("clone.start", repo_id=repo_id, url=record.url)

            repo = shallow_clone(parsed.clone_url, workspace_path)
            record.commit_sha = repo.head.commit.hexsha
            record.default_branch = repo.active_branch.name if not repo.head.is_detached else None

            scan = scan_workspace(workspace_path)
            record.file_count = scan.file_count
            record.languages = {lang.value: count for lang, count in scan.languages.items()}
            record.status = RepositoryStatus.CLONED
            self._store.update(record)
            logger.info(
                "clone.success",
                repo_id=repo_id,
                files=record.file_count,
                languages=record.languages,
            )
            return record

        except (CloneError, WorkspaceLimitExceeded, InvalidRepositoryUrlError) as exc:
            logger.warning("ingest.failed", repo_id=repo_id, error=str(exc))
            cleanup_workspace(workspace_path)
            record.status = RepositoryStatus.FAILED
            record.error = str(exc)
            self._store.update(record)
            return record
        except Exception as exc:  # unexpected — still fail the record, don't crash the worker
            logger.error("ingest.unexpected_error", repo_id=repo_id, error=str(exc))
            cleanup_workspace(workspace_path)
            record.status = RepositoryStatus.FAILED
            record.error = "Internal error during ingestion."
            self._store.update(record)
            return record


github_repository_service = GitHubRepositoryService()
