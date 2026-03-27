#!/usr/bin/env python3
"""
Fetch all data for a drupal.org issue and write structured artifacts.

Orchestrates the drupal.org and GitLab APIs to produce:
  - issue.json        (issue metadata)
  - comments.json     (all comments with system message detection)
  - merge-requests.json (MRs with primary selection heuristic)
  - mr-{iid}-diff.patch (plain diffs for open/merged MRs)
  - mr-{iid}-notes.json (GitLab notes if token available)
  - fetch-log.json    (request tracking)
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

# Add the lib directory to sys.path so we can import our API modules
SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from drupalorg_api import DrupalOrgAPI, get_status_label, get_priority_label
from gitlab_api import GitLabAPI


# Category code mapping
ISSUE_CATEGORY = {
    1: "Bug report",
    2: "Task",
    3: "Feature request",
    4: "Support request",
}


class LinkExtractor(HTMLParser):
    """Extract href values from <a> tags in HTML."""

    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for name, value in attrs:
                if name == 'href' and value:
                    self.links.append(value)


def extract_links_from_html(html_text):
    """Extract all href links from an HTML string."""
    if not html_text:
        return []
    parser = LinkExtractor()
    try:
        parser.feed(html_text)
    except Exception:
        pass
    return parser.links


def extract_mr_references(html_text):
    """Extract GitLab MR URLs from HTML comment body."""
    links = extract_links_from_html(html_text)
    mr_pattern = re.compile(
        r'https?://git\.drupalcode\.org/project/[^/]+/-/merge_requests/(\d+)'
    )
    refs = []
    seen = set()
    for link in links:
        m = mr_pattern.search(link)
        if m and link not in seen:
            seen.add(link)
            refs.append(link)
    return refs


def is_system_message(comment):
    """Detect if a comment is a system/automated message."""
    author_name = comment.get("name", "")
    if "System Message" in author_name:
        return True

    body = safe_body(comment.get("comment_body"))
    system_patterns = [
        "opened merge request",
        "made their first commit",
        "changed the visibility",
        re.compile(r"committed [a-f0-9]+ on "),
    ]
    for pattern in system_patterns:
        if isinstance(pattern, str):
            if pattern in body:
                return True
        elif pattern.search(body):
            return True
    return False


def safe_body(comment_body_field):
    """
    Safely extract HTML body text from a comment_body field.

    The d.o API returns comment_body as a dict {"value": "...", "format": "..."}
    for comments with content, but as an empty list [] for empty comments.
    """
    if isinstance(comment_body_field, dict):
        return comment_body_field.get("value", "")
    return ""


def extract_hidden_branches(comments):
    """Scan comments for branch visibility changes to find hidden branches."""
    hidden = set()
    pattern = re.compile(
        r"changed the visibility of the branch\s+(\S+)\s+to hidden"
    )
    for c in comments:
        body = safe_body(c.get("comment_body"))
        if body:
            for match in pattern.finditer(body):
                hidden.add(match.group(1))
    return hidden


def unix_to_iso(ts):
    """Convert a unix timestamp (string or int) to ISO 8601 string."""
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (ValueError, TypeError, OSError):
        return str(ts)


def parse_issue_url(issue_arg):
    """
    Parse an issue URL or number to extract project and issue ID.

    Accepts:
      - https://www.drupal.org/project/ai/issues/3575190
      - https://www.drupal.org/project/ai/issues/3575190#comment-16521307
      - 3575190

    Returns:
        Tuple of (project_name_or_None, issue_id_int)
    """
    issue_arg = issue_arg.strip()

    # Try URL pattern
    url_pattern = re.compile(
        r'https?://(?:www\.)?drupal\.org/project/([^/]+)/issues/(\d+)'
    )
    m = url_pattern.search(issue_arg)
    if m:
        return m.group(1), int(m.group(2))

    # Try plain number
    if issue_arg.isdigit():
        return None, int(issue_arg)

    # Could be just a number with a hash fragment stripped
    num_match = re.match(r'^(\d+)', issue_arg)
    if num_match:
        return None, int(num_match.group(1))

    print(f"ERROR: Cannot parse issue identifier: {issue_arg}", file=sys.stderr)
    sys.exit(2)


def transform_issue(raw, project):
    """Transform raw drupal.org API issue data into structured artifact format."""
    nid = int(raw.get("nid", 0))

    status_code = raw.get("field_issue_status")
    priority_code = raw.get("field_issue_priority")
    category_code = raw.get("field_issue_category")

    # Author: d.o API returns {"uri": "...", "id": "...", "resource": "user"}
    author_ref = raw.get("author", {})
    author_uid = author_ref.get("id") if isinstance(author_ref, dict) else None
    # Author name is not in the issue node; store UID only
    author = {"uid": int(author_uid) if author_uid else None, "name": None}

    # Assigned
    assigned_ref = raw.get("field_issue_assigned", {})
    if isinstance(assigned_ref, dict) and assigned_ref.get("id"):
        assigned = {
            "uid": int(assigned_ref["id"]),
            "name": None,
        }
    else:
        assigned = None

    # Body
    body_raw = raw.get("body", {})
    body_html = body_raw.get("value", "") if isinstance(body_raw, dict) else ""

    # Files
    files_raw = raw.get("field_issue_files", [])
    files = files_raw if isinstance(files_raw, list) else []

    # Related issues
    related_raw = raw.get("field_issue_related", [])
    related_issues = related_raw if isinstance(related_raw, list) else []

    # Parent issue
    parent_raw = raw.get("field_issue_parent", None)
    parent_issue = parent_raw if parent_raw else None

    # Tags (taxonomy_vocabulary_9)
    tags_raw = raw.get("taxonomy_vocabulary_9", [])
    tags = tags_raw if isinstance(tags_raw, list) else []

    # Comment count
    comment_count_raw = raw.get("comment_count", 0)
    try:
        comment_count = int(comment_count_raw)
    except (ValueError, TypeError):
        comment_count = 0

    # Safely convert category code to int
    try:
        cat_code = int(category_code) if category_code is not None else None
    except (ValueError, TypeError):
        cat_code = None

    return {
        "nid": nid,
        "title": raw.get("title", ""),
        "url": f"https://www.drupal.org/project/{project}/issues/{nid}",
        "project": project,
        "status": {
            "code": status_code,
            "label": get_status_label(status_code),
        },
        "priority": {
            "code": priority_code,
            "label": get_priority_label(priority_code),
        },
        "category": {
            "code": cat_code,
            "label": ISSUE_CATEGORY.get(cat_code, f"Unknown ({cat_code})") if cat_code else "Unknown",
        },
        "component": raw.get("field_issue_component", ""),
        "version": raw.get("field_issue_version", ""),
        "author": author,
        "assigned": assigned,
        "created": unix_to_iso(raw.get("created")),
        "changed": unix_to_iso(raw.get("changed")),
        "comment_count": comment_count,
        "body_html": body_html,
        "related_issues": related_issues,
        "parent_issue": parent_issue,
        "tags": tags,
        "files": files,
    }


def process_comments(raw_comments):
    """
    Process raw comments into structured format and extract hidden branches.

    Returns:
        Tuple of (processed_comments_list, hidden_branches_set)
    """
    hidden_branches = extract_hidden_branches(raw_comments)
    processed = []

    for idx, c in enumerate(raw_comments):
        cid = c.get("cid", "")
        body_html = safe_body(c.get("comment_body"))

        # Author info from comment
        # Name is a top-level field; UID is in author.id (reference object)
        author_name = c.get("name", "")
        author_ref = c.get("author", {})
        author_uid_raw = author_ref.get("id") if isinstance(author_ref, dict) else None
        try:
            author_uid = int(author_uid_raw) if author_uid_raw else None
        except (ValueError, TypeError):
            author_uid = None

        # MR references in comment body
        mr_refs = extract_mr_references(body_html)

        processed.append({
            "number": idx + 1,
            "cid": str(cid),
            "author": {
                "uid": author_uid,
                "name": author_name if author_name else None,
            },
            "created": unix_to_iso(c.get("created")),
            "body_html": body_html,
            "is_system_message": is_system_message(c),
            "mr_references": mr_refs,
        })

    return processed, hidden_branches


def transform_mr(detail):
    """Transform a GitLab MR detail dict, adding computed heuristic fields."""
    return {
        "iid": detail.get("iid"),
        "title": detail.get("title", ""),
        "state": detail.get("state", ""),
        "source_branch": detail.get("source_branch", ""),
        "target_branch": detail.get("target_branch", ""),
        "web_url": detail.get("web_url", ""),
        "created_at": detail.get("created_at", ""),
        "updated_at": detail.get("updated_at", ""),
        "merged_at": detail.get("merged_at"),
        "author": {
            "username": detail.get("author", {}).get("username", ""),
            "name": detail.get("author", {}).get("name", ""),
        },
        "user_notes_count": detail.get("user_notes_count", 0),
        "has_conflicts": detail.get("has_conflicts", False),
        "merge_status": detail.get("merge_status", ""),
        "draft": detail.get("draft", False),
        "labels": detail.get("labels", []),
        "heuristics": {},
        "is_primary": False,
    }


def determine_primary_mr(mrs, issue_version, hidden_branches):
    """
    Select the primary MR using a heuristic priority system.

    Priority order:
      1. Filter out closed MRs (unless all are closed/merged)
      2. version_match: issue version (strip -dev) matches target_branch
      3. is_most_recent: highest updated_at
      4. has_activity: user_notes_count > 0
      5. branch_visible: source branch not hidden

    Returns:
        Tuple of (primary_iid_or_None, reason_string)
    """
    if not mrs:
        return None, "no merge requests found"

    # Strip -dev from issue version for matching
    version_base = issue_version.replace("-dev", "").strip() if issue_version else ""

    # Compute heuristics for each MR
    for mr in mrs:
        target = mr.get("target_branch", "")
        mr["heuristics"] = {
            "version_match": (version_base != "" and version_base == target),
            "is_most_recent": False,  # computed below
            "has_activity": (mr.get("user_notes_count", 0) or 0) > 0,
            "branch_visible": mr.get("source_branch", "") not in hidden_branches,
        }

    # Mark most recent
    if mrs:
        sorted_by_updated = sorted(
            mrs,
            key=lambda m: m.get("updated_at", ""),
            reverse=True,
        )
        sorted_by_updated[0]["heuristics"]["is_most_recent"] = True

    # Filter candidates: prefer non-closed
    non_closed = [m for m in mrs if m.get("state") != "closed"]
    candidates = non_closed if non_closed else mrs

    # Score each candidate
    def score(mr):
        h = mr.get("heuristics", {})
        return (
            1 if h.get("version_match") else 0,
            1 if h.get("is_most_recent") else 0,
            1 if h.get("has_activity") else 0,
            1 if h.get("branch_visible") else 0,
        )

    best = max(candidates, key=score)
    best_h = best.get("heuristics", {})

    # Build reason
    reasons = []
    if best_h.get("version_match"):
        reasons.append(f"target_branch matches issue version ({version_base})")
    if best_h.get("is_most_recent"):
        reasons.append("most recently updated")
    if best_h.get("has_activity"):
        reasons.append("has review activity")
    if best_h.get("branch_visible"):
        reasons.append("branch is visible")
    if not reasons:
        reasons.append("only candidate")

    state_note = ""
    if not non_closed:
        state_note = " (all MRs are closed/merged, selected best from those)"

    reason = "; ".join(reasons) + state_note
    return best.get("iid"), reason


class FetchLog:
    """Track API calls, timing, and errors during a fetch session."""

    def __init__(self):
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.requests = []
        self.errors = []
        self.completed_at = None

    def track(self, label, fn):
        """
        Execute fn(), tracking duration and success/failure.

        Args:
            label: Human-readable label for this request.
            fn: Callable that performs the API request.

        Returns:
            Result of fn().

        Raises:
            Re-raises any exception from fn() after recording it.
        """
        start = time.time()
        try:
            result = fn()
            duration = int((time.time() - start) * 1000)
            self.requests.append({
                "label": label,
                "duration_ms": duration,
                "status": "ok",
            })
            return result
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            self.requests.append({
                "label": label,
                "duration_ms": duration,
                "status": "error",
                "error": str(e),
            })
            raise

    def error(self, artifact, message):
        """Record an error that did not abort the whole fetch."""
        self.errors.append({"artifact": artifact, "message": message})

    def finalize(self):
        """Mark the fetch session as complete."""
        self.completed_at = datetime.now(timezone.utc).isoformat()

    def has_errors(self):
        return len(self.errors) > 0

    def error_count(self):
        return len(self.errors)

    def request_count(self):
        return len(self.requests)

    def to_dict(self):
        return {
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_requests": len(self.requests),
            "requests": self.requests,
            "errors": self.errors,
        }


def write_json(path, data):
    """Write data to a JSON file with pretty printing."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fetch all data for a drupal.org issue and write structured artifacts."
    )
    parser.add_argument(
        "--issue",
        required=True,
        help="Drupal.org issue URL or node ID (e.g. https://www.drupal.org/project/ai/issues/3575190 or 3575190)",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Project machine name (required if --issue is just a number)",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output directory for artifacts",
    )
    parser.add_argument(
        "--gitlab-token-file",
        default=None,
        help="Path to file containing GitLab private access token",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    project, issue_id = parse_issue_url(args.issue)
    project = project or args.project

    if not project:
        print(
            "ERROR: Could not determine project from URL. Use --project.",
            file=sys.stderr,
        )
        sys.exit(2)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    log = FetchLog()

    # 1. Fetch issue metadata
    api = DrupalOrgAPI()
    raw = log.track("issue", lambda: api.get_issue(issue_id))
    issue = transform_issue(raw, project)
    write_json(out_dir / "issue.json", issue)

    # 2. Fetch all comments
    raw_comments = log.track("comments", lambda: api.get_all_comments(issue_id))
    comments, hidden_branches = process_comments(raw_comments)

    # Backfill issue author name from first comment if available
    if comments and issue["author"]["name"] is None:
        first_author = comments[0].get("author", {})
        if first_author.get("name"):
            issue["author"]["name"] = first_author["name"]
            # Re-write issue.json with author name
            write_json(out_dir / "issue.json", issue)

    write_json(out_dir / "comments.json", {
        "issue_id": issue_id,
        "total_count": len(comments),
        "pages_fetched": max(1, (len(comments) + 43) // 44),
        "comments": comments,
    })

    # 3. Search for GitLab MRs
    if args.gitlab_token_file:
        gl = GitLabAPI.from_token_file(args.gitlab_token_file)
    else:
        gl = GitLabAPI()

    try:
        raw_mrs = log.track(
            "mr_search",
            lambda: gl.search_merge_requests(project, issue_id),
        )
    except Exception as e:
        log.error("merge-requests.json", f"MR search failed: {e}")
        raw_mrs = []

    # 4. Enrich each MR with full details
    mrs = []
    for raw_mr in raw_mrs:
        iid = raw_mr.get("iid")
        if iid is None:
            continue
        try:
            detail = log.track(
                f"mr_{iid}",
                lambda r=raw_mr: gl.get_merge_request(project, r["iid"]),
            )
            mrs.append(transform_mr(detail))
        except Exception as e:
            log.error(f"mr_{iid}", str(e))

    # 5. Determine primary MR
    primary_iid, reason = determine_primary_mr(
        mrs, issue.get("version", ""), hidden_branches
    )
    for mr in mrs:
        mr["is_primary"] = (mr.get("iid") == primary_iid)

    write_json(out_dir / "merge-requests.json", {
        "issue_id": issue_id,
        "project": project,
        "merge_requests": mrs,
        "primary_selection_reason": reason,
    })

    # 6. Fetch diffs for open/merged MRs
    for mr in mrs:
        if mr.get("state") in ("opened", "merged"):
            iid = mr["iid"]
            try:
                diff = log.track(
                    f"diff_{iid}",
                    lambda m_iid=iid: gl.get_mr_plain_diff(project, m_iid),
                )
                (out_dir / f"mr-{iid}-diff.patch").write_text(diff, encoding="utf-8")
            except Exception as e:
                log.error(f"mr-{iid}-diff.patch", str(e))

    # 7. Fetch MR notes if token is available
    if gl.token:
        for mr in mrs:
            if mr.get("state") in ("opened", "merged"):
                iid = mr["iid"]
                try:
                    notes = log.track(
                        f"notes_{iid}",
                        lambda m_iid=iid: gl.get_mr_notes(project, m_iid),
                    )
                    write_json(out_dir / f"mr-{iid}-notes.json", notes)
                except Exception as e:
                    log.error(f"mr-{iid}-notes.json", str(e))

    # 8. Write fetch log
    log.finalize()
    write_json(out_dir / "fetch-log.json", log.to_dict())

    if log.has_errors():
        print(
            f"PARTIAL: {log.error_count()} errors (see fetch-log.json)",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"COMPLETE: {log.request_count()} requests, 0 errors")
    sys.exit(0)


if __name__ == "__main__":
    main()
