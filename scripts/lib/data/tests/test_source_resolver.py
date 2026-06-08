import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from source_resolver import parse_identifier, ResolveError

def test_parse_gitlab_work_items_url():
    r = parse_identifier("https://git.drupalcode.org/project/canvas/-/work_items/3542219")
    assert r == {"source": "gitlab", "project": "project/canvas", "iid": "3542219",
                 "url": "https://git.drupalcode.org/project/canvas/-/work_items/3542219"}

def test_parse_project_hash_shorthand():
    r = parse_identifier("canvas#5")
    assert r == {"source": "gitlab", "project": "project/canvas", "iid": "5",
                 "url": "https://git.drupalcode.org/project/canvas/-/work_items/5"}

def test_parse_classic_do_issue_url_is_not_decided_offline():
    r = parse_identifier("https://www.drupal.org/project/webform/issues/123456")
    assert r["needs_probe"] is True
    assert r["iid"] == "123456"
    assert r["project_hint"] == "webform"

def test_parse_bare_number_needs_probe():
    r = parse_identifier("3542219")
    assert r["needs_probe"] is True
    assert r["iid"] == "3542219"
    assert r.get("project_hint") is None

def test_parse_garbage_raises():
    try:
        parse_identifier("not an issue")
        assert False, "expected ResolveError"
    except ResolveError:
        pass
