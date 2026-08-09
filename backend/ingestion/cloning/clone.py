"""Hardened shallow clone of a validated GitHub URL into an isolated directory."""
from pathlib import Path

import git

# Abort clones that stall (defends against a malicious/huge remote hanging the worker).
_CLONE_ENV = {
    "GIT_TERMINAL_PROMPT": "0",  # never block on an auth prompt
    "GIT_HTTP_LOW_SPEED_LIMIT": "1000",  # bytes/sec
    "GIT_HTTP_LOW_SPEED_TIME": "30",  # seconds below the limit before aborting
}


class CloneError(RuntimeError):
    pass


def shallow_clone(clone_url: str, target_dir: Path) -> git.Repo:
    """Clone at depth=1 (history isn't needed for structural parsing) into target_dir.

    target_dir must not already exist; it is created fresh so a failed/partial
    clone can never be mistaken for a prior successful one.
    """
    if target_dir.exists():
        raise CloneError(f"Target workspace already exists: {target_dir}")
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        return git.Repo.clone_from(
            clone_url,
            target_dir,
            depth=1,
            single_branch=True,
            env=_CLONE_ENV,
        )
    except git.GitCommandError as exc:
        raise CloneError(f"git clone failed: {exc}") from exc
