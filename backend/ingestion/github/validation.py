"""Strict validation for user-supplied GitHub URLs.

Only `https://github.com/<owner>/<repo>` is accepted. This blocks:
- git's `ext::`/`fd::` transports (known arbitrary-command-execution vectors)
- `file://` and other local-path schemes (path traversal / local disclosure)
- non-GitHub hosts
- owner/repo values containing shell or filesystem metacharacters
"""
import re
from dataclasses import dataclass

_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/"
    r"(?P<repo>[A-Za-z0-9_.-]{1,100}?)"
    r"(?:\.git)?/?$"
)


class InvalidRepositoryUrlError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedRepoUrl:
    owner: str
    repo: str
    clone_url: str


def validate_github_url(url: str) -> ParsedRepoUrl:
    """Parse and validate a GitHub repository URL, or raise InvalidRepositoryUrlError."""
    url = url.strip()
    match = _GITHUB_URL_RE.match(url)
    if not match:
        raise InvalidRepositoryUrlError(
            "Only URLs of the form https://github.com/<owner>/<repo> are supported."
        )
    owner, repo = match.group("owner"), match.group("repo")
    if repo in {".", ".."}:
        raise InvalidRepositoryUrlError("Invalid repository name.")
    return ParsedRepoUrl(owner=owner, repo=repo, clone_url=f"https://github.com/{owner}/{repo}.git")
