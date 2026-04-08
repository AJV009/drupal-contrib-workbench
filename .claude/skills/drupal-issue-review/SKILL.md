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

## Hands-Free Operation

Hands-free from DDEV setup through reproduction. Canonical rules in
`CLAUDE.md` "Hands-Free Workflow (Critical)". After reproduction/testing,
auto-chain:
- Issues found needing code fixes -> `/drupal-contribute-fix`
- MR verified and working -> `/drupal-issue-comment` (confirming comment)
- Bug reproduced, no fix from us -> `/drupal-issue-comment` (findings)

Stop point is the push gate in `/drupal-contribute-fix` or the draft comment.

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

## Gotchas

- **Never stop/delete other DDEV projects.** Only operate within
  `DRUPAL_ISSUES/{id}/`. Other instances in `DRUPAL_ISSUES/` may be in
  active use. On port conflict, ask the user — do not auto-increment or
  stop neighbors.
- **MR freshness: dry-run `git apply --check` before code review.** A
  green GitLab pipeline on the MR's own base branch does NOT imply clean
  apply to the current target branch. Stale MRs waste review effort.
- **Drush login links are single-use and expire quickly.** Regenerate
  `ddev drush uli --no-browser` for each agent-browser session; a saved
  URL from 10 minutes ago will fail silently.
- **Dependency declaration gaps.** Some modules need `drupal/token`,
  `drupal/key`, etc. without declaring them. If `drush en` fails with a
  missing dependency, `composer require` it and retry; don't assume the
  issue.
- **Discover project test base classes before writing tests.** The AI
  module provides `BaseClassFunctionalJavascriptTests` with built-in
  `takeScreenshot()` and video recording. Use project base classes when
  they exist instead of building from `KernelTestBase`/`WebDriverTestBase`
  directly. Scan `tests/` for `*TestBase*`, `Base*Test*`.
- **Frontend diff changes require visual verification.** CSS/Twig/JS/theme
  diffs cannot be verified by reading code alone. A single class rename
  can break icon positioning. Always take desktop + mobile screenshots
  when the diff touches these files.

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

While the DDEV agent runs in the background (~3-4 min), read the MR diff
at `artifacts/mr-{iid}-diff.patch` and work through the static review
checklist at `references/static-review-checklist.md`. It covers coding
standards, test-coverage gaps, premise/architectural verification, and
MR freshness. Record findings to hand to the verifier/reviewer agents
after DDEV is ready. No running environment needed.

When the DDEV agent completes (you will be notified), use its enriched report
directly: it includes exact paths to phpunit/phpcs, module path, MR application
status, and DDEV URL. Do NOT re-verify file existence or binary paths.
If FAILED, review the error and either fix manually or ask the user.

The manual setup steps below are the FALLBACK if the agent is unavailable or fails.

### Manual fallback (if the agent fails)

`ddev config --project-type=drupal --project-name=d{issue_id}`, then
`ddev start`, `ddev composer create drupal/recommended-project:{core_version}`,
`ddev composer require drush/drush`, and
`ddev drush site:install --account-name=admin --account-pass=admin -y`.
Core version (`^11`, `^10`) comes from Step 1. Prefer the agent over this.

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
cd web/modules/contrib/{module}
# Always dry-run first to catch stale MRs before investing review effort
curl -sL "https://git.drupalcode.org/project/{project}/-/merge_requests/{mr_id}.diff" -o /tmp/mr-{mr_id}.diff
git apply --check /tmp/mr-{mr_id}.diff
```

If `--check` fails, the MR does not apply cleanly to the installed module version.
Do NOT proceed with review. Instead:
- Note the specific files/hunks that conflict
- Check `git log` on the module to identify what changed upstream since the MR
- Draft a comment (via `/drupal-issue-comment`) noting the MR needs a rebase,
  listing the specific conflicts
- Do NOT mark RTBC on a stale MR

If `--check` passes:
```bash
git apply /tmp/mr-{mr_id}.diff
```

To test WITHOUT the fix (reproduce the original bug), just use the module as-is.

## Step 4: Reproduce the Bug

Follow the issue's steps to reproduce **exactly**. If steps involve UI configuration:

1. Generate a login link: `ddev drush uli --no-browser`
2. Use `agent-browser` to navigate and interact (invoke the `/agent-browser` skill for detailed usage)
3. Take screenshots at each significant step

### Screenshot capture

Use the `agent-browser` skill for all browser interaction (full command
reference lives there). Typical flow: login via
`ddev drush uli --no-browser`, open in agent-browser, wait networkidle,
snapshot for refs, click/fill, screenshot `--full` to
`$ISSUE_DIR/screenshots/NN-slug.png`, close.

Save screenshots to `$ISSUE_DIR/screenshots/` with numbered prefixes
(`01-form-display.png`, `02-config-setup.png`, `03-error-triggered.png`,
`04-watchdog-log.png`, etc.).

### Visual verification when reviewing an existing MR with frontend changes

When reviewing an existing MR (categories B, E, I) whose diff includes .css,
.twig, .theme, or .js files, visual verification is part of reproduction/testing,
not a separate gate. No extra stop point is added.

1. After applying the MR, take screenshots of all affected pages at desktop (1280px)
   and mobile (375px via `agent-browser set viewport 375 812`)
2. Verify: icons render, positioning is correct, no overlapping elements, hover/focus
   states work, responsive layout is intact
3. If visual issues are found, they count as "issues found that need code fixes" in the
   auto-continue decision (Step 5), which routes to `/drupal-contribute-fix`
4. If visual verification passes, include screenshot paths in the comment draft

Do NOT skip this for "simple CSS changes." The issue that prompted this rule was a
single class rename that broke icon positioning and missed an entire component
(Tools Library) that also needed updating.

### Check error logs

After reproducing, always check:
```bash
ddev drush watchdog:show --count=5 --severity=3 --format=json
```

Compare the error message with what the issue reports.

## Step 4.5: Pre-Work Gate (optional)

If `--pre-work-gate` was passed through from `/drupal-issue`, STOP here and present
a summary before auto-continuing. This gate only applies when the next step would
be writing a code fix (categories A, B with issues, C, E with scope escalation, G).
Skip it for comment-only outcomes (MR verified, cannot reproduce, just reply).

### What to present

```
===========================================================
  PRE-WORK GATE - Issue #{issue_id}
===========================================================

Classification: {letter} ({description})
Module: {module_name} ({version})
DDEV: {running_url or "not needed"}

Reproduction: {CONFIRMED / NOT REPRODUCED / N/A}
  - {one-line summary of what was found}

Static Review Findings:
  - {bullet points from parallel code review, if any}

Existing MRs: {summary of active MRs or "None"}
Preflight: {upstream fix status}

Suggested Actions:
  1. [PROCEED] Write fix + kernel test (recommended)
  2. [COMMENT] Just post findings, no code fix
  3. [ADJUST]  Change approach — describe what you want
  4. [ABORT]   Stop here

What would you like to do?
===========================================================
```

Wait for the user's response, then:
- **PROCEED**: Continue to `/drupal-contribute-fix` as normal
- **COMMENT**: Invoke `/drupal-issue-comment` with the findings
- **ADJUST**: Read the user's freeform text, treat it as the new approach directive,
  then continue to `/drupal-contribute-fix` with that guidance
- **ABORT**: Stop. Do not invoke any further skills.

If `--pre-work-gate` was NOT passed, skip this step entirely and auto-continue.

## Step 5: Auto-Continue to Next Phase

After reproduction/testing is complete (and after the pre-work gate, if enabled),
automatically continue. Do NOT ask the user (unless the pre-work gate is active).

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

## Companion Skills (Auto-Invoked)

This skill handles environment + reproduction. The next step is invoked
automatically based on the reproduction outcome; do not ask the user which.

| After this phase | Auto-invoke | Purpose |
|-----------------|-------------|---------|
| Issues found, need a fix | `/drupal-contribute-fix` | Write the fix + tests (chains reviewer/verifier agents, stops at push gate) |
| MR verified, no issues | `/drupal-issue-comment` | Draft confirming comment, present to user |
| Bug reproduced, no fix from us | `/drupal-issue-comment` | Draft findings comment, present to user |

