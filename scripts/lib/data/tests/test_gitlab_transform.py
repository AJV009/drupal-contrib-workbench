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
    assert any(n["field_changes"] for n in notes)

def test_transform_notes_since_filter():
    all_notes = _load("canvas-3542219-notes.json")
    cutoff = all_notes[len(all_notes)//2]["created_at"]
    notes = transform_gitlab_notes(all_notes, [], since=cutoff)
    assert all(n["created"] > cutoff for n in notes)
