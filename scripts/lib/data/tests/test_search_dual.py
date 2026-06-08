import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fetch_issue
from gitlab_issues_api import GitLabIssuesAPI

def test_search_merges_do_and_gitlab(monkeypatch):
    monkeypatch.setattr(fetch_issue, "_search_do",
                        lambda project, kw: [{"id": "111", "title": "do hit", "source": "do"}],
                        raising=False)
    monkeypatch.setattr(GitLabIssuesAPI, "search_project_issues",
                        lambda self, p, kw: [{"iid": 5, "title": "gl hit", "web_url": "u"}])
    monkeypatch.setattr(GitLabIssuesAPI, "search_global_issues", lambda self, kw: [])
    results = fetch_issue.search_all(project="project/canvas", keywords="playwright",
                                     gitlab_token_file=None)
    titles = {r["title"] for r in results}
    assert "do hit" in titles and "gl hit" in titles
    assert all("source" in r for r in results)


def test_search_gitlab_receives_joined_keyword_string(monkeypatch):
    captured = {}
    monkeypatch.setattr(fetch_issue, "_search_do",
                        lambda project, kw: [], raising=False)

    def cap_project(self, p, kw):
        captured["project"] = kw
        return []

    def cap_global(self, kw):
        captured["global"] = kw
        return []

    monkeypatch.setattr(GitLabIssuesAPI, "search_project_issues", cap_project)
    monkeypatch.setattr(GitLabIssuesAPI, "search_global_issues", cap_global)
    fetch_issue.search_all(project="project/canvas",
                           keywords=["timezone", "datetime"],
                           gitlab_token_file=None)
    assert captured["project"] == "timezone datetime"
    assert captured["global"] == "timezone datetime"
