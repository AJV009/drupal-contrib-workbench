import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fetch_issue
from gitlab_issues_api import GitLabIssuesAPI

# Canonical match keys both sources must emit.
MATCH_KEYS = {"source", "id", "nid", "title", "status_code", "status_label", "url", "changed"}


def test_search_merges_do_and_gitlab(monkeypatch):
    monkeypatch.setattr(fetch_issue, "_search_do",
                        lambda project, kw: ([fetch_issue._normalize_match(
                            "do", id="111", nid=111, title="do hit",
                            status_code=1, status_label="Active",
                            url="http://x", changed=None)], 42),
                        raising=False)
    monkeypatch.setattr(GitLabIssuesAPI, "search_project_issues",
                        lambda self, p, kw: [{"iid": 5, "title": "gl hit", "web_url": "u",
                                              "labels": ["state::needsWork"], "state": "opened",
                                              "updated_at": "2026-01-01T00:00:00Z"}])
    monkeypatch.setattr(GitLabIssuesAPI, "search_global_issues", lambda self, kw: [])
    result = fetch_issue.search_all(project="project/canvas", keywords="playwright",
                                    gitlab_token_file=None)
    titles = {r["title"] for r in result["matches"]}
    assert "do hit" in titles and "gl hit" in titles
    assert result["total_scanned"] == 42
    assert result["errors"] == []


def test_matches_are_homogeneous(monkeypatch):
    monkeypatch.setattr(fetch_issue, "_search_do",
                        lambda project, kw: ([fetch_issue._normalize_match(
                            "do", id="111", nid=111, title="do hit",
                            status_code=1, status_label="Active",
                            url="http://x", changed=None)], 1),
                        raising=False)
    monkeypatch.setattr(GitLabIssuesAPI, "search_project_issues",
                        lambda self, p, kw: [{"iid": 5, "title": "gl hit", "web_url": "u",
                                              "labels": ["state::needsWork"], "state": "opened",
                                              "updated_at": "2026-01-01T00:00:00Z"}])
    monkeypatch.setattr(GitLabIssuesAPI, "search_global_issues", lambda self, kw: [])
    result = fetch_issue.search_all(project="project/canvas", keywords="x", gitlab_token_file=None)
    for m in result["matches"]:
        assert set(m.keys()) == MATCH_KEYS
    gl = next(m for m in result["matches"] if m["source"] == "gitlab")
    assert gl["nid"] == 5 and gl["status_label"] == "Needs work"
    assert gl["changed"] == "2026-01-01T00:00:00Z"


def test_gitlab_no_state_label_falls_back_to_gitlab_state(monkeypatch):
    monkeypatch.setattr(fetch_issue, "_search_do", lambda project, kw: ([], 0), raising=False)
    monkeypatch.setattr(GitLabIssuesAPI, "search_project_issues",
                        lambda self, p, kw: [{"iid": 9, "title": "t", "web_url": "u",
                                              "labels": [], "state": "closed",
                                              "updated_at": "2026-02-02T00:00:00Z"}])
    monkeypatch.setattr(GitLabIssuesAPI, "search_global_issues", lambda self, kw: [])
    result = fetch_issue.search_all(project="project/canvas", keywords="x", gitlab_token_file=None)
    gl = result["matches"][0]
    assert gl["status_code"] is None and gl["status_label"] == "Closed"


def test_do_failure_recorded_not_fatal(monkeypatch):
    def boom(project, kw):
        raise ValueError("nope")
    monkeypatch.setattr(fetch_issue, "_search_do", boom, raising=False)
    monkeypatch.setattr(GitLabIssuesAPI, "search_project_issues",
                        lambda self, p, kw: [{"iid": 1, "title": "g", "web_url": "u",
                                              "labels": [], "state": "opened", "updated_at": None}])
    monkeypatch.setattr(GitLabIssuesAPI, "search_global_issues", lambda self, kw: [])
    result = fetch_issue.search_all(project="project/canvas", keywords="x", gitlab_token_file=None)
    assert result["errors"] and result["errors"][0]["source"] == "do"
    assert len(result["matches"]) == 1  # gitlab still returned


def test_search_gitlab_receives_joined_keyword_string(monkeypatch):
    captured = {}
    monkeypatch.setattr(fetch_issue, "_search_do", lambda project, kw: ([], 0), raising=False)

    def cap_project(self, p, kw):
        captured["project"] = kw
        return []

    def cap_global(self, kw):
        captured["global"] = kw
        return []

    monkeypatch.setattr(GitLabIssuesAPI, "search_project_issues", cap_project)
    monkeypatch.setattr(GitLabIssuesAPI, "search_global_issues", cap_global)
    fetch_issue.search_all(project="project/canvas", keywords=["timezone", "datetime"],
                           gitlab_token_file=None)
    assert captured["project"] == "timezone datetime"
    assert captured["global"] == "timezone datetime"
