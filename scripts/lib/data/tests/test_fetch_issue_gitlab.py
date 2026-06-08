import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fetch_issue
from gitlab_issues_api import GitLabIssuesAPI
from gitlab_api import GitLabAPI
FX = Path(__file__).resolve().parent / "fixtures"

def test_mode_full_gitlab_emits_unified_files(tmp_path, monkeypatch):
    issue = json.loads((FX / "canvas-3542219-issue.json").read_text())
    notes = json.loads((FX / "canvas-3542219-notes.json").read_text())
    events = json.loads((FX / "canvas-3542219-label-events.json").read_text())
    monkeypatch.setattr(GitLabIssuesAPI, "get_issue", lambda self, p, i: issue)
    monkeypatch.setattr(GitLabIssuesAPI, "get_issue_notes", lambda self, p, i: notes)
    monkeypatch.setattr(GitLabIssuesAPI, "get_resource_label_events", lambda self, p, i: events)
    monkeypatch.setattr(GitLabAPI, "search_merge_requests", lambda self, p, i: [])
    log = fetch_issue.FetchLog()
    rc = fetch_issue.mode_full(log, out_dir=tmp_path, project="project/canvas",
                               issue_id="3542219", source="gitlab", gitlab_token_file=None)
    assert rc == 0
    issue_out = json.loads((tmp_path / "issue.json").read_text())
    assert issue_out["source"] == "gitlab" and issue_out["nid"] == 3542219
    comments_env = json.loads((tmp_path / "comments.json").read_text())
    assert comments_env["source"] == "gitlab"
    assert comments_env["comments"][0]["number"] == 1
