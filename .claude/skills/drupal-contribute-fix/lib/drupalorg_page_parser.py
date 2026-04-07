"""
Drupal.org issue page parser.

Fetches the rendered HTML page for a drupal.org issue and extracts
structured comment data including field changes (status, version,
assignment, tags) that are NOT available via the JSON API.

Replaces the comment.json API calls with a single page fetch that
provides richer data. The JSON API is still used for issue metadata
(status codes, UIDs, timestamps) since those are cleaner as structured
fields.

Usage:
    parser = DrupalOrgPageParser()
    result = parser.fetch_and_parse("ai", 3581952)
    # result["comments"] is a list of comment dicts
    # result["issue_meta"] has sidebar metadata
"""

import html
import re
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple

USER_AGENT = (
    "drupal-contribute-fix/1.0 "
    "(https://github.com/drupal-contribute-fix; community contribution helper)"
)


def _strip_html(text: str) -> str:
    """Strip HTML tags and decode entities."""
    return html.unescape(re.sub(r'<[^>]+>', '', text)).strip()


def _extract_image_urls(html_text: str) -> List[str]:
    """Extract non-decorative image URLs from HTML.

    Filters out user avatars, theme assets, and other decorative images.
    Only returns images that are likely screenshots or attachments.
    """
    urls = re.findall(r'<img[^>]+src="([^"]+)"', html_text)
    decorative_patterns = [
        '/user-pictures/',
        '/user_picture/',
        'drupalorg_user_picture',
        '/themes/',
        '/bluecheese/',
        '/drupalorg/',
        'community-dk-comments',
        'location-icon',
        'gravatar',
    ]
    result = []
    for url in urls:
        if any(p in url for p in decorative_patterns):
            continue
        result.append(url)
    return result


def _extract_mr_references(html_text: str) -> List[str]:
    """Extract GitLab MR URLs from HTML."""
    pattern = re.compile(
        r'https?://git\.drupalcode\.org/project/[^/]+/-/merge_requests/\d+'
    )
    seen = set()
    refs = []
    for m in pattern.finditer(html_text):
        url = m.group(0)
        if url not in seen:
            seen.add(url)
            refs.append(url)
    return refs


class DrupalOrgPageParser:
    """Parses drupal.org issue pages to extract comments and metadata."""

    def fetch_and_parse(
        self, project: str, issue_id: int
    ) -> Dict:
        """Fetch an issue page and parse all comments.

        Args:
            project: Project machine name (e.g., "ai").
            issue_id: Issue node ID.

        Returns:
            Dict with keys:
              "comments": list of comment dicts
              "issue_meta": dict with sidebar metadata extracted from page
              "raw_html_length": int (for diagnostics)

        Raises:
            PageFetchError on network/HTTP failure.
        """
        page_html = self._fetch_page(project, issue_id)
        comments = self._parse_comments(page_html)
        issue_meta = self._parse_sidebar(page_html)
        return {
            "comments": comments,
            "issue_meta": issue_meta,
            "raw_html_length": len(page_html),
        }

    def _fetch_page(self, project: str, issue_id: int) -> str:
        """Fetch the rendered issue page HTML."""
        url = f"https://www.drupal.org/project/{project}/issues/{issue_id}"
        request = urllib.request.Request(url)
        request.add_header("User-Agent", USER_AGENT)
        request.add_header("Accept", "text/html")

        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            raise PageFetchError(
                f"HTTP {e.code} fetching {url}: {e.reason}"
            ) from e
        except urllib.error.URLError as e:
            raise PageFetchError(
                f"Network error fetching {url}: {e.reason}"
            ) from e

    def _parse_comments(self, page_html: str) -> List[Dict]:
        """Parse all comments from the issue page HTML.

        Returns a list of comment dicts, each containing:
          number: int (1-based comment number)
          cid: str (drupal comment ID)
          author: {uid: int|None, name: str}
          created: str (ISO datetime or raw date string)
          body_html: str (raw HTML of comment body)
          is_system_message: bool
          mr_references: list of MR URLs
          field_changes: list of {field, old, new} dicts (may be empty)
          images: list of non-decorative image URLs (may be empty)
        """
        # Find all comment anchors with their positions.
        comment_positions = [
            (m.start(), m.group(1))
            for m in re.finditer(r'id="comment-(\d+)"', page_html)
        ]

        if not comment_positions:
            return []

        comments = []
        for i, (pos, cid) in enumerate(comment_positions):
            end = (
                comment_positions[i + 1][0]
                if i + 1 < len(comment_positions)
                else len(page_html)
            )
            section = page_html[pos:end]
            comment = self._parse_single_comment(cid, section, i + 1)
            comments.append(comment)

        return comments

    def _parse_single_comment(
        self, cid: str, section: str, number: int
    ) -> Dict:
        """Parse a single comment section."""
        author_name, author_uid = self._extract_author(section)
        created = self._extract_date(section)
        body_html = self._extract_body(section)
        field_changes = self._extract_field_changes(section)
        images = _extract_image_urls(body_html) if body_html else []
        mr_refs = _extract_mr_references(section)
        is_system = self._detect_system_message(author_name, body_html)

        return {
            "number": number,
            "cid": cid,
            "author": {
                "uid": author_uid,
                "name": author_name,
            },
            "created": created,
            "body_html": body_html,
            "is_system_message": is_system,
            "mr_references": mr_refs,
            "field_changes": field_changes,
            "images": images,
        }

    def _extract_author(self, section: str) -> Tuple[str, Optional[int]]:
        """Extract author name and UID from a comment section."""
        # Pattern: <a href="/u/username" data-uid="12345" class="username">
        uid_match = re.search(
            r'<a[^>]*href="/u(?:ser)?/[^"]*"[^>]*data-uid="(\d+)"[^>]*'
            r'class="[^"]*username[^"]*"[^>]*>([^<]+)</a>',
            section,
        )
        if uid_match:
            return uid_match.group(2).strip(), int(uid_match.group(1))

        # Fallback: just username class without data-uid
        name_match = re.search(
            r'<a[^>]*href="/u(?:ser)?/[^"]*"[^>]*>([^<]+)</a>',
            section,
        )
        if name_match:
            return name_match.group(1).strip(), None

        # Fallback: username class on a span
        span_match = re.search(
            r'class="[^"]*username[^"]*"[^>]*>([^<]+)<', section
        )
        if span_match:
            return span_match.group(1).strip(), None

        return "", None

    def _extract_date(self, section: str) -> str:
        """Extract the comment date as an ISO string."""
        # <time datetime="2026-04-07T13:49:36+00:00">
        time_match = re.search(
            r'<time[^>]*datetime="([^"]+)"', section
        )
        if time_match:
            return time_match.group(1)
        return ""

    def _extract_body(self, section: str) -> str:
        """Extract the comment body HTML.

        Tries multiple patterns that drupal.org uses for comment content.
        Returns raw HTML (not stripped) to preserve formatting and images.
        """
        # Pattern 1: field-name-comment-body > field-items > field-item
        # The body is nested: field-name-comment-body > field-items > field-item even
        # We want the innerHTML of the innermost field-item div.
        match = re.search(
            r'<div[^>]*class="[^"]*field-name-comment-body[^"]*"[^>]*>'
            r'\s*<div[^>]*class="[^"]*field-items[^"]*"[^>]*>'
            r'\s*<div[^>]*class="[^"]*field-item[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
            section, re.DOTALL,
        )
        if match:
            return match.group(1).strip()

        # Pattern 1b: field-name-comment-body > field-item (no field-items wrapper)
        match = re.search(
            r'<div[^>]*class="[^"]*field-name-comment-body[^"]*"[^>]*>'
            r'.*?<div[^>]*class="[^"]*field-item[^"]*"[^>]*>(.*?)</div>',
            section, re.DOTALL,
        )
        if match:
            return match.group(1).strip()

        # Pattern 2: field--name-comment-body (Drupal 8+ BEM style)
        match = re.search(
            r'<div[^>]*class="[^"]*field--name-comment-body[^"]*"[^>]*>'
            r'(.*?)</div>\s*</div>',
            section, re.DOTALL,
        )
        if match:
            return match.group(1).strip()

        # Pattern 3: text-formatted clearfix
        match = re.search(
            r'<div[^>]*class="[^"]*clearfix[^"]*text-formatted[^"]*"[^>]*>'
            r'(.*?)</div>',
            section, re.DOTALL,
        )
        if match:
            return match.group(1).strip()

        return ""

    def _extract_field_changes(self, section: str) -> List[Dict]:
        """Extract nodechanges (field changes) from a comment section.

        Parses the nodechanges-field-changes table that drupal.org renders
        for status, version, assignment, tag, and related issue changes.
        """
        table_match = re.search(
            r'<table[^>]*class="[^"]*nodechanges[^"]*"[^>]*>(.*?)</table>',
            section, re.DOTALL,
        )
        if not table_match:
            return []

        table_html = table_match.group(1)
        changes = []

        for tr_match in re.finditer(
            r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL
        ):
            tr = tr_match.group(1)

            # Label cell (always present).
            label_match = re.search(
                r'<td[^>]*class="nodechanges-label"[^>]*>(.*?)</td>',
                tr, re.DOTALL,
            )
            if not label_match:
                continue
            field = _strip_html(label_match.group(1)).rstrip(':')

            # Old/new pattern (two value columns).
            old_match = re.search(
                r'<td[^>]*class="nodechanges-old"[^>]*>(.*?)</td>',
                tr, re.DOTALL,
            )
            new_match = re.search(
                r'<td[^>]*class="nodechanges-new"[^>]*>(.*?)</td>',
                tr, re.DOTALL,
            )
            if old_match and new_match:
                old_val = _strip_html(old_match.group(1)).lstrip('\u00bb').strip()
                new_val = _strip_html(new_match.group(1)).lstrip('\u00bb').strip()
                changes.append({"field": field, "old": old_val, "new": new_val})
                continue

            # Colspan changed column (issue summary edits).
            changed_match = re.search(
                r'<td[^>]*class="nodechanges-changed"[^>]*>(.*?)</td>',
                tr, re.DOTALL,
            )
            if changed_match:
                detail = _strip_html(changed_match.group(1))
                changes.append({"field": field, "old": "", "new": detail})

        return changes

    def _detect_system_message(self, author: str, body: str) -> bool:
        """Detect if a comment is a system/automated message."""
        if "System Message" in author:
            return True

        if not body:
            return False

        body_text = _strip_html(body).lower()
        system_phrases = [
            "opened merge request",
            "made their first commit",
            "changed the visibility",
        ]
        for phrase in system_phrases:
            if phrase in body_text:
                return True

        if re.search(r'committed [a-f0-9]+ on ', body_text):
            return True

        return False

    def _parse_sidebar(self, page_html: str) -> Dict:
        """Extract issue metadata from the page sidebar.

        Returns a dict with labels (not codes) for fields that are
        visible on the page. The caller should prefer API metadata
        for machine-readable codes/IDs.
        """
        meta = {}

        # These are informational, not canonical. API is the source of truth.
        patterns = {
            "status_label": r'<span[^>]*class="[^"]*field-name-field-issue-status[^"]*"[^>]*>.*?<span[^>]*>(.*?)</span>',
            "version_label": r'<span[^>]*class="[^"]*field-name-field-issue-version[^"]*"[^>]*>.*?<span[^>]*>(.*?)</span>',
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, page_html, re.DOTALL)
            if match:
                meta[key] = _strip_html(match.group(1))

        return meta


class PageFetchError(Exception):
    """Raised when the issue page cannot be fetched."""
    pass
