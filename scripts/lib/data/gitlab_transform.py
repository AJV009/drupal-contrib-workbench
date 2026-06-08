"""Transform GitLab issue, notes, and label events into the workbench schema.

GitLab-sourced issues (migrated from drupal.org and served via GitLab work
items) must produce the SAME unified ``issue.json`` / per-comment structure as
the d.o API path in ``fetch_issue.py``. This module reshapes the raw GitLab
payloads into that schema, adding a few GitLab-specific extras (``source``,
``iid``, per-comment ``field_changes`` and ``images``) as supersets.

``transform_gitlab_notes`` returns a BARE LIST of comment dicts; the
``{issue_id, total_count, ..., comments: [...]}`` envelope is assembled later by
``mode_full``.
"""

import re

from gitlab_label_map import classify_labels, parse_reported_by

_MR_REF_RE = re.compile(
    r"(?:!(\d+)|https://git\.drupalcode\.org/\S+/merge_requests/\d+)"
)
_IMG_RE = re.compile(r'!\[[^\]]*\]\((\S+?)\)|<img[^>]+src="([^"]+)"')


def _project_short(project):
    """Return the part after the final ``/`` if present, else the project."""
    return project.split("/")[-1] if "/" in project else project


def transform_gitlab_issue(raw, project):
    """Transform a raw GitLab issue dict into the unified issue schema."""
    classified = classify_labels(raw.get("labels", []))
    reporter = parse_reported_by(raw.get("description", "") or "")

    if reporter:
        author = {"name": reporter["name"], "uid": reporter["uid"]}
    else:
        gl_author = raw.get("author") or {}
        author = {
            "name": gl_author.get("name") or gl_author.get("username"),
            "uid": None,
        }

    assignees = raw.get("assignees") or []
    if assignees:
        first = assignees[0]
        assigned = {"name": first.get("username"), "uid": first.get("id")}
    else:
        assigned = None

    iid = raw["iid"]
    return {
        "source": "gitlab",
        "iid": iid,
        "nid": iid,
        "title": raw.get("title", ""),
        "url": f"https://git.drupalcode.org/{project}/-/work_items/{iid}",
        "project": _project_short(project),
        "status": classified["status"],
        "priority": classified["priority"],
        "category": classified["category"],
        "component": "",
        "version": classified["version"],
        "author": author,
        "assigned": assigned,
        "created": raw["created_at"],
        "changed": raw["updated_at"],
        "comment_count": raw.get("user_notes_count", 0),
        "body_html": raw.get("description", "") or "",
        "related_issues": [],
        "parent_issue": None,
        "tags": classified["tags"],
        "files": [],
    }


def _event_change(ev):
    """Convert a single label event into a field_changes entry, or None."""
    label = (ev.get("label") or {}).get("name", "")
    field = label.split("::")[0] if "::" in label else "label"
    action = ev.get("action")
    if action == "add":
        return {"field": field, "old": "", "new": label}
    if action == "remove":
        return {"field": field, "old": label, "new": ""}
    return None


def _label_events_to_changes(events, note_created):
    """Derive field_changes from label events sharing a note's timestamp."""
    changes = []
    for ev in events:
        if ev.get("created_at") != note_created:
            continue
        change = _event_change(ev)
        if change:
            changes.append(change)
    return changes


def _extract_mr_refs(body, project=None):
    """Return a sorted, unique list of MR reference strings in the body.

    Bare ``!NNN`` references resolve to full MR URLs when ``project`` is given,
    matching the d.o path which always yields full URLs.
    """
    refs = set()
    for m in _MR_REF_RE.finditer(body or ""):
        bang = m.group(1)
        if bang is not None and project:
            refs.add(
                f"https://git.drupalcode.org/{project}/-/merge_requests/{bang}"
            )
        else:
            refs.add(m.group(0))
    return sorted(refs)


def _extract_images(body):
    """Return image URLs referenced in markdown or img tags within the body."""
    out = []
    for m in _IMG_RE.finditer(body or ""):
        url = m.group(1) or m.group(2)
        if url:
            out.append(url)
    return out


def transform_gitlab_notes(raw_notes, label_events, since=None, project=None):
    """Transform GitLab notes + label events into a bare list of comment dicts.

    ``field_changes`` is populated only when a label event's ``created_at``
    exactly matches a note's ``created_at`` (what GitLab emits for live UI label
    changes). No fuzzy attachment is performed.
    """
    ordered = sorted(raw_notes, key=lambda n: n.get("created_at") or "")
    notes = []
    number = 0
    for note in ordered:
        created = note.get("created_at")
        if since is not None and not (created and created > since):
            continue
        number += 1
        author = note.get("author") or {}
        body = note.get("body", "")
        notes.append({
            "number": number,
            "cid": str(note.get("id", "")),
            "author": {
                "uid": author.get("id"),
                "name": author.get("name") or author.get("username"),
            },
            "created": created,
            "body_html": body,
            "is_system_message": bool(note.get("system")),
            "mr_references": _extract_mr_refs(body, project),
            "field_changes": _label_events_to_changes(label_events, created),
            "images": _extract_images(body),
        })

    return notes
