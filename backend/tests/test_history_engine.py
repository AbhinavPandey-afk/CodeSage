from datetime import datetime, timezone

from analysis.history.engine import aggregate_component_history
from analysis.history.models import RawCommit
from analysis.reconstruction.models import ArchitectureComponent


def _ts(year, month, day):
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp())


def _component(id_, role, files):
    return ArchitectureComponent(
        id=id_, name=id_, role=role, file_count=len(files), symbol_count=len(files), files=files,
        confidence=0.8, confidence_label="Confirmed", evidence=[],
    )


def _commit(sha, author, date, subject, files):
    return RawCommit(sha=sha, author_name=author, committed_date=_ts(*date), subject=subject, changed_files=tuple(files))


def test_groups_commits_by_component_and_counts():
    api = _component("app/api", "api", ["app/api/c.py"])
    data = _component("app/data", "data_access", ["app/data/r.py"])
    file_to_component = {"app/api/c.py": api, "app/data/r.py": data}

    commits = [
        _commit("c1", "Alice", (2024, 1, 1), "add controller", ["app/api/c.py"]),
        _commit("c2", "Bob", (2024, 2, 1), "add repository", ["app/data/r.py"]),
        _commit("c3", "Alice", (2024, 3, 1), "tweak controller", ["app/api/c.py"]),
    ]
    results = aggregate_component_history(commits, file_to_component)

    by_id = {r.component_id: r for r in results}
    assert by_id["app/api"].commit_count == 2
    assert by_id["app/data"].commit_count == 1


def test_introduction_commit_is_the_oldest_touching_commit():
    api = _component("app/api", "api", ["app/api/c.py"])
    file_to_component = {"app/api/c.py": api}
    commits = [
        _commit("newer", "Bob", (2024, 6, 1), "later change", ["app/api/c.py"]),
        _commit("older", "Alice", (2023, 1, 1), "initial controller", ["app/api/c.py"]),
    ]
    results = aggregate_component_history(commits, file_to_component)
    assert results[0].introduction_commit.sha == "older"
    assert results[0].introduction_commit.subject == "initial controller"


def test_first_seen_and_last_changed_bound_the_window():
    api = _component("app/api", "api", ["app/api/c.py"])
    file_to_component = {"app/api/c.py": api}
    commits = [
        _commit("c1", "Alice", (2023, 1, 1), "first", ["app/api/c.py"]),
        _commit("c2", "Alice", (2024, 6, 1), "last", ["app/api/c.py"]),
    ]
    result = aggregate_component_history(commits, file_to_component)[0]
    assert result.first_seen.startswith("2023-01-01")
    assert result.last_changed.startswith("2024-06-01")


def test_top_authors_ranked_by_commit_count():
    api = _component("app/api", "api", ["app/api/c.py"])
    file_to_component = {"app/api/c.py": api}
    commits = [
        _commit("c1", "Alice", (2024, 1, 1), "a", ["app/api/c.py"]),
        _commit("c2", "Alice", (2024, 1, 2), "b", ["app/api/c.py"]),
        _commit("c3", "Bob", (2024, 1, 3), "c", ["app/api/c.py"]),
    ]
    result = aggregate_component_history(commits, file_to_component)[0]
    assert result.top_authors[0] == ("Alice", 2)


def test_commits_touching_unmapped_files_are_ignored():
    file_to_component: dict = {}
    commits = [_commit("c1", "Alice", (2024, 1, 1), "unrelated", ["some/unmapped/file.py"])]
    assert aggregate_component_history(commits, file_to_component) == []


def test_components_sorted_by_commit_count_descending():
    hot = _component("app/hot", "service", ["app/hot/a.py"])
    cold = _component("app/cold", "service", ["app/cold/b.py"])
    file_to_component = {"app/hot/a.py": hot, "app/cold/b.py": cold}
    commits = [
        _commit("c1", "A", (2024, 1, 1), "x", ["app/hot/a.py"]),
        _commit("c2", "A", (2024, 1, 2), "x", ["app/hot/a.py"]),
        _commit("c3", "A", (2024, 1, 3), "x", ["app/cold/b.py"]),
    ]
    results = aggregate_component_history(commits, file_to_component)
    assert [r.component_id for r in results] == ["app/hot", "app/cold"]


def test_a_commit_touching_two_components_counts_toward_both():
    a = _component("app/a", "service", ["app/a/x.py"])
    b = _component("app/b", "service", ["app/b/y.py"])
    file_to_component = {"app/a/x.py": a, "app/b/y.py": b}
    commits = [_commit("c1", "Alice", (2024, 1, 1), "cross-cutting change", ["app/a/x.py", "app/b/y.py"])]
    results = aggregate_component_history(commits, file_to_component)
    assert {r.component_id for r in results} == {"app/a", "app/b"}
    assert all(r.commit_count == 1 for r in results)
