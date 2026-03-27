# Issue Fetcher + DDEV Setup Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two Claude Code agents: a Python-backed issue data fetcher that writes structured artifacts, and a DDEV environment setup agent that uses learned patterns from past sessions.

**Architecture:** Python script (stdlib only, no external deps) handles all API calls and file writing. Claude agent validates completeness and retries failures. Separate DDEV agent handles environment scaffolding. Both integrate into the existing `/drupal-issue` skill flow.

**Tech Stack:** Python 3 (stdlib: urllib, json, pathlib, time, re, html.parser), Claude Code agents (.md definitions), existing drupalorg_api.py patterns

**Spec:** `docs/superpowers/specs/2026-03-23-issue-fetcher-ddev-agents-design.md`

---

## File Structure

```
skills/drupal-contribute-fix/
  lib/
    drupalorg_api.py          # MODIFY: add get_all_comments() with pagination
    gitlab_api.py             # CREATE: GitLab API client for MRs, diffs, notes
  scripts/
    fetch_issue.py            # CREATE: main fetcher script

.claude/agents/
  drupal-issue-fetcher.md     # CREATE: fetcher agent definition
  drupal-ddev-setup.md        # CREATE: DDEV setup agent definition

skills/drupal-issue/
  SKILL.md                    # MODIFY: dispatch fetcher, read artifacts

skills/drupal-issue-review/
  SKILL.md                    # MODIFY: use artifacts, delegate DDEV to agent
```

---

### Task 1: Enhance drupalorg_api.py with comment pagination

The existing `get_comments()` only fetches page 0. For issues with 100+ comments (~44 per page), this misses most of the thread.

**Files:**
- Modify: `skills/drupal-contribute-fix/lib/drupalorg_api.py:254-266`

- [ ] **Step 1: Read the existing get_comments method**

Read `skills/drupal-contribute-fix/lib/drupalorg_api.py` lines 254-266 to confirm the current implementation.

- [ ] **Step 2: Add get_all_comments method**

Add a new method to the `DrupalOrgAPI` class that paginates through all comment pages:

```python
def get_all_comments(self, issue_nid: int) -> List[Dict]:
    """
    Get ALL comments for an issue, paginating through all pages.

    The d.o API returns ~44 comments per page. Navigation links
    (self, first, last, next) indicate when more pages exist.

    Args:
        issue_nid: Issue node ID

    Returns:
        List of all comments in chronological order
    """
    all_comments = []
    page = 0

    while True:
        params = {"node": issue_nid, "page": page}
        result = self._request("comment.json", params, cache_type="issue_detail")
        batch = result.get("list", [])
        if not batch:
            break
        all_comments.extend(batch)

        # Check if there are more pages via navigation links
        nav_next = result.get("next", "")
        nav_self = result.get("self", "")
        if not nav_next or nav_next == nav_self:
            break
        page += 1

    return all_comments
```

- [ ] **Step 3: Verify the method works**

Run a quick test against a known issue:
```bash
cd /home/alphons/project/freelygive/drupal/CONTRIB_WORKBENCH
python3 -c "
import sys
sys.path.insert(0, '.claude/skills/drupal-contribute-fix/lib')
from drupalorg_api import DrupalOrgAPI
api = DrupalOrgAPI()
comments = api.get_all_comments(3533079)
print(f'Fetched {len(comments)} comments')
# Issue 3533079 has 109 comments, should get all of them
assert len(comments) > 50, f'Expected 100+ comments, got {len(comments)}'
print('PASS')
"
```
Expected: "Fetched 109 comments" (or close), "PASS"

---

### Task 2: Create GitLab API client

New module for git.drupalcode.org API calls. Follows the same patterns as drupalorg_api.py (stdlib only, rate limiting, caching).

**Files:**
- Create: `skills/drupal-contribute-fix/lib/gitlab_api.py`

- [ ] **Step 1: Create the GitLab API client**

Create `skills/drupal-contribute-fix/lib/gitlab_api.py`:

```python
"""
GitLab API client for git.drupalcode.org.

Handles MR search, metadata, diffs, and notes (authenticated).
Uses only stdlib (urllib). Follows same patterns as drupalorg_api.py.
"""

import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Optional, Dict, List, Any

GITLAB_BASE = "https://git.drupalcode.org"
API_BASE = f"{GITLAB_BASE}/api/v4"
USER_AGENT = "drupal-issue-fetcher/1.0"

# Rate limiting (GitLab allows 180 req/period unauthenticated)
MIN_REQUEST_INTERVAL = 0.5  # seconds between requests


class GitLabAPIError(Exception):
    """Exception for GitLab API errors."""
    pass


class GitLabAPI:
    """Client for git.drupalcode.org GitLab API."""

    def __init__(self, token: Optional[str] = None):
        """
        Initialize the GitLab API client.

        Args:
            token: Personal access token for authenticated requests.
                   Required for MR notes. Optional for other endpoints.
        """
        self.token = token
        self._last_request_time = 0.0

    @classmethod
    def from_token_file(cls, token_path: str) -> 'GitLabAPI':
        """Create client from a token file path."""
        path = Path(token_path)
        if path.exists():
            token = path.read_text().strip()
            return cls(token=token)
        return cls(token=None)

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def _request(self, url: str, paginate: bool = False,
                 per_page: int = 100) -> Any:
        """
        Make a GitLab API request.

        Args:
            url: Full API URL
            paginate: If True, follow pagination to get all results
            per_page: Items per page when paginating

        Returns:
            JSON response (dict or list)
        """
        self._rate_limit()

        # Add pagination params
        separator = '&' if '?' in url else '?'
        full_url = f"{url}{separator}per_page={per_page}"

        request = urllib.request.Request(full_url)
        request.add_header("User-Agent", USER_AGENT)
        if self.token:
            request.add_header("PRIVATE-TOKEN", self.token)

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))

                if not paginate:
                    return data

                # Handle pagination
                all_data = data if isinstance(data, list) else [data]
                total_pages = int(response.headers.get('x-total-pages', 1))

                for page in range(2, total_pages + 1):
                    self._rate_limit()
                    page_url = f"{full_url}&page={page}"
                    page_req = urllib.request.Request(page_url)
                    page_req.add_header("User-Agent", USER_AGENT)
                    if self.token:
                        page_req.add_header("PRIVATE-TOKEN", self.token)
                    with urllib.request.urlopen(page_req, timeout=30) as page_resp:
                        page_data = json.loads(page_resp.read().decode('utf-8'))
                        if isinstance(page_data, list):
                            all_data.extend(page_data)

                return all_data

        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise GitLabAPIError(
                    f"Authentication required for {url}. "
                    "Provide a GitLab token."
                )
            raise GitLabAPIError(f"GitLab API error: {e.code} {e.reason}")
        except urllib.error.URLError as e:
            raise GitLabAPIError(f"Network error: {e.reason}")

    def _project_path(self, project: str) -> str:
        """URL-encode a project path like 'project/canvas'."""
        return urllib.parse.quote(f"project/{project}", safe='')

    def search_merge_requests(self, project: str, issue_id: int) -> List[Dict]:
        """
        Search for MRs related to an issue number.

        Args:
            project: Project machine name (e.g., 'ai', 'canvas')
            issue_id: Drupal.org issue node ID

        Returns:
            List of MR metadata dicts
        """
        path = self._project_path(project)
        url = f"{API_BASE}/projects/{path}/merge_requests?search={issue_id}&state=all"
        return self._request(url, paginate=True)

    def get_merge_request(self, project: str, iid: int) -> Dict:
        """
        Get detailed MR metadata.

        Args:
            project: Project machine name
            iid: MR internal ID

        Returns:
            MR metadata dict
        """
        path = self._project_path(project)
        url = f"{API_BASE}/projects/{path}/merge_requests/{iid}"
        return self._request(url)

    def get_mr_diffs(self, project: str, iid: int) -> List[Dict]:
        """
        Get diffs for an MR.

        Args:
            project: Project machine name
            iid: MR internal ID

        Returns:
            List of diff objects (one per file)
        """
        path = self._project_path(project)
        url = f"{API_BASE}/projects/{path}/merge_requests/{iid}/diffs"
        return self._request(url, paginate=True)

    def get_mr_plain_diff(self, project: str, iid: int) -> str:
        """
        Get the complete unified diff as plain text.

        Args:
            project: Project machine name
            iid: MR internal ID

        Returns:
            Complete diff as a string
        """
        url = f"{GITLAB_BASE}/project/{project}/-/merge_requests/{iid}.diff"
        self._rate_limit()

        request = urllib.request.Request(url)
        request.add_header("User-Agent", USER_AGENT)

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            raise GitLabAPIError(f"Failed to fetch diff: {e.code} {e.reason}")

    def get_mr_notes(self, project: str, iid: int) -> List[Dict]:
        """
        Get discussion notes/comments on an MR.
        Requires authentication.

        Args:
            project: Project machine name
            iid: MR internal ID

        Returns:
            List of note objects
        """
        if not self.token:
            raise GitLabAPIError(
                "Authentication required for MR notes. "
                "Provide a GitLab token."
            )
        path = self._project_path(project)
        url = f"{API_BASE}/projects/{path}/merge_requests/{iid}/notes?sort=asc&order_by=created_at"
        return self._request(url, paginate=True)
```

- [ ] **Step 2: Verify MR search works**

```bash
python3 -c "
import sys
sys.path.insert(0, '.claude/skills/drupal-contribute-fix/lib')
from gitlab_api import GitLabAPI
gl = GitLabAPI.from_token_file('git.drupalcode.org.key')
mrs = gl.search_merge_requests('ai', 3575190)
print(f'Found {len(mrs)} MRs')
for mr in mrs:
    print(f'  !{mr[\"iid\"]} ({mr[\"state\"]}): {mr[\"target_branch\"]}')
assert len(mrs) >= 2, 'Expected at least 2 MRs'
print('PASS')
"
```
Expected: "Found 2 MRs", both listed, "PASS"

- [ ] **Step 3: Verify MR notes with auth**

```bash
python3 -c "
import sys
sys.path.insert(0, '.claude/skills/drupal-contribute-fix/lib')
from gitlab_api import GitLabAPI
gl = GitLabAPI.from_token_file('git.drupalcode.org.key')
notes = gl.get_mr_notes('canvas', 18)
print(f'Fetched {len(notes)} notes')
assert len(notes) > 50, f'Expected 100+ notes, got {len(notes)}'
print('PASS')
"
```
Expected: "Fetched 191 notes" (or close), "PASS"

---

### Task 3: Create fetch_issue.py main script

The orchestrator script that calls both APIs and writes all artifacts.

**Files:**
- Create: `skills/drupal-contribute-fix/scripts/fetch_issue.py`

- [ ] **Step 1: Create the script**

Create `skills/drupal-contribute-fix/scripts/fetch_issue.py`. This is the largest file. Key sections:

1. **Argument parsing**: `--issue`, `--project`, `--out`, `--gitlab-token-file`
2. **URL parsing**: Extract issue ID and project from drupal.org URLs
3. **Issue fetching**: Call d.o API, transform into `issue.json` schema
4. **Comment fetching**: Call paginated comments API, number them, detect system messages, extract MR references
5. **MR fetching**: Search GitLab, fetch metadata for each, compute heuristics, determine primary
6. **Diff fetching**: Download plain diff for each open MR
7. **Notes fetching**: If token available, fetch MR notes
8. **Fetch log**: Track every request with URL, status, duration
9. **File writing**: Write each artifact as JSON/patch to the output directory

The script should:
- Parse `https://www.drupal.org/project/{project}/issues/{nid}` URLs to extract project and issue ID
- Also accept just a number (requires `--project` flag)
- Create output directory if it doesn't exist
- Write `fetch-log.json` as it goes (append mode) so the agent can check progress even if the script crashes
- Exit 0 (complete), 1 (partial), or 2 (fatal)

Key implementation details:

**URL parsing:**
```python
import re

def parse_issue_url(url_or_id: str) -> tuple:
    """Parse issue URL or ID into (project, issue_id)."""
    # Full URL: https://www.drupal.org/project/{project}/issues/{nid}
    match = re.match(
        r'https?://www\.drupal\.org/project/([^/]+)/issues/(\d+)',
        url_or_id
    )
    if match:
        return match.group(1), int(match.group(2))
    # Just a number
    if url_or_id.strip().isdigit():
        return None, int(url_or_id.strip())
    raise ValueError(f"Cannot parse issue: {url_or_id}")
```

**Comment processing:**
```python
import re
from html.parser import HTMLParser

class MRLinkExtractor(HTMLParser):
    """Extract MR links from comment HTML."""
    def __init__(self):
        super().__init__()
        self.mr_refs = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = dict(attrs).get('href', '')
            mr_match = re.search(
                r'git\.drupalcode\.org/project/([^/]+)/-/merge_requests/(\d+)',
                href
            )
            if mr_match:
                self.mr_refs.append({
                    'iid': int(mr_match.group(2)),
                    'url': href,
                })

def process_comment(raw_comment: dict, number: int) -> dict:
    """Transform a raw d.o API comment into our schema."""
    body = raw_comment.get('comment_body', {}).get('value', '')
    author_name = raw_comment.get('name', '')

    # Detect system messages
    is_system = author_name == 'System Message' or (
        'opened merge request' in body.lower() or
        'made their first commit' in body.lower() or
        'changed the visibility' in body.lower() or
        'committed' in body.lower() and 'on 1.x' in body.lower()
    )

    # Extract MR references
    extractor = MRLinkExtractor()
    extractor.feed(body)

    return {
        'number': number,
        'cid': raw_comment.get('cid', ''),
        'author': {
            'uid': int(raw_comment.get('author', {}).get('id', 0)),
            'name': author_name,
        },
        'created': raw_comment.get('created', ''),
        'body_html': body,
        'is_system_message': is_system,
        'mr_references': extractor.mr_refs,
    }
```

**Primary MR heuristic:**
```python
def determine_primary_mr(mrs: list, issue_version: str,
                         hidden_branches: set) -> tuple:
    """
    Determine which MR is the primary one.

    Returns (primary_iid, reason_string)
    """
    # Strip -dev from version for matching
    target_version = issue_version.replace('-dev', '')

    # Filter candidates
    candidates = [mr for mr in mrs if mr['state'] not in ('closed',)]

    # If all closed/merged, pick the merged one
    if not candidates:
        merged = [mr for mr in mrs if mr['state'] == 'merged']
        if merged:
            best = max(merged, key=lambda m: m.get('merged_at', ''))
            return best['iid'], f"MR !{best['iid']} is the merged MR"
        return None, "No viable MRs found"

    # Score each candidate
    for mr in candidates:
        score = 0
        reasons = []

        # Signal 1: version match
        if mr['target_branch'] == target_version:
            score += 100
            reasons.append(f"targets {target_version} (matches issue version)")

        # Signal 2: most recently updated
        # (will compare after scoring)

        # Signal 3: not hidden
        if mr.get('source_branch', '') not in hidden_branches:
            score += 10
            reasons.append("branch is visible")
        else:
            score -= 50
            reasons.append("branch hidden (likely abandoned)")

        # Signal 4: activity
        if mr.get('user_notes_count', 0) > 0:
            score += 5
            reasons.append(f"{mr['user_notes_count']} review comments")

        # Signal 5: not draft
        if not mr.get('draft', False):
            score += 5

        mr['_score'] = score
        mr['_reasons'] = reasons

    # Sort by score (desc), then by updated_at (desc)
    candidates.sort(key=lambda m: (m['_score'], m.get('updated_at', '')),
                    reverse=True)

    best = candidates[0]
    reason = f"MR !{best['iid']} " + ", ".join(best['_reasons'])
    return best['iid'], reason
```

**Main orchestrator:**
```python
def main():
    args = parse_args()
    project, issue_id = parse_issue_url(args.issue)
    project = project or args.project

    if not project:
        print("ERROR: Could not determine project. Use --project flag.", file=sys.stderr)
        sys.exit(2)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    fetch_log = FetchLog()

    # Step 1: Fetch issue metadata
    api = DrupalOrgAPI()
    raw_issue = fetch_log.track(lambda: api.get_issue(issue_id),
                                f"/api-d7/node/{issue_id}.json")
    issue = transform_issue(raw_issue, project)
    write_json(out_dir / 'issue.json', issue)

    # Step 2: Fetch all comments
    raw_comments = fetch_log.track(lambda: api.get_all_comments(issue_id),
                                   f"/api-d7/comment.json?node={issue_id}")
    comments = process_comments(raw_comments)
    write_json(out_dir / 'comments.json', {
        'issue_id': issue_id,
        'total_count': len(comments),
        'pages_fetched': (len(comments) // 44) + 1,
        'comments': comments,
    })

    # Step 3: Extract hidden branches from comments
    hidden_branches = extract_hidden_branches(comments)

    # Step 4: Search GitLab for MRs
    gl = GitLabAPI.from_token_file(args.gitlab_token_file) if args.gitlab_token_file else GitLabAPI()
    raw_mrs = fetch_log.track(lambda: gl.search_merge_requests(project, issue_id),
                              f"gitlab/merge_requests?search={issue_id}")

    # Step 5: Enrich each MR with detailed metadata
    mrs = []
    for raw_mr in raw_mrs:
        detail = fetch_log.track(
            lambda iid=raw_mr['iid']: gl.get_merge_request(project, iid),
            f"gitlab/merge_requests/{raw_mr['iid']}"
        )
        mrs.append(transform_mr(detail))

    # Step 6: Determine primary MR
    primary_iid, reason = determine_primary_mr(
        mrs, issue.get('version', ''), hidden_branches
    )
    for mr in mrs:
        mr['is_primary'] = (mr['iid'] == primary_iid)

    write_json(out_dir / 'merge-requests.json', {
        'issue_id': issue_id,
        'project': project,
        'merge_requests': mrs,
        'primary_selection_reason': reason,
    })

    # Step 7: Fetch diffs for open MRs
    for mr in mrs:
        if mr['state'] in ('opened', 'merged'):
            try:
                diff_text = fetch_log.track(
                    lambda iid=mr['iid']: gl.get_mr_plain_diff(project, iid),
                    f"gitlab/merge_requests/{mr['iid']}.diff"
                )
                diff_path = out_dir / f"mr-{mr['iid']}-diff.patch"
                diff_path.write_text(diff_text)
            except Exception as e:
                fetch_log.record_error(f"mr-{mr['iid']}-diff.patch", str(e))

    # Step 8: Fetch MR notes (if token available)
    if gl.token:
        for mr in mrs:
            if mr['state'] in ('opened', 'merged'):
                try:
                    notes = fetch_log.track(
                        lambda iid=mr['iid']: gl.get_mr_notes(project, iid),
                        f"gitlab/merge_requests/{mr['iid']}/notes"
                    )
                    write_json(out_dir / f"mr-{mr['iid']}-notes.json", notes)
                except Exception as e:
                    fetch_log.record_error(f"mr-{mr['iid']}-notes.json", str(e))

    # Step 9: Write fetch log
    fetch_log.finalize()
    write_json(out_dir / 'fetch-log.json', fetch_log.to_dict())

    # Determine exit code
    if fetch_log.has_errors():
        print(f"PARTIAL: {fetch_log.error_count()} errors. See fetch-log.json", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"COMPLETE: {fetch_log.request_count()} requests, 0 errors")
        sys.exit(0)
```

Include the `FetchLog` class, `transform_issue()`, `transform_mr()`, `extract_hidden_branches()`, `write_json()`, `parse_args()` helper functions. The complete file should be ~350-400 lines.

- [ ] **Step 2: Test against issue #3575190 (small, known)**

```bash
python3 skills/drupal-contribute-fix/scripts/fetch_issue.py \
  --issue https://www.drupal.org/project/ai/issues/3575190 \
  --out DRUPAL_ISSUES/3575190/artifacts \
  --gitlab-token-file git.drupalcode.org.key
```

Verify:
```bash
ls DRUPAL_ISSUES/3575190/artifacts/
# Should show: issue.json, comments.json, merge-requests.json, mr-1253-diff.patch, mr-1252-diff.patch, mr-1253-notes.json, mr-1252-notes.json, fetch-log.json
cat DRUPAL_ISSUES/3575190/artifacts/fetch-log.json | python3 -m json.tool | grep '"errors"'
# Should show: "errors": []
```

- [ ] **Step 3: Test against issue #3533079 (large, 109 comments)**

```bash
python3 skills/drupal-contribute-fix/scripts/fetch_issue.py \
  --issue https://www.drupal.org/project/canvas/issues/3533079 \
  --out DRUPAL_ISSUES/3533079/artifacts \
  --gitlab-token-file git.drupalcode.org.key
```

Verify:
```bash
python3 -c "
import json
with open('DRUPAL_ISSUES/3533079/artifacts/comments.json') as f:
    data = json.load(f)
print(f'Comments: {data[\"total_count\"]}')
assert data['total_count'] >= 100, 'Expected 100+ comments'
with open('DRUPAL_ISSUES/3533079/artifacts/merge-requests.json') as f:
    data = json.load(f)
print(f'MRs: {len(data[\"merge_requests\"])}')
print(f'Primary: !{data[\"merge_requests\"][0][\"iid\"]} (is_primary={data[\"merge_requests\"][0][\"is_primary\"]})')
print('PASS')
"
```

---

### Task 4: Create drupal-issue-fetcher agent definition

The Claude agent that runs the Python script, validates output, and retries on failure.

**Files:**
- Create: `.claude/agents/drupal-issue-fetcher.md`

- [ ] **Step 1: Create the agent definition**

Create `/home/alphons/project/freelygive/drupal/CONTRIB_WORKBENCH/.claude/agents/drupal-issue-fetcher.md`:

```markdown
---
model: sonnet
---

# Drupal Issue Fetcher

You fetch all data for a drupal.org issue and store it as structured artifacts.

## Inputs

You will be given:
- An issue URL or number (e.g., `https://www.drupal.org/project/ai/issues/3575190` or `3575190`)
- The output directory (e.g., `DRUPAL_ISSUES/3575190/artifacts`)

## Process

### Step 1: Run the fetch script

```bash
python3 /home/alphons/project/freelygive/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-contribute-fix/scripts/fetch_issue.py \
  --issue {ISSUE_URL_OR_ID} \
  --out {OUTPUT_DIR} \
  --gitlab-token-file /home/alphons/project/freelygive/drupal/CONTRIB_WORKBENCH/git.drupalcode.org.key
```

### Step 2: Validate completeness

Read `{OUTPUT_DIR}/fetch-log.json` and check:

1. **No errors**: `errors` array should be empty
2. **Comment count matches**: Read `issue.json` field `comment_count`, then check `comments.json` field `total_count`. They should match (within 1, since new comments may arrive between requests).
3. **MRs have diffs**: For each MR in `merge-requests.json` with `state: "opened"`, verify a corresponding `mr-{iid}-diff.patch` file exists.
4. **Notes fetched** (if token available): For each open MR, verify `mr-{iid}-notes.json` exists.

### Step 3: Handle failures

If validation fails:
- **Missing comments**: The script may have had a pagination issue. Re-run with just the issue URL.
- **Missing diffs**: Could be a GitLab rate limit. Wait 5 seconds, then fetch the specific diff manually:
  ```bash
  curl -s "https://git.drupalcode.org/project/{project}/-/merge_requests/{iid}.diff" > {OUTPUT_DIR}/mr-{iid}-diff.patch
  ```
- **Missing notes (401)**: Token may be invalid. Report PARTIAL without notes rather than failing.
- **Network errors**: Retry the full script once. If it fails again, report FAILED.

### Step 4: Write files.index

After all validation passes, write `{OUTPUT_DIR}/files.index` as JSON:

```json
{
  "issue_id": {nid},
  "project": "{project}",
  "fetched_at": "{ISO timestamp}",
  "status": "complete|partial",
  "files": [
    {"name": "issue.json", "type": "issue_metadata", "size_bytes": {n}, "fetched_at": "{ts}"},
    {"name": "comments.json", "type": "comment_thread", "comment_count": {n}, "pages_fetched": {n}, ...},
    ...
  ],
  "errors": []
}
```

Read each artifact file to get its size. Use the fetch-log.json timestamps.

### Step 5: Report

Report one of:
- **COMPLETE**: All artifacts fetched and validated. Include: comment count, MR count, primary MR IID.
- **PARTIAL**: Some artifacts missing. Include: what is missing and why.
- **FAILED**: Could not fetch issue data. Include: error details.
```

- [ ] **Step 2: Verify the agent file exists and has valid frontmatter**

```bash
head -5 /home/alphons/project/freelygive/drupal/CONTRIB_WORKBENCH/.claude/agents/drupal-issue-fetcher.md
```

---

### Task 5: Create drupal-ddev-setup agent definition

The agent that efficiently scaffolds DDEV environments using patterns learned from 12+ past sessions.

**Files:**
- Create: `.claude/agents/drupal-ddev-setup.md`

- [ ] **Step 1: Create the agent definition**

Create `/home/alphons/project/freelygive/drupal/CONTRIB_WORKBENCH/.claude/agents/drupal-ddev-setup.md`:

```markdown
---
model: sonnet
---

# Drupal DDEV Setup Agent

You set up a DDEV environment for a drupal.org issue. You have two modes.

## Inputs

You will be given:
- Issue ID
- Project name (e.g., `ai`, `canvas`)
- Module version from the issue (e.g., `1.3.x-dev`)
- Mode: `packagist` (install from composer) or `fork` (clone issue fork)
- If fork mode: the fork branch name and MR source branch

Read `DRUPAL_ISSUES/{issue_id}/artifacts/issue.json` and `merge-requests.json` for context if available.

## IRON LAWS

> **NEVER stop, kill, or tear down other DDEV projects.**

> **NEVER clone into the workspace root.** Always use `DRUPAL_ISSUES/{issue_id}/`.

> **NEVER guess version strings.** Use the rules below.

## Version String Rules

| Issue version field | Composer version string |
|---------------------|------------------------|
| `1.3.x` | `drupal/{module}:1.3.x-dev` |
| `1.3.x-dev` | `drupal/{module}:1.3.x-dev` |
| `2.0.x` | `drupal/{module}:2.0.x-dev` |
| `^1.2` | `drupal/{module}:^1.2` |

**Rule:** If the version ends with `.x` and does not already end with `-dev`, append `-dev`.

## Setup Sequence (Both Modes)

### Phase 1: Scaffold (always the same)

```bash
# 1. Create directory
ISSUE_DIR="DRUPAL_ISSUES/{issue_id}"
ENV_NAME="{project}"  # for packagist mode
# or ENV_NAME="{issue_fork_name}"  # for fork mode
mkdir -p "$ISSUE_DIR/$ENV_NAME"
cd "$ISSUE_DIR/$ENV_NAME"

# 2. Configure DDEV
ddev config --project-type=drupal --php-version=8.3 --docroot=web --project-name=d{issue_id}

# 3. Start containers
ddev start

# 4. Create Drupal
ddev composer create drupal/recommended-project:^11 --no-interaction
```

### Phase 2: Module Dependencies (BEFORE composer require)

Fetch the module's `composer.json` from GitLab to discover external PHP deps:
```bash
curl -s "https://git.drupalcode.org/project/{module}/-/raw/{branch}/composer.json"
```

Parse `require` and `require-dev` for non-drupal packages. Common ones:
- `openai-php/client` (AI module)
- `league/html-to-markdown` (AI module)
- `yethee/tiktoken` (AI module)
- `drupal/key` (many modules)
- `drupal/token` (many modules)

### Phase 3a: Packagist Mode

```bash
# Install module + ALL discovered deps in ONE command
ddev composer require drupal/{module}:{version} {drupal_deps} {external_deps} --no-interaction
```

### Phase 3b: Fork Mode

```bash
# Clone the issue fork into modules directory
git clone git@git.drupalcode.org:issue/{project}-{issue_id}.git web/modules/contrib/{module}
cd web/modules/contrib/{module}
git checkout {mr_source_branch}
cd ../../../..

# Install external dependencies the module needs
ddev composer require {external_deps} --no-interaction
```

### Phase 4: Install and Enable

```bash
# Install Drupal
ddev drush site:install --account-name=admin --account-pass=admin -y

# Enable module and submodules
ddev drush en {module} -y
```

### Phase 5: Test Dependencies (only if testing is needed)

```bash
# MUST use explicit version constraints
ddev composer require --dev "phpunit/phpunit:^11" "drupal/core-dev:^11" -W --no-interaction
```

## Error Handling

| Error | Diagnosis | Fix |
|-------|-----------|-----|
| `composer require` fails with version conflict | Wrong version string OR missing `-dev` suffix | Fix version string per rules above, retry once |
| `composer require` fails with missing package | External dep not on packagist | Check if it needs a custom repository or different package name |
| `ddev start` fails | Port conflict or Docker issue | Report FAILED, do NOT retry blindly |
| `drush en` fails with missing dependency | Module depends on another module not installed | Read error, `composer require` the missing module, retry `drush en` |
| `git clone` fails with permission denied | SSH key issue for git.drupal.org | Report FAILED with suggestion to check SSH config |

**Max retries per step: 1.** If a step fails twice, report FAILED with the error output.

## Report Format

**READY:**
```
READY: Environment at DRUPAL_ISSUES/{issue_id}/{env_name}/
- Drupal: {core_version}
- Module: {module} {version}
- DDEV: d{issue_id} (running)
- URL: https://d{issue_id}.ddev.site
- Login: ddev drush uli
```

**FAILED:**
```
FAILED: Could not set up environment.
- Step failed: {step_name}
- Error: {error_output}
- Suggestion: {what_to_try}
```
```

- [ ] **Step 2: Verify the agent file exists**

```bash
head -5 /home/alphons/project/freelygive/drupal/CONTRIB_WORKBENCH/.claude/agents/drupal-ddev-setup.md
```

---

### Task 6: Update drupal-issue skill to dispatch fetcher

Modify the `/drupal-issue` skill to dispatch the fetcher agent first, then read artifacts instead of using the browser.

**Files:**
- Modify: `skills/drupal-issue/SKILL.md`

- [ ] **Step 1: Read the current SKILL.md**

Read `skills/drupal-issue/SKILL.md` fully. Identify the "Step 1: Read the issue" section.

- [ ] **Step 2: Add fetcher dispatch before Step 1**

After the "Before You Begin" section and before "## Step 1: Read the issue", insert a new section:

```markdown
## Step 0: Fetch issue data

Before reading anything, dispatch the `drupal-issue-fetcher` agent to pull all issue data via APIs:

1. Parse the issue URL to extract project name and issue ID
2. Dispatch the `drupal-issue-fetcher` agent with:
   - Issue URL or ID
   - Output directory: `DRUPAL_ISSUES/{issue_id}/artifacts`
3. Wait for the agent to report COMPLETE, PARTIAL, or FAILED
4. If COMPLETE: proceed to Step 1 using artifacts
5. If PARTIAL: proceed with available data, note gaps
6. If FAILED: fall back to browser-based reading (original approach)

The artifacts are at `DRUPAL_ISSUES/{issue_id}/artifacts/`:
- `issue.json` for metadata (title, status, version, component, author, etc.)
- `comments.json` for the complete comment thread
- `merge-requests.json` for all MRs with the primary MR flagged
- `mr-{iid}-diff.patch` for MR diffs
- `mr-{iid}-notes.json` for GitLab review threads
```

- [ ] **Step 3: Update Step 1 to reference artifacts**

In the existing "Step 1: Read the issue" section, update the "What to read" list to reference artifacts instead of browser reading. Keep the browser as a fallback. Add a note:

```markdown
**When artifacts are available** (Step 0 succeeded):
- Read `artifacts/issue.json` for sidebar metadata
- Read `artifacts/comments.json` for the full comment thread (already numbered and chronological)
- Read `artifacts/merge-requests.json` for MR details and the primary MR flag
- Read `artifacts/mr-{iid}-diff.patch` for MR diffs
- Use the browser ONLY for: viewing screenshots, visual verification, or when artifacts are incomplete

**When artifacts are NOT available** (Step 0 failed):
- Fall back to the original browser-based approach below
```

- [ ] **Step 4: Verify no broken references**

```bash
grep -c "drupal-issue-fetcher" skills/drupal-issue/SKILL.md  # should be >= 1
grep -c "artifacts" skills/drupal-issue/SKILL.md  # should be >= 3
```

---

### Task 7: Update drupal-issue-review skill to use artifacts and delegate DDEV

Modify the `/drupal-issue-review` skill to read artifacts for context (instead of re-reading the issue) and delegate DDEV setup to the new agent.

**Files:**
- Modify: `skills/drupal-issue-review/SKILL.md`

- [ ] **Step 1: Read the current SKILL.md**

Read `skills/drupal-issue-review/SKILL.md` fully. Identify the environment scaffolding section.

- [ ] **Step 2: Add artifact reading at the start**

After the "Before You Begin" section, add:

```markdown
## Using Fetched Artifacts

If `DRUPAL_ISSUES/{issue_id}/artifacts/` exists (populated by `drupal-issue-fetcher`), read:
- `issue.json` for version, project, component
- `merge-requests.json` for MR branches and the primary MR
- `comments.json` for reproduction steps (search for "steps to reproduce" in comment bodies)

This replaces the need to re-read the issue from the browser. The answers to the "Before You Begin" questions should come from these artifacts.
```

- [ ] **Step 3: Update DDEV setup to delegate to agent**

Find the section where DDEV is configured (the `ddev config`, `ddev start`, `ddev composer create` sequence). Add a note before it:

```markdown
### Environment Setup

Dispatch the `drupal-ddev-setup` agent with:
- Issue ID: from artifacts
- Project: from `issue.json` field `project`
- Version: from `issue.json` field `version`
- Mode: `fork` if we need to fix code, `packagist` if just reproducing
- Fork branch: from `merge-requests.json` primary MR's `source_branch` (if fork mode)

Wait for the agent to report READY or FAILED. If READY, proceed with reproduction. If FAILED, review the error and either fix manually or ask the user.

The manual setup steps below are the FALLBACK if the agent is unavailable or fails.
```

- [ ] **Step 4: Verify**

```bash
grep -c "drupal-ddev-setup" skills/drupal-issue-review/SKILL.md  # should be >= 1
grep -c "artifacts" skills/drupal-issue-review/SKILL.md  # should be >= 2
```

---

### Task 8: End-to-end verification

Test the complete flow with a real issue.

**Files:**
- No files created or modified

- [ ] **Step 1: Clean test with issue #3575190**

```bash
rm -rf DRUPAL_ISSUES/3575190/artifacts
python3 skills/drupal-contribute-fix/scripts/fetch_issue.py \
  --issue https://www.drupal.org/project/ai/issues/3575190 \
  --out DRUPAL_ISSUES/3575190/artifacts \
  --gitlab-token-file git.drupalcode.org.key
echo "Exit code: $?"
```
Expected: Exit code 0

- [ ] **Step 2: Validate all artifacts present**

```bash
for f in issue.json comments.json merge-requests.json fetch-log.json; do
  echo -n "$f: "
  test -f "DRUPAL_ISSUES/3575190/artifacts/$f" && echo "OK" || echo "MISSING"
done

# Check for MR diffs
ls DRUPAL_ISSUES/3575190/artifacts/mr-*-diff.patch 2>/dev/null || echo "No diff patches found"

# Check for MR notes
ls DRUPAL_ISSUES/3575190/artifacts/mr-*-notes.json 2>/dev/null || echo "No MR notes found"
```

- [ ] **Step 3: Validate content correctness**

```bash
python3 -c "
import json

# Check issue metadata
with open('DRUPAL_ISSUES/3575190/artifacts/issue.json') as f:
    issue = json.load(f)
assert issue['project'] == 'ai', f'Wrong project: {issue[\"project\"]}'
assert issue['status']['code'] == 8, f'Wrong status: {issue[\"status\"]}'
print(f'Issue: {issue[\"title\"]}')

# Check comments
with open('DRUPAL_ISSUES/3575190/artifacts/comments.json') as f:
    comments = json.load(f)
print(f'Comments: {comments[\"total_count\"]}')

# Check MRs
with open('DRUPAL_ISSUES/3575190/artifacts/merge-requests.json') as f:
    mrs = json.load(f)
primary = [mr for mr in mrs['merge_requests'] if mr['is_primary']]
print(f'MRs: {len(mrs[\"merge_requests\"])}, Primary: !{primary[0][\"iid\"] if primary else \"none\"}')
print(f'Primary reason: {mrs[\"primary_selection_reason\"]}')

# Check fetch log
with open('DRUPAL_ISSUES/3575190/artifacts/fetch-log.json') as f:
    log = json.load(f)
print(f'Requests: {log[\"total_requests\"]}, Errors: {len(log[\"errors\"])}')

print('ALL CHECKS PASSED')
"
```

- [ ] **Step 4: Stress test with large issue #3533079**

```bash
rm -rf DRUPAL_ISSUES/3533079/artifacts
python3 skills/drupal-contribute-fix/scripts/fetch_issue.py \
  --issue https://www.drupal.org/project/canvas/issues/3533079 \
  --out DRUPAL_ISSUES/3533079/artifacts \
  --gitlab-token-file git.drupalcode.org.key
echo "Exit code: $?"

python3 -c "
import json
with open('DRUPAL_ISSUES/3533079/artifacts/comments.json') as f:
    data = json.load(f)
print(f'Comments: {data[\"total_count\"]}')
assert data['total_count'] >= 100, f'Expected 100+, got {data[\"total_count\"]}'
print('LARGE ISSUE TEST PASSED')
"
```

- [ ] **Step 5: Verify all agent definitions have valid frontmatter**

```bash
for agent in drupal-issue-fetcher.md drupal-ddev-setup.md; do
  echo -n "$agent: "
  head -3 "/home/alphons/project/freelygive/drupal/CONTRIB_WORKBENCH/.claude/agents/$agent" | grep -q "model:" && echo "OK" || echo "MISSING FRONTMATTER"
done
```

- [ ] **Step 6: Verify skill updates reference agents correctly**

```bash
grep -c "drupal-issue-fetcher" skills/drupal-issue/SKILL.md
grep -c "drupal-ddev-setup" skills/drupal-issue-review/SKILL.md
# Both should be >= 1
```
