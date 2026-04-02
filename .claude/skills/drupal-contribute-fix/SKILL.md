---
name: drupal-contribute-fix
description: >
  REQUIRED when user mentions a Drupal module + error/bug/issue - even without
  stack traces. Trigger on: (1) "<module_name> module has an error/bug/issue",
  (2) "Acquia/Pantheon/Platform.sh" + module problem, (3) any contrib module name
  (metatag, webform, mcp, paragraphs, etc.) + problem description. Searches
  drupal.org BEFORE you write code changes. NOT just for upstream contributions -
  use for ALL local fixes to contrib/core.
license: GPL-2.0-or-later
metadata:
  author: Drupal Community
  version: "1.7.0"
---

# drupal-contribute-fix

> **IRON LAW:** NO CODE PUSHED WITHOUT KERNEL TESTS. Every fix MUST include tests that fail against pre-fix code and pass against fixed code.

> **IRON LAW (TDD):** NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST. Write the test, watch it fail, write the minimal fix, watch it pass. In that order.

> **IRON LAW (DEBUGGING):** NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST. Read the error message. Reproduce consistently. Check recent changes. Then fix.

> **IRON LAW (VERIFICATION):** NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE. Run PHPCS. Run tests. See them pass. Only then say "done."

### Rationalization Prevention

| Thought | Reality |
|---------|---------|
| "This is just a small fix, no test needed" | Every fix needs a test. Small fixes break in surprising ways. |
| "The existing tests cover this" | If they did, they would have caught the bug. Write a new test. |
| "Let me push now and add tests later" | Tests-later means tests-never. The MR will be reviewed without them. |
| "PHPCS is probably fine" | Run it. "Probably" is not evidence. |
| "The user seems impatient, skip the review" | The user wants quality. Skipping review wastes their time later. |
| "The preflight search will just slow us down" | Duplicate MRs waste maintainer time. 30 seconds of search saves hours. |
| "should work", "probably fine", "seems correct" | RED FLAG. Run the verification command. Evidence, not assumptions. |

**Use this skill for ANY Drupal contrib/core bug - even "local fixes".**

Checks drupal.org before you write code, so you don't duplicate existing fixes.

## Before You Begin

Before writing code or running preflight, answer these questions internally:
1. Is this a contrib/core bug (not a custom module issue)?
2. Have I checked if an upstream fix already exists?
3. Do I know the exact module, version, and branch?
4. Are there existing MRs on the issue I should build on (not duplicate)?
5. Do I have reproduction steps clear enough to write a test?
6. Is there a DDEV environment ready, or do I need `/drupal-issue-review` first?

If answers 1 through 3 are unclear, run preflight first. If 4 through 6 are unclear, read the issue more carefully.

## Preferred Companion Skill: drupalorg-cli (Highly Recommended)

`drupal-contribute-fix` should focus on bug identification, triage quality, and report prep.
Use `drupalorg-cli` for issue-fork, MR, and pipeline execution steps.

Recommended split:

- **This skill:** detect bug ownership, search/match upstream issues, build clear reproduction + test steps, prepare submission-ready notes.
- **drupalorg-cli:** fork/remote setup, branch checkout, MR inspection, pipeline status/log checks, iterative push loop.

Installed at `scripts/drupalorg` in the workspace root (v0.8.5 phar, runs via Docker PHP).

```bash
# From the workspace root:
./scripts/drupalorg --version  # Drupal.org CLI 0.8.5
./scripts/drupalorg issue:show 3579478 --format=llm
```

See CLAUDE.md for the full command reference.

## Resolving Script Paths

All script paths below are relative to this skill's root directory — NOT your current working directory. Before running any command, resolve the skill root once:

```bash
for d in "$HOME/.agents/skills/drupal-contribute-fix" "$HOME/.codex/skills/drupal-contribute-fix"; do [ -f "$d/SKILL.md" ] && DCF_ROOT="$d" && break; done
```

All commands below use `$DCF_ROOT`. You only need to run the line above once per session.

## FIRST STEP - Before Writing Any Code

**If you are debugging an error in `docroot/modules/contrib/*` or `web/modules/contrib/*`,
run `preflight` BEFORE editing any code - even if the user only asked for a local fix.**

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" preflight \
  --project <module-name> \
  --keywords "<error message>" \
  --out .drupal-contribute-fix
```

### False-Positive Guard (Required)

`preflight` candidate matching is heuristic. Do not treat "already fixed" output as final without verification.

Before stopping work due to an "existing fix", you must verify all of the following:

1. Open the referenced issue/commit and confirm its title/component matches the bug class and code area.
2. Inspect the exact affected file/function in the target branch and confirm the bug condition is actually gone.
3. Record file path + commit/issue evidence in your notes/report before closing/switching local tracking.

If any verification step fails, treat it as a false positive and continue triage/fix flow.

This takes 30 seconds and may save hours of duplicate work.

**Important:** Drupal.org's `api-d7` endpoint does **not** support a full-text `text=` filter (it returns HTTP 412). If you need a manual keyword search link, use the Drupal.org UI search:

```text
https://www.drupal.org/project/issues/search/<project>?text=<keywords>
```

## Handoff After Triage (If No Code Changes Made)

If triage-only (no local code change), preserve `preflight` evidence and provide:
- The best-match issue(s)/MR(s)
- Specific reproduction + expected behavior steps
- Suggested `drupalorg-cli` commands to continue contribution work

## NEVER DELETE Contribution Artifacts

**DO NOT delete these files:**
- `.drupal-contribute-fix/` directory
- Diff files in `diffs/`
- `ISSUE_COMMENT.md`
- `REPORT.md`

Even if the user asks to "reset" or "undo" the local fix, **preserve the contribution artifacts**
so the fix can be submitted upstream. The whole point is to help the Drupal community.

## Complete Workflow

```
1. DETECT    → Error from contrib/core? Trigger activated.
2. PREFLIGHT → Search drupal.org BEFORE writing code
3. TRIAGE    → Verify/score candidates, avoid false positives
4. PREP      → Produce report-quality repro/test steps and recommendation
5. PACKAGE   → If code changed, run `package`; otherwise keep preflight evidence only
6. HANDOFF   → Prefer `drupalorg-cli` for fork/MR/pipeline execution
7. PRESERVE  → Keep .drupal-contribute-fix/ artifacts for follow-up
```

**Steps 4-7 are MANDATORY.** Don't stop at "issue found"; leave an actionable handoff.

## What This Skill Does

1. **Searches drupal.org** for existing issues/MRs matching the bug (preflight)
2. **Validates candidate relevance** before declaring "already fixed" (false-positive guard)
3. **Writes the fix** following TDD (test first, then minimal code)
4. **Writes tests** with diff-aware planning
5. **Validates tests** are legitimate (stash/unstash)
6. **Runs quality gates** (PHPCS, reviewer agent, verifier agent)
7. **Generates contribution artifacts** (diff, report, comment draft)
8. **Presents push gate** and waits for user confirmation

## Mandatory Gatekeeper Behavior

**No new local diff artifact may be generated until upstream search + "already fixed?" checks are complete.**
**No "STOP existing fix found" decision may be accepted until the file-level verification steps above are completed.**

The skill ends in exactly one of these outcomes:

| Exit Code | Outcome | Meaning |
|-----------|---------|---------|
| 0 | PROCEED | MR artifacts + local diff generated |
| 10 | STOP | Existing upstream fix found (MR-based, historical patch attachments, or closed-fixed) |
| 20 | STOP | Fixed upstream in newer version (reserved for future use) |
| 30 | STOP | Analysis-only recommended (change would be hacky/broad) |
| 40 | ERROR | Couldn't determine project/baseline, network failure |
| 50 | STOP | Security-related issue detected (follow security team process) |

**Workflow modes:** When an existing fix is found (exit 10), the skill reports whether the
issue has an active MR or only historical patch attachments to guide contributor workflow.

## Workflow Hygiene

Always use **Merge Requests**, never patch uploads (unless maintainers explicitly request it).
When available, use `drupalorg-cli` for fork/remote/branch/pipeline operations.

## Commands

### Preflight (search only)

Search drupal.org for existing issues without generating local artifacts:

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" preflight \
  --project metatag \
  --keywords "TypeError MetatagManager::build" \
  --paths "src/MetatagManager.php" \
  --out .drupal-contribute-fix
```

### Package (search + generate)

Search upstream AND generate contribution artifacts if appropriate:

```bash
# For web/ docroot layout:
python3 "$DCF_ROOT/scripts/contribute_fix.py" package \
  --root /path/to/drupal/site \
  --changed-path web/modules/contrib/metatag \
  --keywords "TypeError MetatagManager::build" \
  --test-steps "Enable metatag" "Visit affected page" "Confirm fixed behavior" \
  --out .drupal-contribute-fix

# For docroot/ layout (common in Acquia/BLT projects):
python3 "$DCF_ROOT/scripts/contribute_fix.py" package \
  --root /path/to/drupal/site \
  --changed-path docroot/modules/contrib/mcp \
  --keywords "module not installed" "update_get_available" \
  --test-steps "Set up failing config" "Trigger failing code path" "Confirm expected post-fix result" \
  --out .drupal-contribute-fix
```

**Note:** `package` always runs `preflight` first and refuses to generate local artifacts
if an existing fix is found (unless `--force` is provided).

### Test (generate RTBC comment)

Generate a Tested-by/RTBC comment for an existing MR or diff artifact you've tested:

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" test \
  --issue 3345678 \
  --tested-on "Drupal 10.2, PHP 8.2" \
  --result pass \
  --out .drupal-contribute-fix
```

Options: `--result` can be `pass`, `fail`, or `partial`. Use `--mr` or `--patch`
to specify which artifact you tested.

### Reroll (legacy patch-only issues)

Legacy fallback only: reroll an existing patch attachment when maintainers explicitly request patch workflow:

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" reroll \
  --issue 3345678 \
  --patch-url "https://www.drupal.org/files/issues/metatag-fix-3345678-15.patch" \
  --target-ref 2.0.x \
  --out .drupal-contribute-fix
```

This downloads the patch, attempts to apply it to your target branch, and generates
a rerolled patch if needed (or confirms it applies cleanly). Prefer MR workflow for new contributions.

### Common Options

| Option | Description |
|--------|-------------|
| `--project` | Drupal project machine name (e.g., `metatag`, `drupal`) |
| `--keywords` | Error message fragments or search terms (space-separated) |
| `--paths` | Relevant file paths (space-separated) |
| `--out` | Output directory for artifacts |
| `--offline` | Use cached data only, don't hit API |
| `--force` | Override gatekeeper and generate local diff artifact anyway |
| `--issue` | Known issue number (runs gatekeeper check against this issue) |
| `--detect-deletions` | Include deleted files in diff (risky with Composer trees) |
| `--test-steps` | **REQUIRED** Specific test steps for the issue (agent must provide) |

### Test Steps (MANDATORY)

**Agents MUST provide specific test steps via `--test-steps`.** Generic placeholders are not acceptable.

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" package \
  --changed-path docroot/modules/contrib/mcp \
  --keywords "update module not installed" \
  --test-steps \
    "Enable MCP module with Update module disabled" \
    "Call the general:status tool via MCP endpoint" \
    "Before fix: Fatal error - undefined function update_get_available()" \
    "After fix: JSON response with status unavailable" \
  --out .drupal-contribute-fix
```

Test steps should:
1. Describe how to set up the environment to reproduce the bug
2. Describe the action that triggers the bug
3. Describe the expected behavior BEFORE the fix (the bug)
4. Describe the expected behavior AFTER the fix (the fix)

## Output Files

```
.drupal-contribute-fix/
├── UPSTREAM_CANDIDATES.json              # Search results cache (shared)
├── 3541839-fix-metatag-build/            # Known issue
│   ├── REPORT.md                         # Analysis & next steps
│   ├── ISSUE_COMMENT.md                  # Paste-ready drupal.org comment
│   └── diffs/
│       └── project-fix-3541839.diff
├── 3573571-component-context/            # Optional local CI evidence
│   ├── LOCAL_CI_PARITY_2026-02-16.md     # Job/result summary + commands
│   └── ci/
│       ├── canvas-ci-local-full-20260216.log
│       └── canvas-ci-local-rerun-20260216.log
└── unfiled-update-module-check/          # New issue needed
    ├── REPORT.md
    ├── ISSUE_COMMENT.md
    └── diffs/
        └── project-fix-new.diff
```

**Directory naming:**
- `{issue_nid}-{slug}/` - Existing issue matched or specified
- `unfiled-{slug}/` - No existing issue found

**Preflight vs Package:** `preflight` only updates `UPSTREAM_CANDIDATES.json`.
Issue directories are created by `package` when generating artifacts.

## Security Issue Handling

If the fix appears security-related, **STOP with exit code 50**. Do NOT post publicly.
Follow: https://www.drupal.org/drupal-security-team/security-team-procedures

## Minimal + Upstream Acceptable

- Minimal fixes only: fix the reported issue, nothing else
- Separate "must fix" from "nice-to-haves" (exclude nice-to-haves from MR)
- Avoid patterns likely to be rejected (see [references/hack-patterns.md](references/hack-patterns.md))

## Git Commit Convention

```bash
git commit -m "Issue #<nid> by <username>: <short description>"
# NEVER add Co-Authored-By tags to d.o commits.
```

For rebasing when needed:
```bash
git fetch origin && git rebase BASE_BRANCH_NAME && git push --force-with-lease
```

### SSH Remote Verification (Before Pushing)

Before any `git push`, verify the remote uses SSH (not HTTPS). HTTPS remotes
will prompt for credentials and fail in non-interactive contexts.

```bash
# Check current remote
git remote -v

# If remote is HTTPS (https://git.drupalcode.org/...), switch to SSH:
git remote set-url origin git@git.drupal.org:issue/{project}-{issue_id}.git

# Always use git.drupal.org (not git.drupalcode.org) for SSH — see SSH config.
```

## Testing & Verification References

Every fix MUST include tests. The following reference docs are bundled:

- `references/smoke-testing.md` - Curl smoke tests, drush eval patterns, DDEV shell gotchas, test script creation
- `references/testing-patterns.md` - PHPUnit test patterns for Drupal
- `references/common-checks.md` - Common verification scenarios
- `references/core-testing.md` - Core testing patterns

### Test Planning from Diff (BEFORE Writing Test Code)

Before writing any tests, analyze the diff to create a targeted test plan:

1. For each file in the diff:
   - NEW file? Test all public methods.
   - MODIFIED file? Test only changed/added methods.
   - Config file? Verify schema/values.
   - Test file? Skip (it IS a test).

2. For each changed/new method, identify:
   - Input types and edge cases
   - Error/exception paths
   - Dependencies that need mocking

3. Write the test plan as a checklist BEFORE writing code:
   ```
   - [ ] ClassName::methodName() handles valid input
   - [ ] ClassName::methodName() handles empty input
   - [ ] ClassName::methodName() propagates ConnectionException
   ```

4. Each checklist item must include: method name, setup, assertion, and WHY.
   No placeholders like "test error handling" (WHICH error? HOW handled?).

### TEST COVERAGE GATE (NON-NEGOTIABLE)

**Every code fix pushed to an MR MUST include kernel tests.** This applies to
both core AND contrib modules in this workspace. Do not push code-only commits
and assume tests can come later. Reviewers WILL send it back.

Before marking any fix work as complete:
1. Write kernel tests that cover each behavioral change
2. Verify the tests FAIL against the pre-fix code
3. Verify the tests PASS against the fixed code
4. Run the full module test suite to confirm no regressions
5. Run PHPCS on all new/modified files

This gate was added after issue #3542457 where code fixes were pushed without
tests and jibran had to send the MR back to "Needs work" for missing test
coverage. That round-trip wasted time for everyone.

### Test Validation (MANDATORY - Proves Tests Are Legitimate)

After all tests pass against the fixed code, validate they are not trivially true:

1. **Identify source changes** (not test files):
   ```bash
   # Get list of changed source files (exclude test files)
   git diff --name-only -- 'src/' 'config/' '*.module' '*.install'
   ```

2. **Stash only source changes** (keep test files unstashed):
   ```bash
   git stash push -- src/ config/ *.module *.install
   ```
   Adjust paths based on what was actually changed. The goal: revert the FIX
   while keeping the TESTS in place.

3. **Run the new/modified tests against unfixed code:**
   ```bash
   ddev exec ../vendor/bin/phpunit [new_test_files]
   ```

4. **Verify tests FAIL:**
   - If all new tests fail: VALIDATED. Tests are legitimate.
   - If some tests pass without the fix: those tests are trivially true
     (they don't actually test the behavioral change). Rewrite them.
   - If all tests pass without the fix: ALL tests are trivially true. Rewrite.

5. **Restore the fix:**
   ```bash
   git stash pop
   ```

6. **Report results in push gate summary:**
   ```
   Test Validation: 22/24 correctly fail without fix
   Trivially passing: 2/24 (testDefaultConfig, testEmptyList - test setup, not fix)
   ```

7. **If invalid tests found:** rewrite them to actually test the behavioral change.
   Re-run validation. Max 2 rewrite cycles.

**Edge cases:**
- Test-only changes (no source fix): skip validation.
- Config-only changes: stash config files specifically.
- If `git stash pop` fails: `git checkout -- src/ config/` to restore from last commit.

### Pre-Push Quality Gate (MANDATORY)

Before pushing to the issue fork, ALL of these must pass:

**Step 1: PHPCS (automatic)**
```bash
ddev exec phpcs --standard=Drupal,DrupalPractice [changed_files]
```
Required: 0 errors, 0 warnings. If issues found, fix automatically and re-run.

**Step 2: Tests (automatic)**
```bash
ddev exec phpunit [module_test_path]
```
Required: 0 failures, 0 errors. If tests fail, fix and re-run.

**Step 3: Reviewer Agent (MANDATORY, not optional)**

ALWAYS dispatch the `drupal-reviewer` agent after code changes are complete.
This is not conditional on change size. Every change gets reviewed.

- Pass: list of changed files, module path, PHPCS results
- Wait for: APPROVED | NEEDS_WORK | CONCERNS
- If NEEDS_WORK: fix issues, re-dispatch (max 2 iterations)
- If CONCERNS: include in push gate summary for user to see

**Step 4: Verifier Agent (MANDATORY, not optional)**

ALWAYS dispatch the `drupal-verifier` agent after code changes are complete.
Can run in parallel with the reviewer (use `run_in_background` for one).

- Pass: module path, test file paths, DDEV project name
- Wait for: VERIFIED | FAILED | BLOCKED
- If FAILED: investigate, fix, re-dispatch (max 2 iterations)
- If BLOCKED: report to user in push gate summary

Both agents MUST report before the push gate is presented.
Only push after all checks pass AND the user confirms (see Push Gate below).

**Step 5: Draft Issue Comment (automatic)**

Before presenting the push gate, invoke `/drupal-issue-comment` to draft a
d.o comment summarizing the changes. Pass it: issue context, what was found,
what was fixed, and test results. The draft is saved to
`DRUPAL_ISSUES/{issue_id}/issue-comment-{issue_id}.html` and included in the
push gate summary for user review.

### Push Gate (THE ONLY STOP POINT IN THE ENTIRE WORKFLOW)

> **IRON LAW:** NEVER AUTO-PUSH. Always present the summary and wait for explicit user confirmation.

This is the ONE place in the hands-free workflow where you stop and wait for the user.
Everything before this point runs automatically. Nothing after this point runs without
user confirmation.

After all checks pass, present a complete summary:

1. **Issue:** number, title, and what was found
2. **Changes made:** list all modified/created files with a one-line description each
3. **Tests:** which tests were written, how many pass, test validation results (if run)
4. **PHPCS:** output showing 0 errors, 0 warnings (fresh, not from memory)
5. **Reviewer verdict:** APPROVED / NEEDS_WORK (if reviewer agent was dispatched)
6. **Verifier verdict:** VERIFIED / FAILED (if verifier agent was dispatched)
7. **Comment draft:** path to the `.html` comment file (if drafted via `/drupal-issue-comment`)
8. **What will be pushed:** the branch name, remote, and commit message
9. **Diff summary:** files changed with +/- line counts

Then ask: **"Ready to push these changes to the issue fork? (yes/no)"**

Only push after the user explicitly confirms. If they say no, ask what they want to change.

### Interdiff Generation (When Pushing Follow-Up Commits)

When pushing follow-up commits to an existing MR (not creating a new MR):

```bash
BASE_COMMIT=$(git log --oneline | head -2 | tail -1 | cut -d' ' -f1)
git diff $BASE_COMMIT..HEAD > DRUPAL_ISSUES/{issue_id}/interdiff-{issue_id}.patch
```

Include the interdiff summary in the push gate and reference it in the draft comment.

### After Successful Push

After the push succeeds, dispatch the `drupal-pipeline-watch` agent in the background
to monitor the GitLab CI pipeline:

- Pass: project path, MR IID, GitLab token file
- The agent will poll every 60 seconds and report when the pipeline completes
- If pipeline fails: the agent provides the failing job and error extract

Tell the user: "Push complete. Pipeline monitoring started. You'll be notified when CI completes."

Then present finishing options:

```
What would you like to do next?
1. Monitor pipeline - Watch GitLab CI and report results
2. Post comment - Open the issue page to post the draft comment
3. Clean up - Stop DDEV project (keeps files)
4. Next issue - Start work on a different issue
5. Done for now - Keep everything as-is
```

Wait for user's choice. Option 3 requires confirmation before stopping DDEV.

### Agent Prompt Templates

When dispatching review/verification agents, use the prompt templates:
- `agents/reviewer-prompt.md` for code review before pushing
- `agents/verifier-prompt.md` for verifying the fix works in a DDEV environment

Fill in the `[BRACKETED]` context variables before dispatching.

## References

- [references/issue-status-codes.md](references/issue-status-codes.md) - Drupal.org issue status mapping
- [references/patch-conventions.md](references/patch-conventions.md) - Patch naming and format
- [references/hack-patterns.md](references/hack-patterns.md) - Patterns to avoid
- [references/core-testing.md](references/core-testing.md) - Writing tests for Drupal core contributions

## Example Output

See [examples/sample-report.md](examples/sample-report.md) for a complete example.

## Handoffs

| After this phase | REQUIRED NEXT SKILL | Purpose |
|-----------------|---------------------|---------|
| Fix is ready to push | Present summary, ask user to confirm | Git push to issue fork branch |
| Need to draft a d.o comment | `/drupal-issue-comment` | Write up findings for the issue |
| Need environment setup first | `/drupal-issue-review` | Scaffold DDEV, reproduce, verify |

## Progress Tracking

Create a TaskCreate entry for each phase:
1. Preflight search on drupal.org
2. Triage and classify candidate issues
3. Write the fix (TDD cycle)
4. Write kernel tests
5. Run PHPCS + full test suite
6. Pre-push review
7. Present completion summary to user (changes, tests, comment draft)
8. Wait for user confirmation before pushing
9. Push to issue fork (only after user says yes)
