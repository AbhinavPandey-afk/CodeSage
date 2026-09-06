"""Output model for Historical Reconstruction (CLAUDE.md §27/§28/§34 Phase 5).

Every fact here comes directly from the repository's own commit history --
never from the LLM, and never a fabricated developer intent. When history is
insufficient to answer a "why" question, the caller is expected to say so
explicitly (CLAUDE.md §27) rather than guess.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RawCommit:
    """A minimal, Git-library-independent view of one commit -- the seam
    between real GitPython objects and the pure aggregation logic below,
    so that logic is unit-testable without a real Git repository."""

    sha: str
    author_name: str
    committed_date: int  # unix timestamp, UTC
    subject: str
    changed_files: tuple[str, ...]


@dataclass(frozen=True)
class CommitInfo:
    sha: str
    short_sha: str
    author_name: str
    authored_date: str  # ISO 8601
    subject: str
    files_changed: int


@dataclass(frozen=True)
class ComponentHistory:
    component_id: str
    component_name: str
    role: str
    commit_count: int
    first_seen: str  # ISO 8601 date of the oldest analyzed commit touching this component
    last_changed: str  # ISO 8601 date of the newest analyzed commit touching this component
    top_authors: list[tuple[str, int]]
    introduction_commit: CommitInfo


@dataclass(frozen=True)
class HistoryReport:
    repo_id: str
    commits_analyzed: int
    history_truncated: bool
    components: list[ComponentHistory]
    recent_commits: list[CommitInfo]
    detection_notes: list[str] = field(default_factory=list)
