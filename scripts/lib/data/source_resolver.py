"""Resolve a drupal.org issue identifier to its source (legacy d.o queue or GitLab work-item)."""

import re

GITLAB_HOST = "git.drupalcode.org"


class ResolveError(Exception):
    """Raised when an identifier cannot be parsed or resolved."""


def _gitlab_url(project, iid):
    return f"https://{GITLAB_HOST}/{project}/-/work_items/{iid}"


_RE_GITLAB = re.compile(r"https?://git\.drupalcode\.org/(project/[^/]+)/-/work_items/(\d+)")
_RE_HASH = re.compile(r"^([A-Za-z0-9_]+)#(\d+)$")
_RE_DO_PROJECT = re.compile(r"https?://www\.drupal\.org/project/([^/]+)/issues/(\d+)")
_RE_DO_SHORT = re.compile(r"https?://www\.drupal\.org/i/(\d+)")
_RE_BARE = re.compile(r"^\d+$")


def parse_identifier(identifier):
    s = identifier.strip()
    if not s:
        raise ResolveError("empty issue identifier")

    m = _RE_GITLAB.match(s)
    if m:
        project, iid = m.group(1), m.group(2)
        return {"source": "gitlab", "project": project, "iid": iid,
                "url": _gitlab_url(project, iid)}

    m = _RE_HASH.match(s)
    if m:
        project, iid = f"project/{m.group(1)}", m.group(2)
        return {"source": "gitlab", "project": project, "iid": iid,
                "url": _gitlab_url(project, iid)}

    m = _RE_DO_PROJECT.match(s)
    if m:
        return {"needs_probe": True, "iid": m.group(2), "project_hint": m.group(1)}

    m = _RE_DO_SHORT.match(s)
    if m:
        return {"needs_probe": True, "iid": m.group(1), "project_hint": None}

    if _RE_BARE.match(s):
        return {"needs_probe": True, "iid": s, "project_hint": None}

    raise ResolveError(f"unrecognized issue identifier: {identifier!r}")
