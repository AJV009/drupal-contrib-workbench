# Dual-Source GitLab Issues Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach the workbench to fetch and process drupal.org issues that have migrated to GitLab work-items, alongside the legacy d.o issue queue, behind one auto-detecting entry point.

**Architecture:** Approach A (source-adapter). A single `resolve_source()` chokepoint redirect-probes an identifier and returns `(source, project, iid)`. A new `gitlab_issues_api.py` client plus a `gitlab_label_map.py` mapper feed `transform_gitlab_issue()` / `transform_gitlab_notes()` which emit the **identical** `issue.json` / `comments.json` schema the d.o path already produces (plus a `source` field and `nid`==`iid` alias). Every `fetch_issue.py` mode branches on `source`; downstream skills consume the unified schema unchanged.

**Tech Stack:** Python 3 (stdlib `urllib`, no new deps), pytest (laptop unit tests), bash CLI smoke (g5 runtime). GitLab REST v4 on `git.drupalcode.org`. Token via existing `--gitlab-token-file` (`git.drupalcode.org.key`).

---

## Ground-truth reference (verified live against canvas/3542219)

- Issue: `GET /api/v4/projects/{enc}/issues/{iid}` (public read, HTTP 200 unauth). Fields used: `iid`, `project_id`, `title`, `description`, `state` (`opened|closed`), `labels` (list of strings), `author{username,name}`, `assignees[]`, `user_notes_count`, `created_at`, `updated_at`, `web_url`.
- Notes: `GET /api/v4/projects/{enc}/issues/{iid}/notes?per_page=100&sort=asc`. Fields: `id`, `type` (null for issue notes; `DiffNote` only on MRs), `system` (bool), `created_at`, `updated_at`, `author{username,name}`, `body`.
- Label events: `GET /api/v4/projects/{enc}/issues/{iid}/resource_label_events?per_page=100`. Fields: `action` (`add|remove`), `created_at`, `label{name}` (may be null if label deleted), `user{username}`.
- Scoped labels: `state::needsWork`, `category::task`, `priority::normal`, plus a bare version label `v1.x-dev`. Migrated issues have GitLab `author.username == "drupalbot"`; real reporter is in the description marker `Reported by: [name](https://www.drupal.org/user/ID)`.
- Search: project `GET /api/v4/projects/{enc}/issues?search=<kw>` (200) and global `GET /api/v4/issues?search=<kw>&scope=all` (200).
- Encoding: project namespace `project/canvas` -> `project%2Fcanvas` (same as `gitlab_api.py`).
- `https://www.drupal.org/i/3542219` redirect-resolves (final URL) to `https://git.drupalcode.org/project/canvas/-/work_items/3542219`.

## File structure

- Create `scripts/lib/data/source_resolver.py` - identifier parsing + redirect probe -> `(source, project, iid, url)`.
- Create `scripts/lib/data/gitlab_label_map.py` - scoped-label <-> d.o code/label mapping (pure).
- Create `scripts/lib/data/gitlab_issues_api.py` - GitLab issue/notes/label-events/post-note client.
- Modify `scripts/lib/data/fetch_issue.py` - add `transform_gitlab_issue/notes`, source branching in modes, `--source`, `post-note` mode, dual-source search.
- Create `scripts/lib/data/tests/` - pytest unit tests + captured fixture `fixtures/canvas-3542219-issue.json`, `fixtures/canvas-3542219-notes.json`, `fixtures/canvas-3542219-label-events.json`.
- Modify `drupal-issue.sh` - resolve identifier, key on iid.
- Modify skills: `.claude/skills/drupal-issue/SKILL.md`, `drupal-issue-review/SKILL.md`, `drupal-issue-comment/SKILL.md`, `drupal-contribute-fix/SKILL.md`.
- Modify docs: `docs/fetcher-modes-reference.md`, `docs/workflow-state-files.md`, `.claude/agents/drupal-issue-fetcher.md`, `CLAUDE.md`.

**Test command (unit, laptop):** `cd scripts/lib/data && python3 -m pytest tests/ -v`
**Smoke (g5 runtime):** `ssh alphons@alphons-g55500` then `./scripts/fetch-issue ...` / `./drupal-issue.sh ...`.

All `unittest`/pytest tests are written as plain `def test_*` functions (pytest style, matching `test_depth_gate_triggers.py`). Network is never hit in unit tests - the redirect probe and HTTP clients are injected/monkeypatched.

---

## Task 1: Source resolver - identifier parsing (no network)

**Files:**
- Create: `scripts/lib/data/source_resolver.py`
- Test: `scripts/lib/data/tests/test_source_resolver.py`

- [ ] **Step 1: Write failing tests for the pure-parse cases**

```python
# tests/test_source_resolver.py
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
    # A classic d.o URL needs a probe to know if it migrated; parse returns probe=True.
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
```

- [ ] **Step 2: Run to verify fail**

Run: `cd scripts/lib/data && python3 -m pytest tests/test_source_resolver.py -v`
Expected: FAIL (`No module named 'source_resolver'`).

- [ ] **Step 3: Implement `parse_identifier`**

```python
# source_resolver.py
"""Resolve an issue identifier to its hosting source (d.o queue vs GitLab work-item).

A migrated issue keeps its old NID as the GitLab IID, so a bare number is resolved
by following the drupal.org redirect. New GitLab-native issues use small per-project
IIDs that collide across projects, so they must be given as a full work-items URL or
`project#iid` shorthand.
"""
from __future__ import annotations

import re
from typing import Optional

GITLAB_HOST = "git.drupalcode.org"


class ResolveError(Exception):
    pass


def _gitlab_url(project: str, iid: str) -> str:
    return f"https://{GITLAB_HOST}/{project}/-/work_items/{iid}"


def parse_identifier(identifier: str) -> dict:
    """Parse an identifier offline. Returns a dict; if the source cannot be known
    without a network probe it sets needs_probe=True (bare number / classic d.o URL)."""
    s = (identifier or "").strip()
    if not s:
        raise ResolveError("empty identifier")

    # GitLab work-items URL
    m = re.match(r"https?://git\.drupalcode\.org/(project/[^/]+)/-/work_items/(\d+)", s)
    if m:
        project, iid = m.group(1), m.group(2)
        return {"source": "gitlab", "project": project, "iid": iid,
                "url": _gitlab_url(project, iid)}

    # project#iid shorthand
    m = re.match(r"^([A-Za-z0-9_]+)#(\d+)$", s)
    if m:
        project = f"project/{m.group(1)}"
        iid = m.group(2)
        return {"source": "gitlab", "project": project, "iid": iid,
                "url": _gitlab_url(project, iid)}

    # classic d.o issue URL -> project hint, but migration status needs a probe
    m = re.match(r"https?://www\.drupal\.org/project/([^/]+)/issues/(\d+)", s)
    if m:
        return {"needs_probe": True, "iid": m.group(2), "project_hint": m.group(1)}

    # d.o short /i/ URL
    m = re.match(r"https?://www\.drupal\.org/i/(\d+)", s)
    if m:
        return {"needs_probe": True, "iid": m.group(1), "project_hint": None}

    # bare number
    if re.match(r"^\d+$", s):
        return {"needs_probe": True, "iid": s, "project_hint": None}

    raise ResolveError(f"unrecognized issue identifier: {identifier!r}")
```

- [ ] **Step 4: Run to verify pass**

Run: `cd scripts/lib/data && python3 -m pytest tests/test_source_resolver.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/data/source_resolver.py scripts/lib/data/tests/test_source_resolver.py
git commit -m "feat(fetcher): add offline issue identifier parser"
```

---

## Task 2: Source resolver - redirect probe (injectable opener)

**Files:**
- Modify: `scripts/lib/data/source_resolver.py`
- Test: `scripts/lib/data/tests/test_source_resolver.py`

- [ ] **Step 1: Write failing tests with a fake opener**

```python
# append to tests/test_source_resolver.py
from source_resolver import resolve


class _FakeResp:
    def __init__(self, final_url):
        self._u = final_url
    def geturl(self):
        return self._u
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def test_resolve_bare_number_migrated_to_gitlab():
    opener = lambda url: _FakeResp("https://git.drupalcode.org/project/canvas/-/work_items/3542219")
    r = resolve("3542219", opener=opener)
    assert r["source"] == "gitlab"
    assert r["project"] == "project/canvas"
    assert r["iid"] == "3542219"


def test_resolve_bare_number_still_on_do_queue():
    opener = lambda url: _FakeResp("https://www.drupal.org/project/webform/issues/123456")
    r = resolve("123456", opener=opener)
    assert r["source"] == "do"
    assert r["project"] == "webform"
    assert r["iid"] == "123456"


def test_resolve_gitlab_url_skips_probe():
    def opener(url):
        raise AssertionError("should not probe a fully-qualified gitlab url")
    r = resolve("https://git.drupalcode.org/project/ai/-/work_items/9", opener=opener)
    assert r["source"] == "gitlab" and r["project"] == "project/ai" and r["iid"] == "9"


def test_resolve_unresolvable_probe_raises_with_hint():
    opener = lambda url: _FakeResp("https://www.drupal.org/not-an-issue")
    try:
        resolve("999999999", opener=opener)
        assert False
    except ResolveError as e:
        assert "project#iid" in str(e)
```

- [ ] **Step 2: Run to verify fail**

Run: `cd scripts/lib/data && python3 -m pytest tests/test_source_resolver.py -v`
Expected: FAIL (`cannot import name 'resolve'`).

- [ ] **Step 3: Implement `resolve` with a default urllib opener**

```python
# append to source_resolver.py
import urllib.request

_DEFAULT_UA = "drupal-contribute-fix/1.0 (community contribution helper)"


def _default_opener(url: str):
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": _DEFAULT_UA})
    return urllib.request.urlopen(req, timeout=20)


def resolve(identifier: str, opener=None) -> dict:
    """Resolve an identifier to {source, project, iid, url}. Probes the d.o redirect
    only when the offline parse cannot decide. `opener(url)` is injectable for tests;
    it must return a context manager exposing geturl() (the final, post-redirect URL)."""
    parsed = parse_identifier(identifier)
    if not parsed.get("needs_probe"):
        return parsed

    iid = parsed["iid"]
    probe_url = (f"https://www.drupal.org/project/{parsed['project_hint']}/issues/{iid}"
                 if parsed.get("project_hint") else f"https://www.drupal.org/i/{iid}")
    open_fn = opener or _default_opener
    try:
        with open_fn(probe_url) as resp:
            final = resp.geturl()
    except Exception as e:  # noqa: BLE001 - surface as a resolve failure
        raise ResolveError(f"redirect probe failed for {probe_url}: {e}")

    m = re.match(r"https?://git\.drupalcode\.org/(project/[^/]+)/-/work_items/(\d+)", final)
    if m:
        project, riid = m.group(1), m.group(2)
        return {"source": "gitlab", "project": project, "iid": riid, "url": final}

    m = re.match(r"https?://www\.drupal\.org/project/([^/]+)/issues/(\d+)", final)
    if m:
        return {"source": "do", "project": m.group(1), "iid": m.group(2), "url": final}

    raise ResolveError(
        f"could not resolve {identifier!r} (final url: {final}). "
        f"For a GitLab-native issue pass a full work_items URL or `project#iid`."
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `cd scripts/lib/data && python3 -m pytest tests/test_source_resolver.py -v`
Expected: PASS (9 tests total).

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/data/source_resolver.py scripts/lib/data/tests/test_source_resolver.py
git commit -m "feat(fetcher): add redirect-probe source resolution"
```

---

## Task 3: GitLab scoped-label map (pure)

**Files:**
- Create: `scripts/lib/data/gitlab_label_map.py`
- Test: `scripts/lib/data/tests/test_gitlab_label_map.py`

Note: status/priority/category code+label dicts must match `drupalorg_api.py` (`ISSUE_STATUS`, `ISSUE_PRIORITY`, `ISSUE_CATEGORY`). Read those dicts first and reuse the exact label strings and codes.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_gitlab_label_map.py
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
    desc = ("text Reported by: [kunal.sachdev](https://www.drupal.org/user/3685163)\n more")
    who = parse_reported_by(desc)
    assert who == {"name": "kunal.sachdev", "uid": 3685163}


def test_parse_reported_by_absent():
    assert parse_reported_by("no marker here") is None
```

- [ ] **Step 2: Run to verify fail**

Run: `cd scripts/lib/data && python3 -m pytest tests/test_gitlab_label_map.py -v`
Expected: FAIL (`No module named 'gitlab_label_map'`).

- [ ] **Step 3: Implement the mapper**

```python
# gitlab_label_map.py
"""Map GitLab scoped labels to the d.o issue code/label model used by issue.json.

Slug values (needsWork, needsReview, rtbc, ...) are matched case-insensitively
after stripping non-alphanumerics, so `state::needsWork` lines up with the d.o
status label "Needs work".
"""
from __future__ import annotations

import re
from typing import Optional

# d.o status code -> label (subset that GitLab state:: slugs map onto).
# Codes mirror drupalorg_api.ISSUE_STATUS.
STATUS_BY_SLUG = {
    "active": (1, "Active"),
    "needswork": (13, "Needs work"),
    "needsreview": (8, "Needs review"),
    "rtbc": (14, "Reviewed & tested by the community"),
    "patchtobereviewed": (8, "Needs review"),
    "fixed": (2, "Fixed"),
    "closedfixed": (7, "Closed (fixed)"),
    "closedduplicate": (18, "Closed (duplicate)"),
    "closedwontfix": (16, "Closed (won't fix)"),
    "closedcannotreproduce": (17, "Closed (cannot reproduce)"),
    "closedoutdated": (15, "Closed (outdated)"),
    "closedworksasdesigned": (4, "Closed (works as designed)"),
    "postponed": (4, "Postponed"),
    "postponedmaintainerneedsmoreinfo": (16, "Postponed (maintainer needs more info)"),
    "todo": (1, "Active"),
}
PRIORITY_BY_SLUG = {
    "critical": (400, "Critical"),
    "major": (300, "Major"),
    "normal": (200, "Normal"),
    "minor": (100, "Minor"),
}
CATEGORY_BY_SLUG = {
    "bug": (1, "Bug report"),
    "task": (2, "Task"),
    "feature": (3, "Feature request"),
    "support": (4, "Support request"),
    "plan": (5, "Plan"),
}

_VERSION_RE = re.compile(r"^v?(\d+\.[0-9x]+(?:-[A-Za-z0-9.]+)?)$")
_REPORTED_BY_RE = re.compile(
    r"Reported by:\s*\[([^\]]+)\]\(https://www\.drupal\.org/user/(\d+)\)")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _lookup(table, raw_value):
    hit = table.get(_slug(raw_value))
    if hit:
        return {"code": hit[0], "label": hit[1]}
    return {"code": None, "label": raw_value}


def classify_labels(labels) -> dict:
    out = {
        "status": {"code": None, "label": None},
        "priority": {"code": None, "label": None},
        "category": {"code": None, "label": None},
        "version": None,
        "tags": [],
    }
    for label in labels or []:
        if "::" in label:
            scope, value = label.split("::", 1)
            scope = scope.strip().lower()
            if scope == "state":
                out["status"] = _lookup(STATUS_BY_SLUG, value.strip())
            elif scope == "priority":
                out["priority"] = _lookup(PRIORITY_BY_SLUG, value.strip())
            elif scope == "category":
                out["category"] = _lookup(CATEGORY_BY_SLUG, value.strip())
            else:
                out["tags"].append(label)
            continue
        m = _VERSION_RE.match(label.strip())
        if m and out["version"] is None:
            out["version"] = m.group(1)
        else:
            out["tags"].append(label)
    return out


def parse_reported_by(description: str) -> Optional[dict]:
    if not description:
        return None
    m = _REPORTED_BY_RE.search(description)
    if not m:
        return None
    return {"name": m.group(1), "uid": int(m.group(2))}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd scripts/lib/data && python3 -m pytest tests/test_gitlab_label_map.py -v`
Expected: PASS (5 tests). If status/category labels differ from `drupalorg_api.py`, align the strings to that module and re-run.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/data/gitlab_label_map.py scripts/lib/data/tests/test_gitlab_label_map.py
git commit -m "feat(fetcher): map GitLab scoped labels to d.o issue model"
```

---

## Task 4: Capture live fixtures (g5, one-time)

**Files:**
- Create: `scripts/lib/data/tests/fixtures/canvas-3542219-issue.json`
- Create: `scripts/lib/data/tests/fixtures/canvas-3542219-notes.json`
- Create: `scripts/lib/data/tests/fixtures/canvas-3542219-label-events.json`

- [ ] **Step 1: Capture from g5 (token read only)**

```bash
ssh alphons@alphons-g55500 'T=$(cat /mnt/data/drupal/CONTRIB_WORKBENCH/git.drupalcode.org.key)
B=https://git.drupalcode.org/api/v4/projects/project%2Fcanvas/issues/3542219
curl -s -H "PRIVATE-TOKEN: $T" "$B"
echo "---NOTES---"
curl -s -H "PRIVATE-TOKEN: $T" "$B/notes?per_page=100&sort=asc"
echo "---EVENTS---"
curl -s -H "PRIVATE-TOKEN: $T" "$B/resource_label_events?per_page=100"' > /tmp/canvas_capture.txt
```

Split `/tmp/canvas_capture.txt` on the `---NOTES---` / `---EVENTS---` markers into the three fixture files (pretty-print with `python3 -m json.tool`). Keep them verbatim - they are the regression baseline.

- [ ] **Step 2: Verify they are valid JSON**

Run: `for f in scripts/lib/data/tests/fixtures/canvas-3542219-*.json; do python3 -m json.tool "$f" >/dev/null && echo "OK $f"; done`
Expected: three `OK` lines.

- [ ] **Step 3: Commit**

```bash
git add scripts/lib/data/tests/fixtures/
git commit -m "test(fetcher): capture canvas/3542219 GitLab issue fixtures"
```

---

## Task 5: GitLab transforms -> unified schema

**Files:**
- Create: `scripts/lib/data/gitlab_transform.py`
- Test: `scripts/lib/data/tests/test_gitlab_transform.py`

Read `transform_issue()` in `drupalorg_api.py` / `fetch_issue.py` first and copy its output keys exactly. The asserts below encode the required shared schema; adjust key names to match the real d.o output if they differ, then keep both paths identical.

- [ ] **Step 1: Write failing tests against fixtures**

```python
# tests/test_gitlab_transform.py
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gitlab_transform import transform_gitlab_issue, transform_gitlab_notes

FX = Path(__file__).resolve().parent / "fixtures"


def _load(name):
    return json.loads((FX / name).read_text())


def test_transform_issue_unified_shape():
    issue = transform_gitlab_issue(_load("canvas-3542219-issue.json"), project="project/canvas")
    assert issue["source"] == "gitlab"
    assert issue["iid"] == 3542219
    assert issue["nid"] == 3542219            # alias for downstream DRUPAL_ISSUES/{id} keying
    assert issue["project"] == "canvas"
    assert issue["status"]["label"] == "Needs work"
    assert issue["category"]["label"] == "Task"
    assert issue["priority"]["label"] == "Normal"
    assert issue["version"] == "1.x-dev"
    assert issue["url"] == "https://git.drupalcode.org/project/canvas/-/work_items/3542219"
    # migrated author backfilled from the description marker, not "drupalbot"
    assert issue["author"]["name"] == "kunal.sachdev"
    assert isinstance(issue["body_html"], str) and issue["body_html"]


def test_transform_notes_unified_shape():
    # transform_gitlab_notes returns the bare comment LIST; mode_full wraps it in
    # the {issue_id,total_count,source,since,comments:[...]} envelope (see Task 7).
    notes = transform_gitlab_notes(
        _load("canvas-3542219-notes.json"),
        _load("canvas-3542219-label-events.json"))
    assert isinstance(notes, list) and notes
    first = notes[0]
    # d.o comment schema keys (process_comments) + superset field_changes/images
    for key in ("number", "cid", "author", "created", "body_html",
                "is_system_message", "mr_references", "field_changes", "images"):
        assert key in first
    assert set(first["author"].keys()) == {"uid", "name"}
    # numbering is 1-based and sequential
    assert [n["number"] for n in notes] == list(range(1, len(notes) + 1))
    # at least one label event surfaced as a field change
    assert any(n["field_changes"] for n in notes)


def test_transform_notes_since_filter():
    all_notes = _load("canvas-3542219-notes.json")
    cutoff = all_notes[len(all_notes)//2]["created_at"]
    notes = transform_gitlab_notes(all_notes, [], since=cutoff)
    assert all(n["created"] > cutoff for n in notes)
```

- [ ] **Step 2: Run to verify fail**

Run: `cd scripts/lib/data && python3 -m pytest tests/test_gitlab_transform.py -v`
Expected: FAIL (`No module named 'gitlab_transform'`).

- [ ] **Step 3: Implement transforms**

```python
# gitlab_transform.py
"""Transform GitLab issue + notes + label events into the workbench's unified
issue.json / comments.json schema (the same shape the d.o path emits)."""
from __future__ import annotations

import re
from typing import List, Optional

from gitlab_label_map import classify_labels, parse_reported_by

_MR_REF_RE = re.compile(r"(?:!(\d+)|https://git\.drupalcode\.org/\S+/merge_requests/\d+)")
_IMG_RE = re.compile(r'!\[[^\]]*\]\((\S+?)\)|<img[^>]+src="([^"]+)"')


def _project_short(project: str) -> str:
    return project.split("/", 1)[1] if "/" in project else project


def transform_gitlab_issue(raw: dict, project: str) -> dict:
    labels = classify_labels(raw.get("labels", []))
    reporter = parse_reported_by(raw.get("description", ""))
    gl_author = raw.get("author", {}) or {}
    author = (reporter if reporter
              else {"name": gl_author.get("name") or gl_author.get("username"), "uid": None})
    assignees = raw.get("assignees", []) or []
    return {
        "source": "gitlab",
        "iid": raw["iid"],
        "nid": raw["iid"],
        "title": raw.get("title", ""),
        "url": f"https://git.drupalcode.org/{project}/-/work_items/{raw['iid']}",
        "project": _project_short(project),
        "status": labels["status"],
        "priority": labels["priority"],
        "category": labels["category"],
        "component": "",
        "version": labels["version"],
        "author": author,
        "assigned": ({"name": assignees[0].get("username"), "uid": assignees[0].get("id")}
                     if assignees else None),
        "created": raw.get("created_at"),
        "changed": raw.get("updated_at"),
        "comment_count": raw.get("user_notes_count", 0),
        "body_html": raw.get("description", "") or "",
        "related_issues": [],
        "parent_issue": None,
        "tags": labels["tags"],
        "files": [],
    }


def _label_events_to_changes(events, note_created):
    """Attach label add/remove events that share a note's timestamp as field_changes."""
    changes = []
    for ev in events or []:
        if ev.get("created_at") != note_created:
            continue
        label = (ev.get("label") or {}).get("name", "")
        field = label.split("::", 1)[0] if "::" in label else "label"
        if ev.get("action") == "add":
            changes.append({"field": field, "old": "", "new": label})
        else:
            changes.append({"field": field, "old": label, "new": ""})
    return changes


def _extract_mr_refs(body: str) -> List[str]:
    return list({m.group(0) for m in _MR_REF_RE.finditer(body or "")})


def _extract_images(body: str) -> List[str]:
    out = []
    for m in _IMG_RE.finditer(body or ""):
        out.append(m.group(1) or m.group(2))
    return [u for u in out if u]


def transform_gitlab_notes(raw_notes, label_events, since: Optional[str] = None) -> list:
    notes = sorted(raw_notes or [], key=lambda n: n.get("created_at", ""))
    out = []
    number = 0
    for n in notes:
        created = n.get("created_at")
        if since and not (created and created > since):
            continue
        number += 1
        author = n.get("author", {}) or {}
        body = n.get("body", "") or ""
        out.append({
            "number": number,
            "cid": str(n.get("id")),
            "author": {"uid": author.get("id"),
                       "name": author.get("name") or author.get("username")},
            "created": created,
            "body_html": body,
            "is_system_message": bool(n.get("system")),
            "mr_references": _extract_mr_refs(body),
            "field_changes": _label_events_to_changes(label_events, created),
            "images": _extract_images(body),
        })
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `cd scripts/lib/data && python3 -m pytest tests/test_gitlab_transform.py -v`
Expected: PASS (3 tests). If `author.name` assert fails, confirm the fixture description actually carries the `Reported by:` marker; adjust the test's expected name to the fixture's real reporter.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/data/gitlab_transform.py scripts/lib/data/tests/test_gitlab_transform.py
git commit -m "feat(fetcher): transform GitLab issue/notes to unified schema"
```

---

## Task 6: GitLab issues API client

**Files:**
- Create: `scripts/lib/data/gitlab_issues_api.py`
- Test: `scripts/lib/data/tests/test_gitlab_issues_api.py`

Mirror `gitlab_api.py`: same `from_token_file` classmethod, `MIN_REQUEST_INTERVAL` rate-limit, `_encode_project`, `PRIVATE-TOKEN` header, pagination by `?page=`/`per_page=100`. The client is thin; transforms live in Task 5. Tests inject a fake `_request` to avoid network.

- [ ] **Step 1: Write failing tests with injected transport**

```python
# tests/test_gitlab_issues_api.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gitlab_issues_api import GitLabIssuesAPI


def test_get_issue_builds_correct_path(monkeypatch):
    api = GitLabIssuesAPI(token="x")
    seen = {}
    monkeypatch.setattr(api, "_request", lambda path, **kw: seen.setdefault("path", path) or {"iid": 3542219})
    out = api.get_issue("project/canvas", "3542219")
    assert seen["path"] == "projects/project%2Fcanvas/issues/3542219"
    assert out["iid"] == 3542219


def test_post_note_requires_token():
    api = GitLabIssuesAPI(token=None)
    try:
        api.post_issue_note("project/canvas", "1", "hi")
        assert False
    except Exception as e:
        assert "token" in str(e).lower()


def test_search_paths(monkeypatch):
    api = GitLabIssuesAPI(token="x")
    calls = []
    monkeypatch.setattr(api, "_request", lambda path, **kw: calls.append(path) or [])
    api.search_project_issues("project/canvas", "playwright")
    api.search_global_issues("playwright")
    assert calls[0].startswith("projects/project%2Fcanvas/issues?")
    assert calls[1].startswith("issues?")
    assert "search=playwright" in calls[0] and "search=playwright" in calls[1]
```

- [ ] **Step 2: Run to verify fail**

Run: `cd scripts/lib/data && python3 -m pytest tests/test_gitlab_issues_api.py -v`
Expected: FAIL (`No module named 'gitlab_issues_api'`).

- [ ] **Step 3: Implement the client**

```python
# gitlab_issues_api.py
"""Read (and optionally post to) GitLab work-item issues on git.drupalcode.org."""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List, Optional

GITLAB_API = "https://git.drupalcode.org/api/v4"
MIN_REQUEST_INTERVAL = 0.5
_UA = "drupal-contribute-fix/1.0 (community contribution helper)"


class GitLabIssuesError(Exception):
    pass


class GitLabIssuesAPI:
    def __init__(self, token: Optional[str] = None):
        self.token = token
        self._last = 0.0

    @classmethod
    def from_token_file(cls, token_path: str) -> "GitLabIssuesAPI":
        p = Path(token_path)
        if not p.exists():
            return cls(token=None)
        try:
            t = p.read_text().strip()
            return cls(token=t or None)
        except OSError:
            return cls(token=None)

    @staticmethod
    def _encode_project(project: str) -> str:
        return urllib.parse.quote(project, safe="")

    def _throttle(self):
        dt = time.monotonic() - self._last
        if dt < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - dt)
        self._last = time.monotonic()

    def _request(self, path: str, method: str = "GET", data: Optional[bytes] = None):
        self._throttle()
        url = f"{GITLAB_API}/{path}"
        headers = {"User-Agent": _UA}
        if self.token:
            headers["PRIVATE-TOKEN"] = self.token
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, method=method, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else None
        except urllib.error.HTTPError as e:
            raise GitLabIssuesError(f"GitLab {method} {path} -> HTTP {e.code}: {e.reason}")

    # --- reads ---
    def get_issue(self, project: str, iid: str) -> dict:
        return self._request(f"projects/{self._encode_project(project)}/issues/{iid}")

    def get_issue_notes(self, project: str, iid: str) -> List[dict]:
        enc = self._encode_project(project)
        out, page = [], 1
        while True:
            batch = self._request(
                f"projects/{enc}/issues/{iid}/notes?per_page=100&sort=asc&page={page}")
            if not batch:
                break
            out.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return out

    def get_resource_label_events(self, project: str, iid: str) -> List[dict]:
        enc = self._encode_project(project)
        return self._request(f"projects/{enc}/issues/{iid}/resource_label_events?per_page=100") or []

    def search_project_issues(self, project: str, keywords: str) -> List[dict]:
        enc = self._encode_project(project)
        q = urllib.parse.urlencode({"search": keywords, "per_page": 20, "state": "all"})
        return self._request(f"projects/{enc}/issues?{q}") or []

    def search_global_issues(self, keywords: str) -> List[dict]:
        q = urllib.parse.urlencode({"search": keywords, "scope": "all", "per_page": 20})
        return self._request(f"issues?{q}") or []

    # --- write ---
    def post_issue_note(self, project: str, iid: str, body: str) -> dict:
        if not self.token:
            raise GitLabIssuesError("posting a note requires a write-scoped PRIVATE-TOKEN")
        enc = self._encode_project(project)
        payload = json.dumps({"body": body}).encode("utf-8")
        return self._request(f"projects/{enc}/issues/{iid}/notes", method="POST", data=payload)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd scripts/lib/data && python3 -m pytest tests/test_gitlab_issues_api.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/data/gitlab_issues_api.py scripts/lib/data/tests/test_gitlab_issues_api.py
git commit -m "feat(fetcher): add GitLab issues API client"
```

---

## Task 7: Wire source branching into fetch_issue.py (full/comments/issue-lookup/related)

**Files:**
- Modify: `scripts/lib/data/fetch_issue.py`
- Test: `scripts/lib/data/tests/test_fetch_issue_gitlab.py`

Read `mode_full`, `mode_comments`, `mode_issue_lookup`, `mode_related`, `parse_args`, and the `main` dispatcher first. **Verified facts about the real code:** JSON is written with `write_json(path, data)` (NOT `_emit_json`, which is for stdout modes); `comments.json` is an envelope `{"issue_id","total_count","source","since","comments":[...]}`; the MR steps (3-8) are inline in `mode_full` and are fully source-agnostic; the log API is `log.track(label, fn)` / `log.error(key,msg)` / `log.finalize()` / `log.to_dict()` / `log.has_errors()`; `mode_full` returns `1 if log.has_errors() else 0`.

**Restructure (not duplicate):** factor `mode_full` so only issue+comments *acquisition* differs by source; the MR block (steps 3-8) stays shared. Add a `--source` arg (`auto|do|gitlab`, default `auto`) resolved at dispatch.

- [ ] **Step 1: Write a failing integration test for the GitLab branch of mode_full**

```python
# tests/test_fetch_issue_gitlab.py
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
    # the shared MR block calls GitLabAPI.search_merge_requests - stub it to no MRs
    monkeypatch.setattr(GitLabAPI, "search_merge_requests", lambda self, p, i: [])

    log = fetch_issue.FetchLog()
    rc = fetch_issue.mode_full(
        log, out_dir=tmp_path, project="project/canvas", issue_id="3542219",
        source="gitlab", gitlab_token_file=None)
    assert rc == 0

    issue_out = json.loads((tmp_path / "issue.json").read_text())
    assert issue_out["source"] == "gitlab" and issue_out["nid"] == 3542219
    comments_env = json.loads((tmp_path / "comments.json").read_text())
    assert comments_env["source"] == "gitlab"
    assert comments_env["comments"][0]["number"] == 1
```

(`out_dir` is a `Path` here because the real `mode_full` does `out_dir / "issue.json"`; pass `tmp_path` directly.)

- [ ] **Step 2: Run to verify fail**

Run: `cd scripts/lib/data && python3 -m pytest tests/test_fetch_issue_gitlab.py -v`
Expected: FAIL (`mode_full() got an unexpected keyword argument 'source'`).

- [ ] **Step 3: Implement the branch**

In `fetch_issue.py`:
1. Add imports at top: `from gitlab_issues_api import GitLabIssuesAPI` and `from gitlab_transform import transform_gitlab_issue, transform_gitlab_notes`.
2. Add `source="do"` parameter to `mode_full`, `mode_comments`, `mode_issue_lookup`, `mode_related`.
3. Replace steps 1-2 of `mode_full` (issue + comments acquisition, lines ~661-703) with a source switch that produces `issue`, `comments` (list), and `hidden_branches`; steps 3-8 (the MR block) stay exactly as they are:

```python
    if source == "gitlab":
        gi = (GitLabIssuesAPI.from_token_file(gitlab_token_file)
              if gitlab_token_file else GitLabIssuesAPI())
        raw_issue = log.track("gitlab.issue", lambda: gi.get_issue(project, issue_id))
        issue = transform_gitlab_issue(raw_issue, project=project)
        write_json(out_dir / "issue.json", issue)
        raw_notes = log.track("gitlab.notes", lambda: gi.get_issue_notes(project, issue_id))
        events = log.track("gitlab.label_events",
                           lambda: gi.get_resource_label_events(project, issue_id))
        comments = transform_gitlab_notes(raw_notes, events, since=since)
        comments_source = "gitlab"
        hidden_branches = set()
    else:
        api = DrupalOrgAPI(offline=False)
        raw = log.track("issue", lambda: api.get_issue(issue_id))
        issue = transform_issue(raw, project)
        write_json(out_dir / "issue.json", issue)
        comments, hidden_branches, comments_source = _fetch_comments(api, project, issue_id, log)
        if comments and issue["author"]["name"] is None:
            first_author = comments[0].get("author", {})
            if first_author.get("name"):
                issue["author"]["name"] = first_author["name"]
                write_json(out_dir / "issue.json", issue)
        if since:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            comments = [c for c in comments if c.get("created") and
                        datetime.fromisoformat(c["created"].replace("Z", "+00:00")) > since_dt]

    write_json(out_dir / "comments.json", {
        "issue_id": issue_id,
        "total_count": len(comments),
        "source": comments_source,
        "since": since,
        "comments": comments,
    })
    # ... steps 3-8 (MR search, enrich, primary, diffs, discussions, fetch-log) unchanged ...
```

(`project` for the GitLab MR search is `project/canvas`; the existing `GitLabAPI.search_merge_requests` already URL-encodes it, so pass the same `project` value through. The d.o branch passes the short project name as today.)

4. `mode_comments` GitLab branch: same source switch for issue+comments, write `issue.json` and the `comments.json` envelope; skip the MR block.
5. `mode_issue_lookup` GitLab branch: return `{"source":"gitlab","project":short,"iid":..,"title":..,"status":..}` from `get_issue` via `_emit_json` (this mode prints to stdout).
6. `mode_related` GitLab branch: parse `#NNN` / `project#NNN` refs out of the transformed `issue["body_html"]`; `write_json(out_dir / "related-issues.json", {...})` in the existing shape.
7. In `main`, after `parse_args`, resolve source when `args.source == "auto"` and the mode needs an issue:

```python
    from source_resolver import resolve, ResolveError
    if getattr(args, "source", "auto") == "auto" and args.issue and mode in NEEDS_ISSUE_MODES:
        try:
            r = resolve(args.issue)
            args.source = r["source"]
            args.project = r["project"] if r["source"] == "gitlab" else (args.project or r["project"])
            args.issue = r["iid"]
        except ResolveError as e:
            print(f"FAILED: {e}", file=sys.stderr)
            sys.exit(2)
```

Pass `source=args.source` through every `mode_*` call in the dispatcher.

- [ ] **Step 4: Run to verify pass**

Run: `cd scripts/lib/data && python3 -m pytest tests/test_fetch_issue_gitlab.py tests/ -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/data/fetch_issue.py scripts/lib/data/tests/test_fetch_issue_gitlab.py
git commit -m "feat(fetcher): branch fetch modes on issue source"
```

---

## Task 8: Dual-source search mode

**Files:**
- Modify: `scripts/lib/data/fetch_issue.py` (`mode_search`)
- Test: `scripts/lib/data/tests/test_search_dual.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_search_dual.py
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
```

- [ ] **Step 2: Run to verify fail**

Run: `cd scripts/lib/data && python3 -m pytest tests/test_search_dual.py -v`
Expected: FAIL (`module 'fetch_issue' has no attribute 'search_all'`).

- [ ] **Step 3: Implement `search_all` and route `mode_search` through it**

```python
# in fetch_issue.py
def search_all(project, keywords, gitlab_token_file=None):
    """Search both the d.o issue queue and GitLab issues; merge + dedupe by (source,id)."""
    results = []
    try:
        for r in _search_do(project, keywords):   # existing d.o search, normalized below
            r.setdefault("source", "do")
            results.append(r)
    except Exception as e:  # noqa: BLE001 - one source failing must not kill the other
        results.append({"source": "do", "error": str(e)})

    gi = GitLabIssuesAPI.from_token_file(gitlab_token_file) if gitlab_token_file else GitLabIssuesAPI()
    seen = set()
    for finder, scope in ((gi.search_project_issues, project), (gi.search_global_issues, None)):
        try:
            hits = finder(scope, keywords) if scope else finder(keywords)
        except Exception:  # noqa: BLE001
            hits = []
        for h in hits:
            key = ("gitlab", h.get("iid"))
            if key in seen:
                continue
            seen.add(key)
            results.append({"source": "gitlab", "id": str(h.get("iid")),
                            "title": h.get("title"), "url": h.get("web_url")})
    return results
```

If the current `mode_search` does the d.o query inline, extract it into `_search_do(project, keywords)` returning normalized dicts, then have `mode_search` emit `search_all(...)`.

- [ ] **Step 4: Run to verify pass**

Run: `cd scripts/lib/data && python3 -m pytest tests/test_search_dual.py tests/ -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/data/fetch_issue.py scripts/lib/data/tests/test_search_dual.py
git commit -m "feat(fetcher): dual-source issue search (d.o + GitLab)"
```

---

## Task 9: post-note mode (GitLab note posting)

**Files:**
- Modify: `scripts/lib/data/fetch_issue.py` (add `mode_post_note`, register in dispatcher + arg validation)
- Test: `scripts/lib/data/tests/test_post_note.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_post_note.py
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
```

- [ ] **Step 2: Run to verify fail**

Run: `cd scripts/lib/data && python3 -m pytest tests/test_post_note.py -v`
Expected: FAIL (`module 'fetch_issue' has no attribute 'mode_post_note'`).

- [ ] **Step 3: Implement the mode + register**

```python
# in fetch_issue.py
def mode_post_note(project, issue_id, body_file, gitlab_token_file=None):
    gi = GitLabIssuesAPI.from_token_file(gitlab_token_file) if gitlab_token_file else GitLabIssuesAPI()
    body = Path(body_file).read_text()
    return gi.post_issue_note(project, issue_id, body)
```

Register `post-note` in `parse_args` (add `--body-file`), in the dispatcher, and in arg validation (`needs_project`, `needs_issue`, requires `--body-file` and a GitLab source). On `GitLabIssuesError` for a missing/read-only token, print `PARTIAL: token lacks write scope; post the note manually at {url}` to stderr and exit 1 (do not crash).

- [ ] **Step 4: Run to verify pass**

Run: `cd scripts/lib/data && python3 -m pytest tests/test_post_note.py tests/ -v`
Expected: PASS (full suite green).

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/data/fetch_issue.py scripts/lib/data/tests/test_post_note.py
git commit -m "feat(fetcher): add GitLab post-note mode"
```

---

## Task 10: drupal-issue.sh entry resolution

**Files:**
- Modify: `drupal-issue.sh`
- Test: manual CLI assertion (bash)

- [ ] **Step 1: Read current arg handling**

`drupal-issue.sh` currently takes `<issue_id_or_url>` and passes it down. It must resolve the identifier once and pass `--source` + resolved project/iid to downstream fetch calls, and key `DRUPAL_ISSUES/{iid}` on the resolved iid.

- [ ] **Step 2: Add resolution shim**

```bash
# near the top, after parsing positional issue arg into $ISSUE_ARG:
RESOLVED_JSON="$(python3 scripts/lib/data/source_resolver_cli.py "$ISSUE_ARG" 2>/dev/null)" || {
  echo "Could not resolve issue '$ISSUE_ARG'. For a GitLab-native issue pass a full" >&2
  echo "work_items URL or project#iid shorthand." >&2
  exit 1
}
ISSUE_SOURCE="$(printf '%s' "$RESOLVED_JSON" | python3 -c 'import sys,json;print(json.load(sys.stdin)["source"])')"
ISSUE_PROJECT="$(printf '%s' "$RESOLVED_JSON" | python3 -c 'import sys,json;print(json.load(sys.stdin)["project"])')"
ISSUE_IID="$(printf '%s' "$RESOLVED_JSON" | python3 -c 'import sys,json;print(json.load(sys.stdin)["iid"])')"
```

- [ ] **Step 3: Add the tiny CLI wrapper**

```python
# scripts/lib/data/source_resolver_cli.py
import json, sys
from source_resolver import resolve, ResolveError
try:
    print(json.dumps(resolve(sys.argv[1])))
except (ResolveError, IndexError) as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)
```

- [ ] **Step 4: Manual verify on g5 (live)**

```bash
ssh alphons@alphons-g55500 'cd /mnt/data/drupal/CONTRIB_WORKBENCH && python3 scripts/lib/data/source_resolver_cli.py 3542219'
```

Expected: `{"source": "gitlab", "project": "project/canvas", "iid": "3542219", "url": "...work_items/3542219"}`

- [ ] **Step 5: Commit**

```bash
git add drupal-issue.sh scripts/lib/data/source_resolver_cli.py
git commit -m "feat: resolve issue source at drupal-issue.sh entry"
```

---

## Task 11: Skill updates (source awareness + comment gate)

**Files:**
- Modify: `.claude/skills/drupal-issue/SKILL.md`
- Modify: `.claude/skills/drupal-issue-review/SKILL.md`
- Modify: `.claude/skills/drupal-issue-comment/SKILL.md`
- Modify: `.claude/skills/drupal-contribute-fix/SKILL.md`

- [ ] **Step 1: drupal-issue + review** - add a short "Source awareness" section: read `source` from `issue.json`; for `gitlab`, issue metadata comes from scoped labels (already normalized into the same fields), the issue thread is `comments.json` (GitLab Notes), and the issue lives at the `url` field. No behavior change beyond reading `source`.

- [ ] **Step 2: drupal-issue-comment** - add a branch: when `source == "gitlab"`, format the draft as **GitLab-flavored markdown** (not d.o HTML); references use `#iid` / `project#iid` / `!mr`. After presenting the draft, **ask the user "post this note to the issue now?"**. On yes, run:

```bash
./scripts/fetch-issue --mode post-note --issue {iid} --project project/{project} \
  --body-file {draft_path} --gitlab-token-file git.drupalcode.org.key
```

On a `PARTIAL` (read-only token) result, tell the user to paste it manually at the issue `url`.

- [ ] **Step 3: drupal-contribute-fix** - note that for `gitlab` issues the MR/fork flow is unchanged (it was always GitLab), and the issue-thread re-fetch uses `--mode comments` which now auto-detects source. No push-gate change.

- [ ] **Step 4: Verify skill files still parse** (frontmatter intact, line counts sane)

Run: `head -5 .claude/skills/drupal-issue-comment/SKILL.md`
Expected: valid `---` frontmatter with `name:`/`description:`.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/drupal-issue/SKILL.md .claude/skills/drupal-issue-review/SKILL.md .claude/skills/drupal-issue-comment/SKILL.md .claude/skills/drupal-contribute-fix/SKILL.md
git commit -m "docs(skills): teach skills GitLab-issue source awareness"
```

---

## Task 12: Docs + agent contract + CLAUDE.md

**Files:**
- Modify: `docs/fetcher-modes-reference.md`
- Modify: `docs/workflow-state-files.md`
- Modify: `.claude/agents/drupal-issue-fetcher.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: fetcher-modes-reference.md** - add `--source auto|do|gitlab` to every mode row, document the new `post-note` mode (required flags: `--issue`, `--project`, `--body-file`, `--gitlab-token-file`), and note that `search` is now dual-source.

- [ ] **Step 2: workflow-state-files.md** - document that `issue.json` now carries `source` (`do|gitlab`) and `iid` (alias of `nid`); `DRUPAL_ISSUES/{id}` is keyed on the resolved iid.

- [ ] **Step 3: drupal-issue-fetcher.md** - add a "Source resolution" paragraph (redirect probe, three identifier forms) and the `post-note` mode to the dispatch contract.

- [ ] **Step 4: CLAUDE.md** - under "Drupal.org Contribution Workflow", add a "Dual issue sources" note: the workbench auto-detects whether an issue is on the legacy d.o queue or migrated to GitLab work-items, handles both, and accepts bare numbers (migrated/legacy), full work_items URLs, and `project#iid` for new GitLab-native issues.

- [ ] **Step 5: Commit**

```bash
git add docs/fetcher-modes-reference.md docs/workflow-state-files.md .claude/agents/drupal-issue-fetcher.md CLAUDE.md
git commit -m "docs: document dual-source GitLab-issue support"
```

---

## Task 13: End-to-end smoke on g5 (live, both sources)

**Files:** none (runtime verification on g5).

- [ ] **Step 1: Sync g5 to the branch**

```bash
ssh alphons@alphons-g55500 'cd /mnt/data/drupal/CONTRIB_WORKBENCH && git fetch origin && git checkout gitlab-issues-dual-source && git pull --ff-only'
```

- [ ] **Step 2: GitLab issue path (canvas/3542219)**

```bash
ssh alphons@alphons-g55500 'cd /mnt/data/drupal/CONTRIB_WORKBENCH && ./scripts/fetch-issue --mode full --issue 3542219 --out /tmp/smoke-gl --gitlab-token-file git.drupalcode.org.key && python3 -c "import json;d=json.load(open(\"/tmp/smoke-gl/issue.json\"));print(d[\"source\"],d[\"nid\"],d[\"status\"][\"label\"],d[\"version\"]); print(\"comments:\", len(json.load(open(\"/tmp/smoke-gl/comments.json\"))))"'
```

Expected: `gitlab 3542219 Needs work 1.x-dev` and a nonzero comment count.

- [ ] **Step 3: d.o queue path (a known not-yet-migrated issue)**

Pick a still-on-d.o issue number `$DO` (one whose `drupal.org/i/{n}` does NOT redirect to git.drupalcode.org), then:

```bash
ssh alphons@alphons-g55500 'cd /mnt/data/drupal/CONTRIB_WORKBENCH && ./scripts/fetch-issue --mode full --issue '$DO' --project <proj> --out /tmp/smoke-do && python3 -c "import json;d=json.load(open(\"/tmp/smoke-do/issue.json\"));print(d.get(\"source\"),d[\"nid\"])"'
```

Expected: `do <DO>` - proves the legacy path still works unchanged.

- [ ] **Step 4: Full unit suite green on laptop**

Run: `cd scripts/lib/data && python3 -m pytest tests/ -v`
Expected: all tests PASS.

- [ ] **Step 5: Final commit + push**

```bash
git add -A && git commit -m "test: end-to-end dual-source smoke notes" --allow-empty
git push -u origin gitlab-issues-dual-source
```

---

## Self-review notes

- **Spec coverage:** resolver+3 forms (T1,T2,T10); GitLab client (T6); label map (T3); transforms+unified schema (T5); mode branching (T7); dual search (T8); post-note with ask-to-post (T9,T11); skills source-awareness (T11); docs (T12); both-path smoke (T13). All spec sections covered.
- **Type consistency:** `resolve()` returns `{source, project, iid, url}` everywhere; `transform_gitlab_issue` emits `source/iid/nid/status/priority/category/version/...`; `GitLabIssuesAPI` method names (`get_issue`, `get_issue_notes`, `get_resource_label_events`, `search_project_issues`, `search_global_issues`, `post_issue_note`) are used identically across tasks.
- **Open verification during execution:** confirm `transform_issue()` (d.o) output keys match the asserts in T5; if the d.o path uses different key names, align both to one schema and update tests. Confirm the existing MR-fetch code in `mode_full` is extracted to a shared helper so both branches reuse it.
</content>
</invoke>
