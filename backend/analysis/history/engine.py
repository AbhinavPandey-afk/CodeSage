"""Historical Reconstruction engine (CLAUDE.md §27/§28/§34 Phase 5).

Uses the repository's own Git history -- never the LLM -- to establish which
architectural components change most, when they were likely introduced, and
who touches them. If history is insufficient, that limitation is disclosed
in detection_notes rather than papered over (CLAUDE.md §27: "If there is no
explicit rationale, say so").

Repositories are cloned shallow (depth=1) for parsing speed (see
ingestion/cloning/clone.py) -- the ingestion pipeline itself doesn't need
history. Rather than changing that default for every repository, this module
best-effort widens the clone on demand, bounded to a fixed number of extra
commits so a repository with a very long history doesn't pull all of it.

_aggregate_component_history and _commit_info are pure (they take RawCommit,
a Git-library-independent seam) and are unit-tested without a real Git repo.
Only analyze_history() touches Git and Neo4j.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import git

from analysis.history.models import CommitInfo, ComponentHistory, HistoryReport, RawCommit
from analysis.reconstruction.engine import reconstruct_architecture
from analysis.reconstruction.models import ArchitectureComponent
from app.repositories.repository_store import repository_store

_DEEPEN_COMMITS = 500
_MAX_COMMITS_ANALYZED = 500
_MAX_RECENT_COMMITS = 20
_TOP_AUTHORS = 3


class RepositoryNotFoundError(ValueError):
    pass


class WorkspaceUnavailableError(RuntimeError):
    pass


def _open_repo(workspace_path: str) -> git.Repo:
    path = Path(workspace_path)
    if not path.exists():
        raise WorkspaceUnavailableError(f"Workspace no longer exists at {workspace_path}.")
    try:
        return git.Repo(path)
    except git.InvalidGitRepositoryError as exc:
        raise WorkspaceUnavailableError(f"No Git repository found at {workspace_path}.") from exc


def _is_shallow(repo: git.Repo) -> bool:
    try:
        return repo.git.rev_parse("--is-shallow-repository").strip() == "true"
    except git.GitCommandError:
        return False


def _ensure_history(repo: git.Repo) -> None:
    try:
        if _is_shallow(repo):
            repo.git.fetch("origin", "--deepen", str(_DEEPEN_COMMITS))
    except git.GitCommandError:
        pass  # best-effort -- fall back to whatever history is already present


def _to_raw_commit(commit: git.Commit) -> RawCommit:
    try:
        changed_files = tuple(commit.stats.files.keys())
    except Exception:
        changed_files = ()
    message = commit.message.strip()
    return RawCommit(
        sha=commit.hexsha,
        author_name=commit.author.name or "unknown",
        committed_date=commit.committed_date,
        subject=message.splitlines()[0] if message else "(no message)",
        changed_files=changed_files,
    )


def _commit_info(raw: RawCommit) -> CommitInfo:
    dt = datetime.fromtimestamp(raw.committed_date, tz=timezone.utc)
    return CommitInfo(
        sha=raw.sha, short_sha=raw.sha[:8], author_name=raw.author_name,
        authored_date=dt.isoformat(), subject=raw.subject, files_changed=len(raw.changed_files),
    )


def aggregate_component_history(
    commits: list[RawCommit], file_to_component: dict[str, ArchitectureComponent]
) -> list[ComponentHistory]:
    """Pure: groups commits by which architectural component(s) they touched,
    oldest-first, so the earliest commit found becomes each component's
    (window-bounded) introduction evidence."""
    per_component: dict[str, list[RawCommit]] = {}
    for commit in commits:
        touched: set[str] = set()
        for changed_file in commit.changed_files:
            comp = file_to_component.get(changed_file)
            if comp is not None:
                touched.add(comp.id)
        for cid in touched:
            per_component.setdefault(cid, []).append(commit)

    components_by_id = {c.id: c for c in file_to_component.values()}
    results: list[ComponentHistory] = []
    for cid, commit_list in per_component.items():
        comp = components_by_id.get(cid)
        if comp is None:
            continue
        ordered = sorted(commit_list, key=lambda c: c.committed_date)
        oldest, newest = ordered[0], ordered[-1]
        author_counts = Counter(c.author_name for c in commit_list)
        results.append(
            ComponentHistory(
                component_id=cid, component_name=comp.name, role=comp.role,
                commit_count=len(commit_list),
                first_seen=datetime.fromtimestamp(oldest.committed_date, tz=timezone.utc).isoformat(),
                last_changed=datetime.fromtimestamp(newest.committed_date, tz=timezone.utc).isoformat(),
                top_authors=author_counts.most_common(_TOP_AUTHORS),
                introduction_commit=_commit_info(oldest),
            )
        )
    results.sort(key=lambda c: c.commit_count, reverse=True)
    return results


def analyze_history(repo_id: str) -> HistoryReport:
    record = repository_store.get(repo_id)
    if record is None:
        raise RepositoryNotFoundError(f"Repository {repo_id} not found.")
    if record.workspace_path is None:
        raise WorkspaceUnavailableError(f"Repository {repo_id} has no workspace.")

    repo = _open_repo(record.workspace_path)
    _ensure_history(repo)

    try:
        git_commits = list(repo.iter_commits(max_count=_MAX_COMMITS_ANALYZED))
    except git.GitCommandError:
        git_commits = []
    raw_commits = [_to_raw_commit(c) for c in git_commits]

    history_truncated = _is_shallow(repo) or len(raw_commits) >= _MAX_COMMITS_ANALYZED

    model = reconstruct_architecture(repo_id)
    file_to_component = {f: c for c in model.components for f in c.files}

    components = aggregate_component_history(raw_commits, file_to_component)

    detection_notes = [
        "Analysis is based on this repository's own commit history, not inferred developer intent.",
        f"Up to {_MAX_COMMITS_ANALYZED} of the most recent commits were analyzed.",
    ]
    if history_truncated:
        detection_notes.append(
            "This repository has more commits than were analyzed (it was cloned shallow for speed "
            "and only partially deepened) -- 'first seen' dates reflect the oldest commit found "
            "within that window, not necessarily when a component was first introduced."
        )
    if not raw_commits:
        detection_notes.append("No commit history could be read for this repository.")

    return HistoryReport(
        repo_id=repo_id, commits_analyzed=len(raw_commits), history_truncated=history_truncated,
        components=components, recent_commits=[_commit_info(c) for c in raw_commits[:_MAX_RECENT_COMMITS]],
        detection_notes=detection_notes,
    )
