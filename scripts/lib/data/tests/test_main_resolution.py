import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fetch_issue
from fetch_issue import FetchLog


def test_mode_related_self_skip_requires_int_issue_id(tmp_path, monkeypatch):
    class FakeAPI:
        def get_project_nid(self, project):
            return 12345

        def fetch_issues_batch(self, nid, max_issues):
            return [
                {"nid": 3542219, "title": "self", "field_issue_status": 1, "changed": 0},
                {"nid": 999, "title": "other", "field_issue_status": 1, "changed": 0},
            ]

    monkeypatch.setattr(fetch_issue, "DrupalOrgAPI", lambda *a, **k: FakeAPI())

    # int issue_id (correct, post-fix) excludes self.
    fetch_issue.mode_related(FetchLog(), tmp_path, "project/canvas", 3542219, 50)
    data = json.loads((tmp_path / "related-issues.json").read_text())
    nids = [i["nid"] for i in data["issues"]]
    assert 3542219 not in nids
    assert 999 in nids

    # str issue_id (pre-fix bug) would fail to exclude self -- this asserts the
    # comparison is int-based and the resolver must cast to int.
    fetch_issue.mode_related(FetchLog(), tmp_path, "project/canvas", "3542219", 50)
    bug_data = json.loads((tmp_path / "related-issues.json").read_text())
    bug_nids = [i["nid"] for i in bug_data["issues"]]
    assert 3542219 in bug_nids  # str != int, self leaks in -> proves the bug
