# Issue Fetcher + DDEV Setup Agents Design Spec

**Date:** 2026-03-23
**Author:** ajv009 + Claude
**Status:** Approved

## Problem

The `/drupal-issue` skill currently reads issues by scrolling a browser window and taking screenshots. For large issues (100+ comments, multiple MRs, long review threads), this is slow, unreliable, and burns tokens on mechanical data retrieval. DDEV environment setup also wastes time on trial-and-error (wrong version strings, missing dependencies, phpunit conflicts).

## Solution

Two new agents that split the mechanical work from the intelligent work:

1. **`drupal-issue-fetcher`**: Python script fetches all issue data via APIs, Claude agent validates completeness and retries failures.
2. **`drupal-ddev-setup`**: Efficiently scaffolds DDEV environments using learned patterns from past sessions.

## Agent 1: drupal-issue-fetcher

### Purpose

Programmatically fetch ALL data for a drupal.org issue and store it as structured artifacts. Zero browser interaction. ~7-9 API calls instead of 10+ minutes of scrolling.

### Data Sources

| Data | Source | Auth Required | Endpoint |
|------|--------|---------------|----------|
| Issue metadata | d.o REST API | No | `/api-d7/node/{nid}.json` |
| All comments | d.o REST API | No | `/api-d7/comment.json?node={nid}&page={n}` (~44/page) |
| MR search | GitLab API | No | `/api/v4/projects/project%2F{name}/merge_requests?search={nid}&state=all` |
| MR metadata | GitLab API | No | `/api/v4/projects/.../merge_requests/{iid}` |
| MR diffs | GitLab API | No | `/api/v4/projects/.../merge_requests/{iid}/diffs?per_page=100` |
| MR plain diff | GitLab | No | `/project/{name}/-/merge_requests/{iid}.diff` |
| MR notes | GitLab API | Yes (token) | `/api/v4/projects/.../merge_requests/{iid}/notes?per_page=100` |

### Tokens

- **d.o API**: No auth needed. Rate limit: 1 req/sec (self-imposed). Cache: 15 min server-side.
- **GitLab API**: Token at `/home/alphons/project/freelygive/drupal/CONTRIB_WORKBENCH/git.drupalcode.org.key`. Rate limit: 180 req/period (unauthenticated), higher with token. Token enables MR notes access.

### Architecture

**Python script** (`scripts/fetch_issue.py`):
- Takes: issue URL or number, project name (auto-detected from URL)
- Uses existing `drupalorg_api.py` for d.o calls (enhanced with comment pagination)
- Uses `urllib` for GitLab API calls (no external deps, consistent with existing code)
- Writes raw JSON/patch files to `DRUPAL_ISSUES/{issue_id}/artifacts/`
- Exits with status codes indicating completeness

**Claude agent** (`agents/issue-fetcher.md`):
- Dispatched by `/drupal-issue` skill before any analysis
- Runs the Python script
- Reads `fetch-log.json` to check for failures
- If failures: diagnoses the problem, adjusts parameters, re-runs specific fetches
- Validates: comment count matches `comment_count` from issue node, MRs found, diffs downloaded
- Writes `files.index` after all validation passes

### Artifact Structure

```
DRUPAL_ISSUES/{issue_id}/
  artifacts/
    files.index             # Manifest of all artifacts
    issue.json              # Core issue metadata
    comments.json           # Complete comment thread
    merge-requests.json     # All MRs with heuristic signals
    mr-{iid}-diff.patch     # Raw diff per open/active MR
    mr-{iid}-notes.json     # GitLab threads per MR (if token available)
    fetch-log.json          # Fetch audit trail
  issue-comment-{id}.html   # Drafted comment (from /drupal-issue-comment)
  {issue_fork_name}/        # DDEV environment (from drupal-ddev-setup)
```

### Artifact Schemas

#### files.index
```json
{
  "issue_id": 3575190,
  "project": "ai",
  "fetched_at": "2026-03-23T12:00:00Z",
  "status": "complete",
  "files": [
    {
      "name": "issue.json",
      "type": "issue_metadata",
      "size_bytes": 4523,
      "fetched_at": "2026-03-23T12:00:01Z"
    },
    {
      "name": "comments.json",
      "type": "comment_thread",
      "size_bytes": 125000,
      "comment_count": 109,
      "pages_fetched": 3,
      "fetched_at": "2026-03-23T12:00:04Z"
    },
    {
      "name": "merge-requests.json",
      "type": "merge_requests",
      "mr_count": 2,
      "primary_mr_iid": 1253,
      "fetched_at": "2026-03-23T12:00:05Z"
    },
    {
      "name": "mr-1253-diff.patch",
      "type": "mr_diff",
      "mr_iid": 1253,
      "size_bytes": 8200,
      "fetched_at": "2026-03-23T12:00:06Z"
    },
    {
      "name": "mr-1253-notes.json",
      "type": "mr_notes",
      "mr_iid": 1253,
      "note_count": 12,
      "fetched_at": "2026-03-23T12:00:07Z"
    }
  ],
  "errors": []
}
```

#### issue.json
```json
{
  "nid": 3575190,
  "title": "Only one AI Automator worker queue item is processed per cron execution",
  "url": "https://www.drupal.org/project/ai/issues/3575190",
  "project": "ai",
  "status": {"code": 8, "label": "Needs review"},
  "priority": {"code": 200, "label": "Normal"},
  "category": {"code": 1, "label": "Bug report"},
  "component": "AI Automators",
  "version": "1.3.x-dev",
  "author": {"uid": 12345, "name": "sgavilan"},
  "assigned": {"uid": 67890, "name": "ajv009"},
  "created": "2026-02-23T10:00:00Z",
  "changed": "2026-03-23T06:00:00Z",
  "comment_count": 8,
  "body_html": "<p>Each cron execution queues several items...</p>",
  "related_issues": [],
  "parent_issue": null,
  "tags": ["AI Initiative Sprint", "AI Innovation"],
  "files": []
}
```

#### comments.json
```json
{
  "issue_id": 3575190,
  "total_count": 8,
  "pages_fetched": 1,
  "comments": [
    {
      "number": 1,
      "cid": "16487000",
      "author": {"uid": 12345, "name": "sgavilan"},
      "created": "2026-02-23T10:00:00Z",
      "body_html": "<p>sgavilan created an issue...</p>",
      "is_system_message": false,
      "mr_references": []
    },
    {
      "number": 4,
      "cid": "16488271",
      "author": {"uid": 0, "name": "System Message"},
      "created": "2026-02-26T19:22:00Z",
      "body_html": "<p>jorgik opened <a href=\"...\">merge request !1252</a></p>",
      "is_system_message": true,
      "mr_references": [{"iid": 1252, "url": "https://git.drupalcode.org/project/ai/-/merge_requests/1252"}]
    }
  ]
}
```

#### merge-requests.json
```json
{
  "issue_id": 3575190,
  "project": "ai",
  "merge_requests": [
    {
      "iid": 1253,
      "title": "Issue #3575190: Add configurable queue items per cron for AI Automators",
      "state": "opened",
      "author": "jorgik",
      "source_branch": "3575190-configurable-queue-items-per-cron-1.3.x",
      "target_branch": "1.3.x",
      "created_at": "2026-02-26T19:31:48Z",
      "updated_at": "2026-03-23T06:00:17Z",
      "user_notes_count": 0,
      "has_conflicts": false,
      "merge_status": "can_be_merged",
      "draft": false,
      "pipeline_status": "failed",
      "changes_count": 10,
      "web_url": "https://git.drupalcode.org/project/ai/-/merge_requests/1253",
      "heuristics": {
        "version_match": true,
        "is_most_recent": true,
        "has_activity": true,
        "branch_visible": true
      },
      "is_primary": true
    },
    {
      "iid": 1252,
      "title": "Issue #3575190: Add configurable queue items per cron for AI Automators",
      "state": "opened",
      "author": "jorgik",
      "source_branch": "3575190-configurable-queue-items-per-cron",
      "target_branch": "1.2.x",
      "created_at": "2026-02-26T19:22:33Z",
      "updated_at": "2026-02-26T19:27:15Z",
      "user_notes_count": 0,
      "has_conflicts": false,
      "merge_status": "unchecked",
      "draft": false,
      "pipeline_status": "failed",
      "changes_count": 8,
      "web_url": "https://git.drupalcode.org/project/ai/-/merge_requests/1252",
      "heuristics": {
        "version_match": false,
        "is_most_recent": false,
        "has_activity": false,
        "branch_visible": true
      },
      "is_primary": false
    }
  ],
  "primary_selection_reason": "MR !1253 targets 1.3.x which matches issue version 1.3.x-dev, and was most recently updated"
}
```

#### fetch-log.json
```json
{
  "started_at": "2026-03-23T12:00:00Z",
  "completed_at": "2026-03-23T12:00:08Z",
  "total_requests": 7,
  "requests": [
    {"url": "/api-d7/node/3575190.json", "status": 200, "duration_ms": 450, "cached": false},
    {"url": "/api-d7/comment.json?node=3575190&page=0", "status": 200, "duration_ms": 380, "cached": false},
    {"url": "...gitlab.../merge_requests?search=3575190", "status": 200, "duration_ms": 520, "cached": false}
  ],
  "errors": [],
  "retries": []
}
```

### Primary MR Heuristic

When multiple MRs exist, determine which is primary using these signals in priority order:

1. **State filter**: Exclude `closed` and `merged` (unless all are closed/merged, then pick the merged one)
2. **Version match**: Issue `field_issue_version` (strip `-dev`) matches MR `target_branch`
3. **Most recently updated**: Compare `updated_at` timestamps
4. **Activity level**: Higher `user_notes_count` indicates more review activity
5. **Branch visibility**: Check d.o comments for "changed visibility to hidden" (hidden = abandoned)

### Python Script Design

**Location:** `skills/drupal-contribute-fix/scripts/fetch_issue.py`

**Dependencies:** stdlib only (urllib, json, os, pathlib, time). Reuses existing `drupalorg_api.py` patterns.

**CLI:**
```bash
python3 fetch_issue.py \
  --issue 3575190 \
  --project ai \
  --out DRUPAL_ISSUES/3575190/artifacts \
  --gitlab-token-file git.drupalcode.org.key
```

**Exit codes:**
- 0: All artifacts fetched successfully
- 1: Partial fetch (some artifacts missing, see fetch-log.json)
- 2: Fatal error (issue not found, network failure)

**Enhancements to existing drupalorg_api.py:**
- `get_comments()` must paginate (currently only fetches page 0)
- Add `get_all_comments(issue_nid)` that follows `next` links until exhausted
- Add comment numbering (sequential, matching d.o display)

### Agent Definition

**Location:** `.claude/agents/drupal-issue-fetcher.md`

**Model:** sonnet (mechanical validation work, no complex reasoning needed)

**Responsibilities:**
1. Run `fetch_issue.py` with correct arguments
2. Read `fetch-log.json` and validate:
   - Comment count in `comments.json` matches `comment_count` from `issue.json`
   - All open MRs have corresponding `mr-{iid}-diff.patch` files
   - If GitLab token available, all MRs have `mr-{iid}-notes.json`
   - No HTTP errors in fetch log
3. If validation fails: diagnose, fix parameters, re-run specific fetches
4. Write `files.index` after all validation passes
5. Report status: COMPLETE | PARTIAL (with what's missing) | FAILED (with error)

---

## Agent 2: drupal-ddev-setup

### Purpose

Efficiently scaffold a DDEV environment for a drupal.org issue. Uses learned patterns from 12+ past sessions to avoid common pitfalls (wrong version strings, missing dependencies, phpunit conflicts).

### Two Modes

**Mode 1: Packagist install** (for reproducing/testing)
```
DRUPAL_ISSUES/{issue_id}/{project}/
  .ddev/
  web/modules/contrib/{module}/  (installed via composer)
```

**Mode 2: Issue fork clone** (for contributing fixes)
```
DRUPAL_ISSUES/{issue_id}/{issue_fork_name}/
  .ddev/
  web/modules/contrib/{module}/  (cloned fork, set as local path)
```

### Agent Definition

**Location:** `.claude/agents/drupal-ddev-setup.md`

**Model:** sonnet

**Inputs (from artifacts):**
- `issue.json`: version, project name
- `merge-requests.json`: fork branch name, target branch
- User choice: mode 1 or mode 2

### Learned Setup Sequence (Optimized)

```bash
# 1. Directory and DDEV config (5 sec)
mkdir -p DRUPAL_ISSUES/{issue_id}/{env_name}
cd DRUPAL_ISSUES/{issue_id}/{env_name}
ddev config --project-type=drupal --php-version=8.3 --docroot=web --project-name=d{issue_id}

# 2. Start containers (30 sec)
ddev start

# 3. Create Drupal project (15 sec)
ddev composer create drupal/recommended-project:^11 --no-interaction

# 4. Read module's composer.json for external deps BEFORE requiring
#    (prevents the "missing openai-php/client" loop)
#    Fetch: https://git.drupalcode.org/project/{module}/-/raw/{branch}/composer.json

# 5. Install module + ALL dependencies in ONE command (20 sec)
ddev composer require drupal/{module}:{version}-dev {external_deps} --no-interaction

# 6. Install Drupal (10 sec)
ddev drush site:install --account-name=admin --account-pass=admin -y

# 7. Enable modules (5 sec)
ddev drush en {module} {sub_modules} -y

# 8. For testing: add dev deps with explicit versions (30 sec)
ddev composer require --dev "phpunit/phpunit:^11" "drupal/core-dev:^11" -W --no-interaction
```

### Version String Rules (Learned from Past Failures)

| Issue says | Use in composer |
|-----------|----------------|
| `1.3.x` | `drupal/{module}:1.3.x-dev` |
| `1.3.x-dev` | `drupal/{module}:1.3.x-dev` |
| `2.0.x` | `drupal/{module}:2.0.x-dev` |
| `^1.2` | `drupal/{module}:^1.2` |

### Module Dependency Pre-fetch

Before `composer require`, fetch the module's own `composer.json` from GitLab to discover external PHP deps:
```
https://git.drupalcode.org/project/{module}/-/raw/{branch}/composer.json
```

Parse `require` section for non-drupal packages (openai-php/client, league/html-to-markdown, yethee/tiktoken, etc.) and include them in the single `composer require` command.

### Issue Fork Setup (Mode 2)

```bash
# Clone the issue fork
git clone git@git.drupalcode.org:issue/{project}-{issue_id}.git web/modules/contrib/{module}
cd web/modules/contrib/{module}
git checkout {mr_source_branch}

# Composer can't autoload from a git clone without path repository
# Add as path repository in composer.json OR just install deps directly
cd ../../..
ddev composer require {external_deps_from_module_composer_json} --no-interaction
```

### Safeguards

- NEVER stop/kill other DDEV instances
- NEVER clone into the workspace root
- Project name: `d{issue_id}` (consistent, short, no conflicts)
- If DDEV start fails: report error, do NOT retry blindly
- If composer require fails: read error output, diagnose (version conflict? missing dep?), fix once, retry once

### Agent Report Format

```
READY: Environment at DRUPAL_ISSUES/{issue_id}/{env_name}/
- Drupal: 11.3.x
- Module: {module} {version}
- DDEV: d{issue_id} (running)
- URL: https://d{issue_id}.ddev.site
- Login: ddev drush uli

FAILED: Could not set up environment.
- Step failed: {which step}
- Error: {error output}
- Suggestion: {what the user could try}
```

---

## Integration with Existing Skills

### Updated /drupal-issue flow

```
1. User: /drupal-issue <url>
2. drupal-issue skill activates, announces itself
3. Parse issue ID and project from URL
4. Dispatch drupal-issue-fetcher agent
   -> Writes artifacts/ with all data
   -> Reports COMPLETE/PARTIAL/FAILED
5. Read artifacts/files.index to confirm data available
6. Read artifacts/issue.json + comments.json + merge-requests.json
7. Classify action (categories A through I, using Before You Begin gate)
8. If action needs environment:
   -> Dispatch drupal-ddev-setup agent with mode choice
   -> Agent reports READY/FAILED
9. Continue with existing skill chain (fix, test, comment, push gate)
```

### What Changes in Existing Skills

| Skill | Change |
|-------|--------|
| `/drupal-issue` | Dispatch fetcher first, read artifacts instead of browser |
| `/drupal-issue-review` | Use artifacts for issue context, only use browser for screenshots |
| `/drupal-contribute-fix` | Read artifacts for issue context instead of re-reading the issue |
| `/drupal-issue-comment` | Reference artifacts for accurate comment details |

### What Stays the Same

- Browser still used for: screenshots, visual verification, posting comments
- All existing governance patterns (iron laws, handoffs, question gates)
- The entire fix/test/review/push workflow
- Comment drafting skill
- Agent prompt templates for reviewer/verifier

---

## File Locations Summary

```
.claude/agents/
  drupal-issue-fetcher.md       # Agent definition
  drupal-ddev-setup.md          # Agent definition

skills/drupal-contribute-fix/
  scripts/fetch_issue.py        # Python fetcher script
  lib/drupalorg_api.py          # Enhanced with comment pagination

DRUPAL_ISSUES/{issue_id}/
  artifacts/                    # All fetched data
  issue-comment-{id}.html      # Drafted comment
  {env_name}/                   # DDEV environment
```
