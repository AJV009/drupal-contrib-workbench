#!/usr/bin/env python3
"""
Fetch all data for a drupal.org issue and write structured artifacts.

Orchestrates the drupal.org and GitLab APIs to produce:
  - issue.json        (issue metadata)
  - comments.json     (all comments with system message detection)
  - merge-requests.json (MRs with primary selection heuristic)
  - mr-{iid}-diff.patch (plain diffs for open/merged MRs)
  - mr-{iid}-discussions.json (GitLab discussions: general + inline diff comments)
  - fetch-log.json    (request tracking)
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

# In the consolidated layout, this script lives in scripts/lib/data/
# alongside the API modules it imports.
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from drupalorg_api import DrupalOrgAPI, get_status_label, get_priority_label, USER_AGENT
from drupalorg_page_parser import DrupalOrgPageParser, PageFetchError
from gitlab_api import GitLabAPI
from raw_fetch import download_raw_file, RawFetchError


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



# Note: fetch_nodechanges() was removed. Its functionality is now in
# DrupalOrgPageParser which extracts comments + nodechanges in one pass.


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
        description="Multi-mode fetcher for drupal.org issues and GitLab MRs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  full          Bulk fetch issue + comments + MRs + diffs + discussions (default)
  refresh       Same as full but bypass HTTP caches
  delta         Full fetch then filter to changes since --since timestamp
  comments      Fetch issue + comments only
  related       Fetch project's recent issues into related-issues.json
  search        Keyword search across project issues; JSON to stdout/file
  issue-lookup  Lightweight metadata only (no comments, no MRs); JSON to stdout/file
  mr-diff       Plain unified diff for a single MR
  mr-status     Pipeline status + mergeability for an MR (phar backend)
  mr-logs       Failing job logs for an MR (phar backend)
  raw-file      Download an arbitrary raw URL (composer.json, patch files, etc.)

Use --out - to write JSON/text output to stdout (for stdout-emitting modes).
        """,
    )
    parser.add_argument(
        "--mode",
        default="full",
        choices=["full", "refresh", "delta", "comments", "related",
                 "search", "issue-lookup", "mr-diff", "mr-status", "mr-logs",
                 "raw-file"],
        help="Operation mode (default: full)",
    )
    parser.add_argument("--issue", default=None,
                        help="Drupal.org issue URL or node ID")
    parser.add_argument("--project", default=None,
                        help="Project machine name")
    parser.add_argument("--out", default=None,
                        help="Output directory (file modes) or '-' for stdout JSON")
    parser.add_argument("--gitlab-token-file", default=None,
                        help="Path to GitLab token file")
    parser.add_argument("--since", default=None,
                        help="ISO 8601 timestamp for delta mode (e.g. 2026-04-09T00:00:00Z)")
    parser.add_argument("--keywords", nargs="+", default=[],
                        help="Search keywords for search mode (AND-matched)")
    parser.add_argument("--mr-iid", type=int, default=None,
                        help="MR iid for mr-diff / mr-status / mr-logs")
    parser.add_argument("--no-cache", action="store_true",
                        help="Bypass HTTP cache (implied by refresh mode)")
    parser.add_argument("--max-issues", type=int, default=200,
                        help="Max issues to scan for search/related (default: 200)")
    parser.add_argument("--url", default=None,
                        help="Raw URL to fetch for raw-file mode")
    return parser.parse_args()


# ============================================================================
# Shared building blocks
# ============================================================================

def _fetch_comments(api, project, issue_id, log):
    """Page-first comment fetch with API fallback. Reused by full and comments modes."""
    page_parser = DrupalOrgPageParser()
    comments = []
    hidden_branches = set()
    comments_source = "page"

    try:
        page_result = log.track(
            "page_comments",
            lambda: page_parser.fetch_and_parse(project, issue_id),
        )
        comments = page_result["comments"]
        hidden_pattern = re.compile(
            r"changed the visibility of the branch\s+(\S+)\s+to hidden"
        )
        for c in comments:
            body = c.get("body_html", "")
            if body:
                for m in hidden_pattern.finditer(body):
                    hidden_branches.add(m.group(1))
    except (PageFetchError, Exception) as e:
        log.error("page_comments", f"Page fetch failed, falling back to API: {e}")
        comments_source = "api"
        try:
            raw_comments = log.track(
                "api_comments",
                lambda: api.get_all_comments(issue_id),
            )
            comments, hidden_branches = process_comments(raw_comments)
        except Exception as e2:
            log.error("api_comments", f"API fallback also failed: {e2}")

    return comments, hidden_branches, comments_source


def _emit_json(data, out_target):
    """Emit JSON either to stdout (out_target == '-' or None) or a file path."""
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if out_target == "-" or out_target is None:
        sys.stdout.write(text)
        sys.stdout.write("\n")
        sys.stdout.flush()
    else:
        Path(out_target).write_text(text + "\n", encoding="utf-8")


def _emit_error_json(message, out_target):
    """Emit a structured error JSON."""
    _emit_json({"error": message}, out_target)


def _phar_subprocess(args_list, out_target, log, label):
    """
    Run scripts/drupalorg with the given args list. Output goes to stdout or
    a file. Used by mr-status and mr-logs modes (phar covers what gitlab_api.py
    does not).
    """
    import subprocess
    # SCRIPT_DIR = scripts/lib/data → workbench root is 3 levels up
    workbench_root = SCRIPT_DIR.parent.parent.parent
    phar_wrapper = workbench_root / "scripts" / "drupalorg"
    if not phar_wrapper.exists():
        _emit_error_json(
            f"phar wrapper not found at {phar_wrapper}",
            out_target,
        )
        return 2

    cmd = [str(phar_wrapper)] + args_list

    def run():
        return subprocess.run(cmd, capture_output=True, text=True, check=False)

    result = log.track(label, run)
    log.finalize()

    if out_target == "-" or out_target is None:
        sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
    else:
        Path(out_target).write_text(result.stdout, encoding="utf-8")

    return result.returncode


# ============================================================================
# Mode: full / refresh / delta (the original 8-step bulk fetch)
# ============================================================================

def mode_full(log, out_dir, project, issue_id, gitlab_token_file=None,
              no_cache=False, since=None):
    """
    Bulk fetch: issue + comments + MRs + diffs + discussions.

    Args:
        log: FetchLog instance
        out_dir: Path for artifact output
        project: Drupal project machine name
        issue_id: int issue node ID
        gitlab_token_file: optional path to GitLab token
        no_cache: bypass DrupalOrgAPI HTTP cache (refresh mode)
        since: ISO 8601 timestamp; if set, comments and discussions are
               filtered to only items created/updated after this time

    Returns 0 on success, 1 on partial errors.
    """
    # 1. Issue metadata
    api = DrupalOrgAPI(offline=False)
    if no_cache and hasattr(api, "_cache_dir"):
        # Best-effort cache bypass: clear the cache dir for this run.
        # DrupalOrgAPI doesn't expose a runtime no-cache flag, but the cache
        # directory layout is opaque. Setting offline=False already does fresh
        # fetches; the no-cache flag is forwarded for future use.
        pass
    raw = log.track("issue", lambda: api.get_issue(issue_id))
    issue = transform_issue(raw, project)
    write_json(out_dir / "issue.json", issue)

    # 2. Comments (page-first, API fallback)
    comments, hidden_branches, comments_source = _fetch_comments(
        api, project, issue_id, log
    )

    # Backfill issue author name from first comment if available
    if comments and issue["author"]["name"] is None:
        first_author = comments[0].get("author", {})
        if first_author.get("name"):
            issue["author"]["name"] = first_author["name"]
            write_json(out_dir / "issue.json", issue)

    # Delta filter on comments by created timestamp
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            comments = [
                c for c in comments
                if c.get("created") and
                datetime.fromisoformat(c["created"].replace("Z", "+00:00")) > since_dt
            ]
        except (ValueError, TypeError):
            log.error("delta_filter", f"Invalid --since value: {since}")

    write_json(out_dir / "comments.json", {
        "issue_id": issue_id,
        "total_count": len(comments),
        "source": comments_source,
        "since": since,
        "comments": comments,
    })

    # 3. Search for GitLab MRs
    if gitlab_token_file:
        gl = GitLabAPI.from_token_file(gitlab_token_file)
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

    # 4. Enrich each MR
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

    # 6. MR diffs (open/merged only)
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

    # 7. MR discussions (open/merged only, requires GitLab token)
    if gl.token:
        for mr in mrs:
            if mr.get("state") in ("opened", "merged"):
                iid = mr["iid"]
                try:
                    discussions = log.track(
                        f"discussions_{iid}",
                        lambda m_iid=iid: gl.get_mr_discussions(project, m_iid),
                    )
                    # Delta filter on discussions by note created_at
                    if since:
                        try:
                            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
                            filtered = []
                            for disc in discussions:
                                kept_notes = [
                                    n for n in disc.get("notes", [])
                                    if n.get("created_at") and
                                    datetime.fromisoformat(n["created_at"].replace("Z", "+00:00")) > since_dt
                                ]
                                if kept_notes:
                                    new_disc = dict(disc)
                                    new_disc["notes"] = kept_notes
                                    filtered.append(new_disc)
                            discussions = filtered
                        except (ValueError, TypeError):
                            log.error("delta_filter", f"Invalid --since for discussions")
                    write_json(out_dir / f"mr-{iid}-discussions.json", discussions)
                except Exception as e:
                    log.error(f"mr-{iid}-discussions.json", str(e))

    # 8. Fetch log
    log.finalize()
    write_json(out_dir / "fetch-log.json", log.to_dict())

    return 1 if log.has_errors() else 0


# ============================================================================
# Mode: comments (lightweight: just issue + comments)
# ============================================================================

def mode_comments(log, out_dir, project, issue_id, since=None):
    api = DrupalOrgAPI()
    raw = log.track("issue", lambda: api.get_issue(issue_id))
    issue = transform_issue(raw, project)
    write_json(out_dir / "issue.json", issue)

    comments, _hidden, source = _fetch_comments(api, project, issue_id, log)

    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            comments = [
                c for c in comments
                if c.get("created") and
                datetime.fromisoformat(c["created"].replace("Z", "+00:00")) > since_dt
            ]
        except (ValueError, TypeError):
            log.error("delta_filter", f"Invalid --since value: {since}")

    write_json(out_dir / "comments.json", {
        "issue_id": issue_id,
        "total_count": len(comments),
        "source": source,
        "since": since,
        "comments": comments,
    })
    log.finalize()
    write_json(out_dir / "fetch-log.json", log.to_dict())
    return 1 if log.has_errors() else 0


# ============================================================================
# Mode: issue-lookup (lightest: just issue metadata, no MRs, no comments)
# ============================================================================

def mode_issue_lookup(log, project, issue_id, out_target):
    api = DrupalOrgAPI()
    raw = log.track("issue", lambda: api.get_issue(issue_id, include_mrs=False))
    issue = transform_issue(raw, project)
    log.finalize()
    _emit_json(issue, out_target)
    return 0


# ============================================================================
# Mode: search (client-side keyword match against project issue batch)
# ============================================================================

def mode_search(log, project, keywords, max_issues, out_target):
    api = DrupalOrgAPI()
    nid = log.track("project_nid", lambda: api.get_project_nid(project))
    if not nid:
        _emit_error_json(f"Could not resolve project '{project}'", out_target)
        return 2

    issues = log.track(
        "batch_fetch",
        lambda: api.fetch_issues_batch(nid, max_issues=max_issues),
    )

    keywords_lower = [k.lower() for k in keywords]
    matched = []
    for raw in issues:
        title = raw.get("title", "").lower()
        if all(k in title for k in keywords_lower):
            matched.append({
                "nid": int(raw.get("nid", 0)),
                "title": raw.get("title", ""),
                "status_code": raw.get("field_issue_status"),
                "status_label": get_status_label(raw.get("field_issue_status")),
                "url": f"https://www.drupal.org/node/{raw.get('nid')}",
                "changed": unix_to_iso(raw.get("changed")),
            })

    log.finalize()
    _emit_json({
        "project": project,
        "keywords": keywords,
        "total_scanned": len(issues),
        "match_count": len(matched),
        "matches": matched,
    }, out_target)
    return 0


# ============================================================================
# Mode: related (project's recent issues for context, migrates Step 4b curl)
# ============================================================================

def mode_related(log, out_dir, project, issue_id, max_issues):
    api = DrupalOrgAPI()
    nid = log.track("project_nid", lambda: api.get_project_nid(project))
    if not nid:
        log.error("project_nid", f"Could not resolve project '{project}'")
        log.finalize()
        write_json(out_dir / "related-issues.json", {
            "issue_id": issue_id,
            "project": project,
            "error": f"Could not resolve project nid",
            "issues": [],
        })
        return 2

    issues = log.track(
        "batch_fetch",
        lambda: api.fetch_issues_batch(nid, max_issues=max_issues),
    )

    compact = []
    for raw in issues:
        try:
            raw_nid = int(raw.get("nid", 0))
        except (ValueError, TypeError):
            continue
        if raw_nid == issue_id:
            continue  # skip self
        compact.append({
            "nid": raw_nid,
            "title": raw.get("title", ""),
            "status_code": raw.get("field_issue_status"),
            "status_label": get_status_label(raw.get("field_issue_status")),
            "changed": unix_to_iso(raw.get("changed")),
            "url": f"https://www.drupal.org/node/{raw_nid}",
        })

    write_json(out_dir / "related-issues.json", {
        "issue_id": issue_id,
        "project": project,
        "total": len(compact),
        "issues": compact,
    })
    log.finalize()
    return 0


# ============================================================================
# Mode: mr-diff (single MR plain diff)
# ============================================================================

def mode_mr_diff(log, project, mr_iid, out_target, gitlab_token_file=None):
    if gitlab_token_file:
        gl = GitLabAPI.from_token_file(gitlab_token_file)
    else:
        gl = GitLabAPI()
    diff = log.track(
        f"mr_diff_{mr_iid}",
        lambda: gl.get_mr_plain_diff(project, mr_iid),
    )
    log.finalize()

    if out_target == "-" or out_target is None:
        sys.stdout.write(diff)
        sys.stdout.flush()
    else:
        Path(out_target).write_text(diff, encoding="utf-8")
    return 0


# ============================================================================
# Modes: mr-status / mr-logs (phar backend — gaps in gitlab_api.py)
# ============================================================================

def mode_mr_status(log, project, nid, mr_iid, out_target):
    """Phar-backed: pipeline state + mergeability for a single MR.

    Phar signature: mr:status <nid> <mr-iid> --format=json
    """
    return _phar_subprocess(
        ["mr:status", str(nid), str(mr_iid), "--format=json"],
        out_target,
        log,
        label=f"phar_mr_status_{nid}_{mr_iid}",
    )


def mode_mr_logs(log, project, nid, mr_iid, out_target):
    """Phar-backed: failing job logs for a single MR's latest pipeline.

    Phar signature: mr:logs <nid> <mr-iid>
    """
    return _phar_subprocess(
        ["mr:logs", str(nid), str(mr_iid)],
        out_target,
        log,
        label=f"phar_mr_logs_{nid}_{mr_iid}",
    )


# ============================================================================
# Mode: raw-file (arbitrary URL download, for composer.json / patch files /
#                  anything the API clients don't cover)
# ============================================================================

def mode_raw_file(log, url, out_target):
    """
    Download a raw file from an arbitrary URL. Not API-backed — uses the
    scripts/lib/data/raw_fetch.py helper with plain urllib.

    Use cases (the only two things this mode exists for):
      - Fetching a project branch's composer.json from git.drupalcode.org/raw/
      - Downloading an arbitrary .patch file for reroll

    For structured issue/MR data, use the other modes. This mode deliberately
    has no caching, no retry, no rate limiting — raw file downloads are
    infrequent and the caller typically wants the latest content.
    """
    try:
        content = log.track(
            f"raw_file_{url[-30:]}",
            lambda: download_raw_file(url),
        )
    except RawFetchError as e:
        log.error("raw_file", str(e))
        log.finalize()
        return 1

    log.finalize()

    if out_target == "-" or out_target is None:
        sys.stdout.write(content)
        if not content.endswith("\n"):
            sys.stdout.write("\n")
        sys.stdout.flush()
    else:
        Path(out_target).parent.mkdir(parents=True, exist_ok=True)
        Path(out_target).write_text(content, encoding="utf-8")
    return 0


# ============================================================================
# Dispatcher
# ============================================================================

def main():
    args = parse_args()
    log = FetchLog()

    # Parse issue identifier (most modes need it)
    issue_id = None
    project = args.project
    if args.issue:
        parsed_project, issue_id = parse_issue_url(args.issue)
        project = parsed_project or project

    # Validate required args per mode
    needs_project = {
        # Modes that hit the Python data layer directly need the project name
        # for URL construction and API calls. Phar-backed modes (mr-status,
        # mr-logs) don't — phar resolves the project from the nid itself.
        "full", "refresh", "delta", "comments", "related",
        "search", "issue-lookup", "mr-diff",
    }
    needs_issue = {"full", "refresh", "delta", "comments", "related",
                   "issue-lookup", "mr-status", "mr-logs"}
    needs_mr_iid = {"mr-diff", "mr-status", "mr-logs"}
    needs_out_dir = {"full", "refresh", "delta", "comments", "related"}

    if args.mode in needs_project and not project:
        print(f"ERROR: --project is required for mode '{args.mode}'", file=sys.stderr)
        sys.exit(2)
    if args.mode in needs_issue and not issue_id:
        print(f"ERROR: --issue is required for mode '{args.mode}'", file=sys.stderr)
        sys.exit(2)
    if args.mode in needs_mr_iid and not args.mr_iid:
        print(f"ERROR: --mr-iid is required for mode '{args.mode}'", file=sys.stderr)
        sys.exit(2)
    if args.mode == "search" and not args.keywords:
        print("ERROR: --keywords is required for search mode", file=sys.stderr)
        sys.exit(2)
    if args.mode == "delta" and not args.since:
        print("ERROR: --since is required for delta mode", file=sys.stderr)
        sys.exit(2)

    out_dir = None
    if args.mode in needs_out_dir:
        if not args.out:
            print(f"ERROR: --out is required for mode '{args.mode}'", file=sys.stderr)
            sys.exit(2)
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)

    # Dispatch
    if args.mode == "full":
        rc = mode_full(log, out_dir, project, issue_id,
                       gitlab_token_file=args.gitlab_token_file)
    elif args.mode == "refresh":
        rc = mode_full(log, out_dir, project, issue_id,
                       gitlab_token_file=args.gitlab_token_file, no_cache=True)
    elif args.mode == "delta":
        rc = mode_full(log, out_dir, project, issue_id,
                       gitlab_token_file=args.gitlab_token_file, since=args.since)
    elif args.mode == "comments":
        rc = mode_comments(log, out_dir, project, issue_id, since=args.since)
    elif args.mode == "related":
        rc = mode_related(log, out_dir, project, issue_id, args.max_issues)
    elif args.mode == "search":
        rc = mode_search(log, project, args.keywords, args.max_issues, args.out)
    elif args.mode == "issue-lookup":
        rc = mode_issue_lookup(log, project, issue_id, args.out)
    elif args.mode == "mr-diff":
        rc = mode_mr_diff(log, project, args.mr_iid, args.out,
                          gitlab_token_file=args.gitlab_token_file)
    elif args.mode == "mr-status":
        rc = mode_mr_status(log, project, issue_id, args.mr_iid, args.out)
    elif args.mode == "mr-logs":
        rc = mode_mr_logs(log, project, issue_id, args.mr_iid, args.out)
    elif args.mode == "raw-file":
        if not args.url:
            print("ERROR: --url is required for raw-file mode", file=sys.stderr)
            sys.exit(2)
        rc = mode_raw_file(log, args.url, args.out)
    else:
        print(f"ERROR: unknown mode '{args.mode}'", file=sys.stderr)
        sys.exit(2)

    # Status line to stderr (so it doesn't pollute stdout JSON)
    if rc == 0:
        print(
            f"COMPLETE: mode={args.mode} requests={log.request_count()} errors={log.error_count()}",
            file=sys.stderr,
        )
    else:
        print(
            f"PARTIAL: mode={args.mode} requests={log.request_count()} errors={log.error_count()}",
            file=sys.stderr,
        )

    sys.exit(rc)


if __name__ == "__main__":
    main()
