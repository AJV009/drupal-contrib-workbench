"""Map GitLab scoped labels to the workbench's drupal.org issue model.

GitLab-sourced issues (migrated from drupal.org) carry scoped labels such as
``state::needsWork``, ``category::task`` and ``priority::normal`` plus version
labels like ``v1.x-dev``. This module normalizes those labels into the same
``{code, label}`` shape the rest of the workbench uses for d.o-sourced issues,
reusing the exact codes and label strings from ``drupalorg_api.py`` so both
sources produce identical output.

It also parses the ``Reported by:`` marker that migrated issue descriptions use
to preserve the original drupal.org reporter.
"""

import re

from drupalorg_api import ISSUE_STATUS, ISSUE_PRIORITY


def _slug(value):
    """Normalize a label value to a lookup slug (lowercase, alphanumerics only)."""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _build(table):
    """Invert an {code: label} dict into {slug: (code, label)}."""
    return {_slug(label): (code, label) for code, label in table.items()}


# Status slugs derived from ISSUE_STATUS, plus convenience aliases.
STATUS_BY_SLUG = _build(ISSUE_STATUS)
STATUS_BY_SLUG["needswork"] = (13, ISSUE_STATUS[13])
STATUS_BY_SLUG["needsreview"] = (8, ISSUE_STATUS[8])
STATUS_BY_SLUG["rtbc"] = (14, ISSUE_STATUS[14])
STATUS_BY_SLUG["active"] = (1, ISSUE_STATUS[1])
STATUS_BY_SLUG["fixed"] = (2, ISSUE_STATUS[2])
STATUS_BY_SLUG["postponed"] = (4, ISSUE_STATUS[4])
STATUS_BY_SLUG["todo"] = (1, ISSUE_STATUS[1])

PRIORITY_BY_SLUG = _build(ISSUE_PRIORITY)

# drupal.org issue categories. No ISSUE_CATEGORY dict exists in drupalorg_api.py,
# so these use the standard d.o category codes and labels.
ISSUE_CATEGORY = {
    1: "Bug report",
    2: "Task",
    3: "Feature request",
    4: "Support request",
    5: "Plan",
}
CATEGORY_BY_SLUG = {
    "bug": (1, "Bug report"),
    "bugreport": (1, "Bug report"),
    "task": (2, "Task"),
    "feature": (3, "Feature request"),
    "featurerequest": (3, "Feature request"),
    "support": (4, "Support request"),
    "supportrequest": (4, "Support request"),
    "plan": (5, "Plan"),
}

_VERSION_RE = re.compile(r"^v?(\d+\.[0-9x]+(?:-[A-Za-z0-9.]+)?)$")
_REPORTED_BY_RE = re.compile(
    r"Reported by:\s*\[([^\]]+)\]\(https://www\.drupal\.org/user/(\d+)\)"
)


def _lookup(table, raw_value):
    """Look up a raw scoped-label value, preserving the raw string on a miss."""
    hit = table.get(_slug(raw_value))
    if hit is None:
        return {"code": None, "label": raw_value}
    code, label = hit
    return {"code": code, "label": label}


def classify_labels(labels):
    """Classify GitLab labels into status/priority/category/version/tags."""
    out = {
        "status": {"code": None, "label": None},
        "priority": {"code": None, "label": None},
        "category": {"code": None, "label": None},
        "version": None,
        "tags": [],
    }
    for label in labels:
        if "::" in label:
            scope, value = label.split("::", 1)
            if scope == "state":
                out["status"] = _lookup(STATUS_BY_SLUG, value)
            elif scope == "priority":
                out["priority"] = _lookup(PRIORITY_BY_SLUG, value)
            elif scope == "category":
                out["category"] = _lookup(CATEGORY_BY_SLUG, value)
            else:
                out["tags"].append(label)
        else:
            m = _VERSION_RE.match(label)
            if m and out["version"] is None:
                out["version"] = m.group(1)
            else:
                out["tags"].append(label)
    return out


def parse_reported_by(description):
    """Parse the migrated-issue ``Reported by:`` marker, or return None."""
    m = _REPORTED_BY_RE.search(description)
    if m is None:
        return None
    return {"name": m.group(1), "uid": int(m.group(2))}
