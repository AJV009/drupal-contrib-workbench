import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gitlab_label_map import classify_labels, parse_reported_by


def test_classify_full_label_set():
    out = classify_labels(["category::task", "priority::normal", "state::needsWork",
                           "v1.x-dev", "AI Initiative Sprint"])
    assert out["category"]["label"] == "Task"
    assert out["priority"]["label"] == "Normal"
    assert out["status"]["label"] == "Needs work"
    assert out["version"] == "1.x-dev"
    assert "AI Initiative Sprint" in out["tags"]


def test_classify_unknown_state_kept_raw():
    out = classify_labels(["state::somethingNew"])
    assert out["status"]["code"] is None
    assert out["status"]["label"] == "somethingNew"


def test_classify_empty():
    out = classify_labels([])
    assert out["status"]["code"] is None and out["tags"] == []


def test_parse_reported_by_marker():
    desc = "text Reported by: [kunal.sachdev](https://www.drupal.org/user/3685163)\n more"
    who = parse_reported_by(desc)
    assert who == {"name": "kunal.sachdev", "uid": 3685163}


def test_parse_reported_by_absent():
    assert parse_reported_by("no marker here") is None
