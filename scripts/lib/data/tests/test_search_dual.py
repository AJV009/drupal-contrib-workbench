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
