"""Response contract for GET /api/repositories/{id}/history (CLAUDE.md §27/§44)."""
from pydantic import BaseModel


class CommitInfoResponse(BaseModel):
    sha: str
    short_sha: str
    author_name: str
    authored_date: str
    subject: str
    files_changed: int


class ComponentHistoryResponse(BaseModel):
    component_id: str
    component_name: str
    role: str
    commit_count: int
    first_seen: str
    last_changed: str
    top_authors: list[tuple[str, int]]
    introduction_commit: CommitInfoResponse


class HistoryReportResponse(BaseModel):
    repo_id: str
    commits_analyzed: int
    history_truncated: bool
    components: list[ComponentHistoryResponse]
    recent_commits: list[CommitInfoResponse]
    detection_notes: list[str]
