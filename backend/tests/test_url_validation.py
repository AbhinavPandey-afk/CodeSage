"""URL validation is the first security boundary in ingestion (CLAUDE.md §29)."""
import pytest

from ingestion.github.validation import InvalidRepositoryUrlError, validate_github_url


def test_accepts_plain_github_url():
    parsed = validate_github_url("https://github.com/pallets/flask")
    assert parsed.owner == "pallets"
    assert parsed.repo == "flask"
    assert parsed.clone_url == "https://github.com/pallets/flask.git"


def test_accepts_dot_git_suffix():
    parsed = validate_github_url("https://github.com/pallets/flask.git")
    assert parsed.repo == "flask"


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.com/pallets/flask",
        "ext::sh -c \"touch pwned\"",
        "file:///etc/passwd",
        "git@github.com:pallets/flask.git",
        "https://github.com/pallets/../../etc",
        "http://github.com/pallets/flask",  # not https
        "https://github.com/pallets",  # missing repo
        "",
    ],
)
def test_rejects_unsafe_or_malformed_urls(url):
    with pytest.raises(InvalidRepositoryUrlError):
        validate_github_url(url)
