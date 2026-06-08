import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gitlab_issues_api import GitLabIssuesAPI


def test_get_issue_builds_correct_path(monkeypatch):
    api = GitLabIssuesAPI(token="x")
    seen = {}
    monkeypatch.setattr(api, "_request", lambda path, **kw: (seen.__setitem__("path", path), {"iid": 3542219})[1])
    out = api.get_issue("project/canvas", "3542219")
    assert seen["path"] == "projects/project%2Fcanvas/issues/3542219"
    assert out["iid"] == 3542219


def test_post_note_requires_token():
    api = GitLabIssuesAPI(token=None)
    try:
        api.post_issue_note("project/canvas", "1", "hi")
        assert False
    except Exception as e:
        assert "token" in str(e).lower()


def test_search_paths(monkeypatch):
    api = GitLabIssuesAPI(token="x")
    calls = []
    monkeypatch.setattr(api, "_request", lambda path, **kw: calls.append(path) or [])
    api.search_project_issues("project/canvas", "playwright")
    api.search_global_issues("playwright")
    assert calls[0].startswith("projects/project%2Fcanvas/issues?")
    assert calls[1].startswith("issues?")
    assert "search=playwright" in calls[0] and "search=playwright" in calls[1]
