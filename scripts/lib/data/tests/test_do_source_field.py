import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fetch_issue import transform_issue


def test_do_transform_sets_source():
    issue = transform_issue({"nid": "2924003", "title": "x"}, "webform")
    assert issue["source"] == "do"
    assert issue["nid"] == 2924003
