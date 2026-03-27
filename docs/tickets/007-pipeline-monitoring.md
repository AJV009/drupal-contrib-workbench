# TICKET-007: Post-Push GitLab CI Pipeline Monitoring

**Status:** COMPLETED
**Priority:** P2 (Medium)
**Affects:** New skill or agent
**Type:** New Feature

## Problem

In the #3579478 session, after pushing to MR !20, the session simply ended. There was no monitoring of whether the GitLab CI pipeline passed or failed. If the pipeline fails, the user won't know until they manually check the MR page.

This is a gap in the workflow. The fix may pass locally but fail in CI due to:
- Different PHP version
- Different database engine (SQLite locally, MySQL/PostgreSQL in CI)
- Missing test dependencies
- PHPCS/PHPStan version differences
- Drupal core version matrix testing

## Current Behavior

```
Push to MR -> Session ends -> User manually checks CI
```

## Desired Behavior

```
Push to MR -> Monitor pipeline -> Report results:
  - If PASS: "Pipeline passed. MR is ready for review."
  - If FAIL: Fetch logs, diagnose, suggest fix or auto-fix
```

## Implementation Options

### Option A: Post-Push Polling Agent (Recommended)

Create a new `drupal-pipeline-watch` agent that:

1. Takes MR URL and project info as input
2. Polls GitLab CI API every 60 seconds
3. Reports when pipeline completes
4. On failure: fetches job logs, identifies the failing step

```markdown
# drupal-pipeline-watch agent

## Input
- Project: ai_provider_litellm
- MR IID: 20
- GitLab token file: git.drupalcode.org.key

## Process
1. Poll: GET /api/v4/projects/{id}/merge_requests/{iid}/pipelines
2. Check status: pending | running | success | failed | canceled
3. If running: wait 60 seconds, poll again (max 15 minutes)
4. If success: report PIPELINE_PASSED
5. If failed:
   a. GET /api/v4/projects/{id}/pipelines/{pipeline_id}/jobs
   b. Find failed jobs
   c. GET /api/v4/projects/{id}/jobs/{job_id}/trace (log output)
   d. Extract error from log
   e. Report PIPELINE_FAILED with diagnosis

## Output
PIPELINE_PASSED:
  - Pipeline #12345: success
  - Jobs: phpunit (pass), phpcs (pass), phpstan (pass)
  - Duration: 3m 45s
  - MR ready for review

PIPELINE_FAILED:
  - Pipeline #12345: failed
  - Failed job: phpunit (PHP 8.2 + MySQL)
  - Error: "Call to undefined method ..."
  - Diagnosis: Method doesn't exist in Drupal 10.3, only 11.x
  - Suggestion: Add version check or use interface method
```

### Option B: Integrate Into Push Gate

Instead of a separate agent, add pipeline monitoring as the final step of the push gate in `drupal-contribute-fix`:

```markdown
After push is confirmed and executed:
1. Extract pipeline URL from git push output
2. Poll pipeline status every 60 seconds
3. When complete, append results to the session
```

This is simpler but ties the main session to a potentially 10+ minute wait.

### Option C: Background Agent + Notification

Best of both worlds:
1. Push happens
2. Dispatch pipeline-watch agent in background
3. Main session presents summary and closes
4. Agent monitors pipeline and notifies when done

The user gets immediate feedback that push succeeded, and a follow-up notification about CI status.

## Recommended: Option C

Option C is best because:
- User isn't blocked waiting for CI
- Pipeline failures get diagnosed automatically
- Main session context isn't consumed by polling

## Implementation Plan

### 1. Create `drupal-pipeline-watch` agent

New file: `.claude/agents/drupal-pipeline-watch.md`

```markdown
---
model: haiku  # lightweight, just polling and log reading
tools: [Bash, Read, Grep]
---

# Pipeline Watch Agent

Monitor a GitLab CI pipeline and report results.

## Input
- project_path: e.g., "project/ai_provider_litellm"
- mr_iid: e.g., 20
- gitlab_token_file: path to token file

## Process
[polling loop with API calls]

## Output
[structured report]
```

### 2. Add pipeline monitoring to push gate in `drupal-contribute-fix`

After push succeeds:
```markdown
After successful push:
1. Dispatch drupal-pipeline-watch agent in background
2. Tell user: "Push complete. Pipeline monitoring agent dispatched.
   You'll be notified when CI completes."
```

### 3. Add the API script

Create `scripts/watch_pipeline.py` that handles the polling logic, since shell-based polling with `sleep` and `curl` in a loop is fragile.

## Acceptance Criteria

- [ ] Pipeline is monitored after every push
- [ ] Pipeline pass/fail is reported to user
- [ ] Failed pipelines include: failing job name, error extract, diagnosis
- [ ] User is not blocked waiting for pipeline
- [ ] Polling respects rate limits (max 1 request per 60 seconds)
- [ ] Monitoring times out after 15 minutes with a "still running" message

## Files to Create/Modify

1. `.claude/agents/drupal-pipeline-watch.md` - NEW agent definition
2. `.claude/skills/drupal-contribute-fix/SKILL.md` - Add post-push pipeline dispatch
3. `.claude/skills/drupal-contribute-fix/scripts/watch_pipeline.py` - NEW polling script (optional)
