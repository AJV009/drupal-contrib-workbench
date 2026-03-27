---
name: drupal-issue-review
description: >
  Full workflow for reviewing/reproducing a drupal.org issue. Invoke with
  `/drupal-issue-review <issue-url-or-number>`. Reads the issue, determines
  required Drupal core + module versions, scaffolds a fresh environment, reproduces the bug, and
  optionally drafts a comment. Companion to drupal-contribute-fix (which
  handles the actual fix + MR packaging).
license: GPL-2.0-or-later
metadata:
  author: ajv009
  version: "1.0.0"
---

# drupal-issue-review

End-to-end workflow: read a drupal.org issue, set up a matching environment, reproduce, and comment.

Invoke: `/drupal-issue-review <issue-url-or-number>`

> **IRON LAW:** NO ENVIRONMENT SETUP WITHOUT CLEAR REPRODUCTION STEPS. If the issue doesn't have clear steps, read comments until you find them or ask the user.

> **IRON LAW (VERIFICATION):** NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE. Don't say "reproduced" without showing the error. Don't say "verified" without test output.

## Hands-Free Operation (CRITICAL)

This skill runs hands-free. Do NOT stop between phases to ask the user what to do.

- After DDEV setup completes: immediately proceed to reproduction/testing.
- After reproduction/testing: immediately proceed to the next appropriate action:
  - Issues found that need code fixes -> auto-invoke `/drupal-contribute-fix`
  - MR verified and working -> auto-invoke `/drupal-issue-comment` to draft confirming comment
  - Bug reproduced, no fix needed yet -> auto-invoke `/drupal-issue-comment` to draft findings
- The ONLY stop point is the push gate in `/drupal-contribute-fix` or presenting the draft comment.

## Before You Begin

Before scaffolding a DDEV environment, answer these questions internally:
1. What Drupal core version does this issue target?
2. What module version/branch is needed?
3. Are there specific contrib modules that need to be installed?
4. Are there existing MRs I should apply to test with/without the fix?
5. Does the issue have concrete reproduction steps, or do I need to derive them?
6. Is there already a DDEV environment for this issue number in DRUPAL_ISSUES/?

If answers are unclear, go re-read the issue. Do NOT start `ddev config` until you can answer all 6.

## Using Fetched Artifacts

If `DRUPAL_ISSUES/{issue_id}/artifacts/` exists (populated by `drupal-issue-fetcher`), read:
- `issue.json` for version, project, component, status
- `merge-requests.json` for MR branches, primary MR, fork details
- `comments.json` for reproduction steps (search comment bodies for "steps to reproduce" or numbered lists)

This replaces the need to re-read the issue from the browser. The answers to the "Before You Begin" questions should come from these artifacts.

## Overview

```
Issue URL/number
      │
      ▼
 ┌─────────────┐
 │ 1. READ     │  Read the issue page (browser or web fetch)
 │    ISSUE    │  Extract: versions, modules, steps to reproduce
 └──────┬──────┘
        ▼
 ┌─────────────┐
 │ 2. SCAFFOLD │  Create DRUPAL_ISSUES/{issue_id}/
 │    DDEV ENV │  ddev config + composer create-project + drush si
 └──────┬──────┘
        ▼
 ┌─────────────┐
 │ 3. INSTALL  │  composer require + drush en for each module
 │    MODULES  │  at the exact versions from the issue
 └──────┬──────┘
        ▼
 ┌─────────────┐
 │ 4. REPRODUCE│  Follow the issue's steps to reproduce
 │    THE BUG  │  Take screenshots with Playwright
 └──────┬──────┘
        ▼
 ┌─────────────┐
 │ 5. COMMENT  │  Draft a d.o comment (uses /drupal-issue-comment)
 │    (opt)    │
 └─────────────┘
```

## Step 1: Read the Issue

Accept either format:
- `https://www.drupal.org/project/{project}/issues/{id}`
- Just the number: `3561693`

Normalize to the full URL. Read the issue page using the browser (Claude Chrome)
or WebFetch. **Read carefully** — don't skim. Pay attention to:

### What to extract

| Field | Where to find it | Example |
|-------|-------------------|---------|
| **Issue ID** | URL | `3561693` |
| **Project** | Breadcrumb / sidebar | `ai` |
| **Version** | Sidebar "Version" field | `1.2.x-dev` |
| **Component** | Sidebar | `AI Automators` |
| **Status** | Sidebar | `Needs work` |
| **Modules to enable** | Steps to reproduce | `ai_automators`, `canvas` |
| **Module versions** | Comments, description | `drupal/ai:1.2.x-dev`, `drupal/canvas` |
| **Drupal core version** | Usually implied by module version; check comments | `^11` |
| **Steps to reproduce** | Issue body or comments | numbered list |
| **Existing MRs** | Issue fork section | `!1288` on `1.2.x` |
| **Related issues** | Comments, linked issues | `[#3558728]` |

### Reading comments

Don't just read the issue body. **Read every comment**, especially:
- The latest comments (why was it reopened? what failed?)
- Any comments with screenshots or videos (view them)
- MR descriptions and code diffs
- Status changes (who moved it to Needs work and why?)

### Version detection heuristics

If the issue doesn't explicitly state versions:
- Check the **Version** field in the sidebar
- Look at `composer require` commands in comments
- Check MR target branches (`1.2.x`, `2.0.x`)
- If ambiguous, use the version from the sidebar

For Drupal core:
- Module requires `drupal/core:^11` → use `drupal/recommended-project:^11`
- Module requires `drupal/core:^10` → use `drupal/recommended-project:^10`
- Check the module's `composer.json` if unsure

## Step 2: Scaffold the ddev Environment

**IMPORTANT: Do NOT stop, delete, or tear down any other DDEV projects.** Other
instances in DRUPAL_ISSUES/ may be in active use. Only operate within the new
issue's directory. If there's a port conflict, ask the user.

```bash
ISSUE_DIR="/home/alphons/project/freelygive/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/{issue_id}"
mkdir -p "$ISSUE_DIR"
cd "$ISSUE_DIR"
```

### Environment Setup via Agent

Dispatch the `drupal-ddev-setup` agent with:
- Issue ID: from artifacts or the issue URL
- Project: from `issue.json` field `project`
- Version: from `issue.json` field `version`
- Mode: `fork` if we need to fix code, `packagist` if just reproducing
- Fork details: from `merge-requests.json` primary MR's `source_branch` (if fork mode)

Dispatch the DDEV agent with `run_in_background: true` so you can do useful
work while it sets up (~3-4 minutes).

### Parallel Work While DDEV Sets Up

While the DDEV agent runs in the background, perform static code review of the
MR diff (if an MR exists). This requires NO running environment:

1. **Read the full MR diff** from `artifacts/mr-{iid}-diff.patch`
2. **Static review checklist** (for each file in the diff):
   - `declare(strict_types=1)` present in new PHP files?
   - No `\Drupal::` static calls in services/controllers?
   - Constructor injection used correctly?
   - PHPDoc on all public methods?
   - `$this->t()` for user-facing strings?
   - Proper exception handling (not swallowing errors)?
   - Entity ID constraints respected (64 char max for config entities)?
   - Input validation at system boundaries?
3. **Test coverage gap analysis**: identify new/changed methods that need tests
4. **Note findings** for use after DDEV is ready

When the DDEV agent completes (you will be notified), use its enriched report
directly: it includes exact paths to phpunit/phpcs, module path, MR application
status, and DDEV URL. Do NOT re-verify file existence or binary paths.
If FAILED, review the error and either fix manually or ask the user.

The manual setup steps below are the FALLBACK if the agent is unavailable or fails.

### ddev config

Use a short project name derived from the issue ID to avoid conflicts:

```bash
ddev config \
  --project-type=drupal \
  --php-version=8.3 \
  --docroot=web \
  --project-name=d{issue_id}
```

### Start + install Drupal

```bash
ddev start
ddev composer create drupal/recommended-project:{core_version} --no-interaction
ddev composer require drush/drush --no-interaction
ddev drush site:install --account-name=admin --account-pass=admin -y
```

Where `{core_version}` is `^11`, `^10`, etc. based on step 1.

## Step 3: Install Required Modules

Install each module at the version specified in the issue:

```bash
ddev composer require drupal/{module1}:{version1} drupal/{module2} --no-interaction
ddev drush en {module1} {module2} {module3} -y
```

**Watch for dependency errors.** Some modules need `drupal/token`, `drupal/key`,
etc. If `drush en` fails with a missing dependency, `composer require` it and retry.

### If the issue has an MR to test

To test WITH the fix applied:
```bash
# Fetch the MR diff and apply it
cd web/modules/contrib/{module}
curl -L "https://git.drupalcode.org/project/{project}/-/merge_requests/{mr_id}.diff" | git apply
```

To test WITHOUT the fix (reproduce the original bug), just use the module as-is.

## Step 4: Reproduce the Bug

Follow the issue's steps to reproduce **exactly**. If steps involve UI configuration:

1. Generate a login link: `ddev drush uli`
2. Use Claude Chrome or Playwright to navigate and interact
3. Take screenshots at each significant step

### Screenshot capture

**Prefer Chrome MCP tools** (already available, no installation needed):
1. `mcp__claude-in-chrome__navigate` to open the DDEV site (use uli link)
2. `mcp__claude-in-chrome__computer` with screenshot action to capture pages
3. `mcp__claude-in-chrome__gif_creator` for multi-step workflows

**Fallback (if Chrome MCP unavailable):** Install Playwright:
```bash
cd "$ISSUE_DIR"
npm init -y && npm install playwright
npx playwright install chromium
```

Save screenshots to `$ISSUE_DIR/screenshots/` with numbered prefixes:

```
screenshots/
  01-form-display.png
  02-config-setup.png
  03-error-triggered.png
  04-watchdog-log.png
```

### Check error logs

After reproducing, always check:
```bash
ddev drush watchdog:show --count=5 --severity=3 --format=json
```

Compare the error message with what the issue reports.

## Step 5: Auto-Continue to Next Phase

After reproduction/testing is complete, automatically continue. Do NOT ask the user.

| Outcome | Auto-Action |
|---------|-------------|
| Issues found that need code fixes | Run preflight search, then invoke `/drupal-contribute-fix` |
| MR verified, working correctly | Invoke `/drupal-issue-comment` to draft confirming comment |
| Bug reproduced, no fix expected from us | Invoke `/drupal-issue-comment` to draft findings |
| Cannot reproduce | Invoke `/drupal-issue-comment` to draft "could not reproduce" comment |

### Preflight Gate (MANDATORY before writing fixes)

If you identified issues during review that need code changes, you MUST run a
preflight search BEFORE writing any code. This checks if someone else already
identified and fixed the same problems:

```bash
DCF_ROOT=$(find ~/.claude -path "*/drupal-contribute-fix/SKILL.md" -exec dirname {} \; 2>/dev/null | head -1)
python3 "$DCF_ROOT/scripts/contribute_fix.py" preflight \
  --project {module} \
  --keywords "{brief description of issues found}" \
  --out .drupal-contribute-fix
```

- If upstream fix exists: note it, do not duplicate the work
- If nothing found: proceed to `/drupal-contribute-fix`

This takes 30 seconds and prevents duplicate MRs.

Output (if comment drafted) goes to: `$ISSUE_DIR/issue-comment-{issue_id}.html`

## Companion skills

This skill handles **environment + reproduction**. Next steps are auto-invoked:

| What | Skill | When |
|------|-------|------|
| Writing the actual fix | `/drupal-contribute-fix` | Auto: when issues found |
| Code review before submitting | `drupal-reviewer` agent | Auto: via contribute-fix |
| Verifying the fix works | `drupal-verifier` agent | Auto: via contribute-fix |
| Drafting the d.o comment | `/drupal-issue-comment` | Auto: when review complete |
| Coding standards check | `/drupal-coding-standards` | Auto: via contribute-fix |

## Quick reference

```
/drupal-issue-review 3561693
/drupal-issue-review https://www.drupal.org/project/ai/issues/3561693
```

Both forms work. The skill extracts the issue ID either way.

## Handoffs (Auto-Invoked)

These are invoked AUTOMATICALLY. Do not ask the user which to use.

| After this phase | AUTO-INVOKE | Purpose |
|-----------------|-------------|---------|
| Issues found, need a fix | `/drupal-contribute-fix` | Write the fix + tests, stops at push gate |
| MR verified, no issues | `/drupal-issue-comment` | Draft confirming comment, present to user |
| Bug reproduced, no fix from us | `/drupal-issue-comment` | Draft findings comment, present to user |

## Progress Tracking

Use lazy task creation. Do NOT create all 6 tasks upfront.
Create each task only when you START that phase.
