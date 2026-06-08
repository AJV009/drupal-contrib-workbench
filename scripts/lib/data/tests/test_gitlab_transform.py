import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gitlab_transform import transform_gitlab_issue, transform_gitlab_notes
FX = Path(__file__).resolve().parent / "fixtures"
def _load(name): return json.loads((FX / name).read_text())

def test_transform_issue_unified_shape():
    issue = transform_gitlab_issue(_load("canvas-3542219-issue.json"), project="project/canvas")
    assert issue["source"] == "gitlab"
    assert issue["iid"] == 3542219
    assert issue["nid"] == 3542219
    assert issue["project"] == "canvas"
    assert issue["status"]["label"] == "Needs work"
    assert issue["category"]["label"] == "Task"
    assert issue["priority"]["label"] == "Normal"
    assert issue["version"] == "1.x-dev"
    assert issue["url"] == "https://git.drupalcode.org/project/canvas/-/work_items/3542219"
    assert issue["author"]["name"] == "kunal.sachdev"
    assert isinstance(issue["body_html"], str) and issue["body_html"]

def test_transform_notes_unified_shape():
    notes = transform_gitlab_notes(_load("canvas-3542219-notes.json"), _load("canvas-3542219-label-events.json"))
    assert isinstance(notes, list) and notes
    first = notes[0]
    for key in ("number","cid","author","created","body_html","is_system_message","mr_references","field_changes","images"):
        assert key in first
    assert set(first["author"].keys()) == {"uid", "name"}
    assert [n["number"] for n in notes] == list(range(1, len(notes)+1))
    assert all(isinstance(n["field_changes"], list) for n in notes)

def test_extract_mr_refs_bang_resolves_to_full_url():
    notes = transform_gitlab_notes(
        [{"id": 1, "created_at": "2024-01-01T00:00:00Z", "body": "Fixed in !274"}],
        [],
        project="project/canvas",
    )
    assert "https://git.drupalcode.org/project/canvas/-/merge_requests/274" \
        in notes[0]["mr_references"]

def test_exact_timestamp_label_event_attaches():
    ts = "2024-05-01T12:00:00Z"
    notes = transform_gitlab_notes(
        [{"id": 9, "created_at": ts, "body": "changed status"}],
        [{"created_at": ts, "action": "add",
          "label": {"name": "Status::Needs review"}}],
    )
    changes = notes[0]["field_changes"]
    assert changes == [{"field": "Status", "old": "", "new": "Status::Needs review"}]

def test_transform_notes_since_filter():
    all_notes = _load("canvas-3542219-notes.json")
    cutoff = all_notes[len(all_notes)//2]["created_at"]
    notes = transform_gitlab_notes(all_notes, [], since=cutoff)
    assert all(n["created"] > cutoff for n in notes)
