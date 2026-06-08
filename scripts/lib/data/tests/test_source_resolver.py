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


from source_resolver import resolve

class _FakeResp:
    def __init__(self, final_url): self._u = final_url
    def geturl(self): return self._u
    def __enter__(self): return self
    def __exit__(self, *a): return False

def test_resolve_bare_number_migrated_to_gitlab():
    opener = lambda url: _FakeResp("https://git.drupalcode.org/project/canvas/-/work_items/3542219")
    r = resolve("3542219", opener=opener)
    assert r["source"] == "gitlab" and r["project"] == "project/canvas" and r["iid"] == "3542219"

def test_resolve_bare_number_still_on_do_queue():
    opener = lambda url: _FakeResp("https://www.drupal.org/project/webform/issues/123456")
    r = resolve("123456", opener=opener)
    assert r["source"] == "do" and r["project"] == "webform" and r["iid"] == "123456"

def test_resolve_gitlab_url_skips_probe():
    def opener(url): raise AssertionError("should not probe a fully-qualified gitlab url")
    r = resolve("https://git.drupalcode.org/project/ai/-/work_items/9", opener=opener)
    assert r["source"] == "gitlab" and r["project"] == "project/ai" and r["iid"] == "9"

def test_resolve_unresolvable_probe_raises_with_hint():
    opener = lambda url: _FakeResp("https://www.drupal.org/not-an-issue")
    try:
        resolve("999999999", opener=opener)
        assert False
    except ResolveError as e:
        assert "project#iid" in str(e)
