"""Resolve a drupal.org issue identifier to its source (legacy d.o queue or GitLab work-item)."""

import re
import urllib.request

GITLAB_HOST = "git.drupalcode.org"

_DEFAULT_UA = "drupal-contrib-workbench-source-resolver/1.0"


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


def _default_opener(url):
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": _DEFAULT_UA})
    return urllib.request.urlopen(req, timeout=20)


def resolve(identifier, opener=None):
    parsed = parse_identifier(identifier)
    if not parsed.get("needs_probe"):
        return parsed

    iid = parsed["iid"]
    project_hint = parsed.get("project_hint")
    if project_hint:
        probe_url = f"https://www.drupal.org/project/{project_hint}/issues/{iid}"
    else:
        probe_url = f"https://www.drupal.org/i/{iid}"

    try:
        with (opener or _default_opener)(probe_url) as resp:
            final = resp.geturl()
    except Exception as e:
        raise ResolveError(f"redirect probe failed for {probe_url}: {e}")

    m = _RE_GITLAB.match(final)
    if m:
        project, fiid = m.group(1), m.group(2)
        return {"source": "gitlab", "project": project, "iid": fiid, "url": final}

    m = _RE_DO_PROJECT.match(final)
    if m:
        return {"source": "do", "project": m.group(1), "iid": m.group(2), "url": final}

    raise ResolveError(
        f"could not resolve {identifier!r} (final url: {final}). "
        f"For a GitLab-native issue pass a full work_items URL or `project#iid`."
    )
