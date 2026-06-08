import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fetch_issue
from gitlab_issues_api import GitLabIssuesAPI

def test_post_note_reads_body_file_and_posts(tmp_path, monkeypatch):
    body_file = tmp_path / "note.md"
    body_file.write_text("Looks good, tested locally.")
    captured = {}
    monkeypatch.setattr(GitLabIssuesAPI, "post_issue_note",
                        lambda self, p, i, b: captured.update(project=p, iid=i, body=b) or {"id": 999})
    out = fetch_issue.mode_post_note(project="project/canvas", issue_id="3542219",
                                     body_file=str(body_file), gitlab_token_file="/tmp/does-not-exist")
    assert captured["body"] == "Looks good, tested locally."
    assert out["id"] == 999
