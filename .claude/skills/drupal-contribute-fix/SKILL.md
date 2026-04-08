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

## Rules at a glance

Read before every session. Details for each rule live further down.

1. **Preflight first.** Run `preflight` mode before editing any contrib/core code (duplicate-MR guard, `modes/preflight.md`).
2. **Read called APIs before calling them** in scanning/validation/transformation code. Docblocks lie; implementations don't. (Before You Begin Q7.)
3. **TDD order.** Failing test -> minimal fix -> passing test. No exceptions.
4. **Validate tests are not trivially true.** Stash source, re-run new tests, confirm they fail without the fix. (Testing Step 3.)
5. **CI parity before push.** Run `scripts/local_ci_mirror.sh` (Step 0 of Pre-Push Quality Gate). Exit 0 required.
6. **Dispatch spec + code + verifier agents** before presenting the push gate. All three must report. (Pre-Push Quality Gate Steps 3-5.)
7. **Never auto-push.** Present the push gate summary and wait for explicit user confirmation. (Push Gate.)
8. **Humility rules in comment drafts.** No "happy to change" hedges on incomplete work, no "separate follow-up" without the three-part pre-follow-up search, no self-congratulatory filler. (See `drupal-issue-comment` SKILL.md.)
9. **Minimal fix for the full bug class**, not just the reported symptom. Enumerate input shapes before declaring done. (Minimal + Upstream Acceptable.)
10. **Preserve contribution artifacts.** Never delete `.drupal-contribute-fix/`, `diffs/`, `REPORT.md`, or `ISSUE_COMMENT.md`, even if asked to "reset".

### Rationalization Prevention

| Thought | Reality |
|---------|---------|
| "This is just a small fix, no test needed" | Every fix needs a test. Small fixes break in surprising ways. |
| "The existing tests cover this" | If they did, they would have caught the bug. Write a new test. |
| "Let me push now and add tests later" | Tests-later means tests-never. The MR will be reviewed without them. |
| "PHPCS is probably fine" | Run it. "Probably" is not evidence. |
| "The user seems impatient, skip the review" | The user wants quality. Skipping review wastes their time later. |
| "The preflight search will just slow us down" | Duplicate MRs waste maintainer time. 30 seconds of search saves hours. |
| "The proper implementation is ~N lines, this 3-line shortcut is good enough" | Write the proper version before calling it too long. Line estimates without a draft are almost always wrong. The recursive walker in #3580690 was rationalized as "about 50 lines with two new helpers" in prose; it was ~20 lines with one helper when actually written. |
| "This trade-off is acceptable for [the common case]" | Turn the trade-off into a failing test case with an adversarial input. If the test fails against your shortcut, the trade-off was actually a silent bug, not a trade-off. Prose justification is not evidence; a test is. #3580690's `json_encode` shortcut was justified as "safer failure mode for PII" — it was a silent bypass for every pattern targeting control chars, quotes, or backslashes. |
| "should work", "probably fine", "seems correct" | RED FLAG. Run the verification command. Evidence, not assumptions. |

**Use this skill for ANY Drupal contrib/core bug - even "local fixes".**

Checks drupal.org before you write code, so you don't duplicate existing fixes.

## Gotchas

Environment-specific traps. Most of these have burned us at least once.

- **`ChatMessage::getRenderedTools()` double-encodes arguments.** It calls
  `Json::encode()` internally via `ToolsFunctionOutput::getOutputRenderArray()`.
  Wrapping the result in another `json_encode()` produces `\"` and `\\`
  escape artifacts that hide control chars, quotes, and backslashes from
  regex scanning. Walk `$tool->getArguments()->getValue()` directly for
  content inspection. (#3580690)
- **PHPCS warnings do not fail Drupal CI.** CI runs phpcs with
  `ignore_warnings_on_exit=1`. Local runs must match
  (`--runtime-set ignore_warnings_on_exit 1`) or the push gate reports
  false failures. `scripts/local_ci_mirror.sh` handles this automatically.
- **Local cspell ≠ CI cspell.** The Drupal CI template ships a base
  dictionary (`langcode`, `vid`, etc.) local `npx cspell` cannot replicate.
  Run cspell only against files in your diff, not the whole tree.
- **Never install `phpunit/phpunit` standalone.** It resolves to v12+ which
  cannot load Drupal test base classes (`UnitTestCase`, `KernelTestBase`).
  Use `ddev composer require --dev "drupal/core-dev:^11" -W` (bundles
  PHPUnit 11). See CLAUDE.md "Dependency Rules".
- **Never install `drupal/coder` standalone.** Conflicts with the coder 8
  bundled inside `drupal/core-dev` and blocks the core-dev install.
- **drupal.org `api-d7` endpoint rejects full-text search.** `text=` on
  api-d7 returns HTTP 412. For keyword search use the UI:
  `https://www.drupal.org/project/issues/search/<project>?text=<keywords>`.
- **SSH remote: `git.drupal.org`, not `git.drupalcode.org`.** HTTPS remotes
  prompt for credentials and fail in non-interactive sessions. Switch with
  `git remote set-url origin git@git.drupal.org:issue/{project}-{issue_id}.git`.
- **Rebasing MR branches is fine.** Drupal.org recommends rebase over merge.
  Use `--force-with-lease`. The "X commits from branch" noise in GitLab is
  expected and not a merge problem.
- **`drupalorg` CLI is a phar at `./scripts/drupalorg`.** Not on `$PATH`.
  Always call with the relative path from the workspace root.
- **Test-validation stash recovery.** If `git stash pop` fails during
  Testing Step 3, use `git checkout -- src/ config/ *.module *.install` to
  restore from last commit. Do not try fancier recovery paths.

## Before You Begin

Before writing code or running preflight, answer these questions internally:
1. Is this a contrib/core bug (not a custom module issue)?
2. Have I checked if an upstream fix already exists?
3. Do I know the exact module, version, and branch?
4. Are there existing MRs on the issue I should build on (not duplicate)?
5. Do I have reproduction steps clear enough to write a test?
6. Is there a DDEV environment ready, or do I need `/drupal-issue-review` first?
7. For every existing function I plan to call from scanning, validation, or transformation code: have I read its implementation (not just the docblock) to confirm what shape it returns and whether it applies transformations (JSON encoding, HTML escaping, normalization)? Hidden transformations inside called functions are the most common source of silent bypass bugs. #3580690 shipped a double-encoding bug because `getRenderedTools()` internally calls `Json::encode()` and the author never opened the file.

If answers 1 through 3 are unclear, run preflight first. If 4 through 6 are unclear, read the issue more carefully. If 7 is unclear, open the module source and read the called functions before writing the fix.

## Companions

This skill owns bug identification, TDD, tests, quality gates, and
submission prep. For fork/remote/MR/pipeline execution use `drupalorg-cli`
(`./scripts/drupalorg`, full reference in CLAUDE.md).

Script paths in this skill are relative to the skill root, not CWD. Resolve once per session:

```bash
for d in "$HOME/.agents/skills/drupal-contribute-fix" "$HOME/.codex/skills/drupal-contribute-fix"; do [ -f "$d/SKILL.md" ] && DCF_ROOT="$d" && break; done
```

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

If triage-only (no local code change), preserve `preflight` evidence, provide
best-match issue(s)/MR(s) + reproduction steps, and suggest `drupalorg-cli`
commands to continue the contribution. Never delete `.drupal-contribute-fix/`,
`diffs/`, `ISSUE_COMMENT.md`, or `REPORT.md` even on "reset" requests —
those are the artifacts that get submitted upstream.

## Complete Workflow

```
1. DETECT    → Error from contrib/core? Trigger activated.
2. PREFLIGHT → Search drupal.org BEFORE writing code (mode: preflight)
3. TRIAGE    → Verify/score candidates, avoid false positives
4. FIX + TESTS → TDD cycle (test first, then minimal code, then validate)
5. QUALITY GATES → PHPCS, CI parity, spec reviewer, code reviewer, verifier
6. PACKAGE   → Generate artifacts (mode: package)
7. PUSH GATE → Present summary, wait for user confirmation
8. PRESERVE  → Keep `.drupal-contribute-fix/` for follow-up
```

Steps 2-8 are all mandatory. Don't stop at "issue found"; drive through to
push gate or a clean triage handoff.

## Exit Codes

The skill ends in exactly one of these outcomes. No local diff artifact
may be generated until upstream search and false-positive verification are
both complete.

| Exit Code | Outcome | Meaning |
|-----------|---------|---------|
| 0 | PROCEED | MR artifacts + local diff generated |
| 10 | STOP | Existing upstream fix found (active MR, historical patch attachments, or closed-fixed) |
| 20 | STOP | Fixed upstream in newer version (reserved) |
| 30 | STOP | Analysis-only recommended (change would be hacky/broad) |
| 40 | ERROR | Couldn't determine project/baseline, network failure |
| 50 | STOP | Security-related issue (follow security team process) |

## Commands

Full command reference (flags, examples, exit codes, gotchas) lives in the
mode files. Open the one that matches your current phase:

| Mode | When | Reference |
|------|------|-----------|
| `preflight` | Before writing any code for a contrib/core bug | `modes/preflight.md` |
| `package` | After the fix is written, to generate contribution artifacts | `modes/package.md` |
| `test` | Testing someone else's MR for RTBC | `modes/test.md` |
| `reroll` | Legacy patch workflow (only when maintainers request it) | `modes/reroll.md` |

All four invoke `$DCF_ROOT/scripts/contribute_fix.py` with the matching
subcommand. `package` always runs `preflight` first and refuses to generate
artifacts if an existing upstream fix is found (override with `--force`).

**Test steps are mandatory** (`--test-steps` flag on `package`). Steps must
describe: setup to reproduce, triggering action, pre-fix behavior (the bug),
post-fix behavior (the fix). Generic placeholders are rejected. Full examples
in `modes/package.md`.

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

## Testing

Every fix MUST include kernel tests that fail against pre-fix code and pass
against fixed code. Non-negotiable. See IRON LAWs above. Gate exists because
of #3542457 (code-only push bounced as Needs Work).

Reference docs (open when needed, not by default):
- `references/testing-patterns.md` - PHPUnit patterns for Drupal
- `references/smoke-testing.md` - Curl tests, drush eval, DDEV gotchas
- `references/common-checks.md` - Common verification scenarios
- `references/core-testing.md` - Core-specific patterns

### Step 1: Plan from the diff (before writing test code)

First, discover project test infrastructure:
```bash
find web/modules/contrib/{module} -name "*TestBase*" -o -name "*Base*Test*" | head -10
find web/modules/contrib/{module} -path "*/tests/*" -name "*.php" | head -20
```
Look for base classes that provide screenshot/video capture, pre-configured
modules, helper traits, or mock providers. Use project base classes when
they exist rather than building from `KernelTestBase`/`WebDriverTestBase`
directly. (E.g. the AI module provides `BaseClassFunctionalJavascriptTests`.)

For each file in the diff: NEW file tests all public methods; MODIFIED file
tests only changed/added methods; config file verifies schema/values; test
file itself is skipped.

For each changed/new method, identify: input types and edge cases,
error/exception paths, dependencies needing mocks. Write the plan as a
checklist first with specific assertions ("handles empty input", "propagates
ConnectionException"), never vague placeholders ("test error handling").

### Step 2: Write the tests, then the fix (TDD)

Write the test, watch it fail, write the minimal fix, watch it pass. Then
run the full module test suite to confirm no regressions, and PHPCS on all
new/modified files.

### Step 3: Validate tests are not trivially true

After tests pass against fixed code, prove they actually test the behavioral
change:

```bash
# 1. Stash source changes, keep tests in place
git stash push -- src/ config/ *.module *.install

# 2. Run new/modified tests against unfixed code
ddev exec ../vendor/bin/phpunit [new_test_files]

# 3. Verify FAILURE (expected). Then restore.
git stash pop
```

Results interpretation: all new tests fail = validated, tests are legitimate.
Some pass without fix = those are trivially true (test setup, not behavioral
change), rewrite them. All pass without fix = rewrite all. Max 2 rewrite
cycles. Report in push gate summary: `Test Validation: N/M correctly fail
without fix, K trivially passing`.

Edge cases: test-only changes skip validation; config-only changes stash
config files specifically; if `git stash pop` fails, `git checkout -- src/ config/`
to restore from last commit.

### Pre-Push Quality Gate

Before pushing to the issue fork, ALL of these must pass:

**Step 0: CI parity discovery (run first)**

Mirror every CI job that will run on the module's pipeline. PHPCS + PHPUnit
alone is not enough; modern Drupal modules enforce PHPStan, cspell,
stylelint, and eslint too, and each skipped job is a potential CI
round-trip.

```bash
/mnt/data/drupal/CONTRIB_WORKBENCH/scripts/local_ci_mirror.sh \
  web/modules/contrib/<module_name>
```

Required: exit code 0 (zero failed jobs). Do NOT proceed to Steps 1-2
below until Step 0 passes. See `references/ci-parity.md` for the full
flag list (`--fast`, `--tests-only`, `--only`, `--skip`, `--json`),
gotcha handling (PHPCS warnings, cspell dictionaries, eslint configs,
`allow_failure` jobs), and failure triage (pre-existing vs caused by
your changes).

Steps 1-2 below are per-tool fallbacks for debugging a single job in
isolation when the helper is unavailable.

**Step 1: PHPCS (automatic, fallback)**
```bash
ddev exec phpcs --standard=Drupal,DrupalPractice --runtime-set ignore_warnings_on_exit 1 [changed_files]
```
Required: 0 errors. Warnings are reported but do not block.

**Step 2: Tests (automatic, fallback)**
```bash
ddev exec phpunit [module_test_path]
```
Required: 0 failures, 0 errors. If tests fail, fix and re-run.

**Step 3: Spec Reviewer Agent** (for feature MRs and review-only flows)

Dispatch the `drupal-spec-reviewer` agent BEFORE the code reviewer. This agent
verifies that the implementation matches the issue requirements AND that the
issue's factual claims are accurate.

- Pass: issue requirements (title, description, key comments), list of changed
  files, what the implementer claims they did
- Wait for: SPEC_COMPLIANT | SPEC_GAPS
- If SPEC_GAPS: address gaps before proceeding to code review. If a gap reveals
  a false premise (e.g., the issue claims no extension point exists but one does),
  STOP and escalate to the user rather than continuing to review code built on
  a wrong foundation.
- Skip for: trivial bug fixes where the issue premise is a concrete error message
  that you already reproduced. The spec reviewer adds value when the issue
  describes architectural gaps, missing features, or how code "should" work.

**Step 4: Reviewer Agent**

ALWAYS dispatch the `drupal-reviewer` agent after code changes are complete.
This is not conditional on change size. Every change gets reviewed.

- Pass: list of changed files, module path, PHPCS results
- Wait for: APPROVED | NEEDS_WORK | CONCERNS
- If NEEDS_WORK: fix issues, re-dispatch (max 2 iterations)
- If CONCERNS: include in push gate summary for user to see

**Step 5: Verifier Agent**

ALWAYS dispatch the `drupal-verifier` agent after code changes are complete.
Can run in parallel with the reviewer (use `run_in_background` for one).

- Pass: module path, test file paths, DDEV project name
- If diff includes .css, .twig, .theme, or .js files, add to the verifier prompt:
  "Visual verification required. DDEV URL: https://d{issue_id}.ddev.site.
  Take screenshots of affected pages at desktop and mobile viewports."
- Wait for: VERIFIED | FAILED | BLOCKED
- If FAILED: investigate, fix, re-dispatch (max 2 iterations)
- If BLOCKED: report to user in push gate summary

All three agents (spec, reviewer, verifier) MUST report before the push gate
is presented. Only push after all checks pass AND the user confirms (see Push
Gate below).

**Step 6: Draft Issue Comment (automatic)**

Before presenting the push gate, invoke `/drupal-issue-comment` to draft a
d.o comment summarizing the changes. Pass it: issue context, what was found,
what was fixed, and test results. The draft is saved to
`DRUPAL_ISSUES/{issue_id}/issue-comment-{issue_id}.html` and included in the
push gate summary for user review.

The drafting rules live in `drupal-issue-comment` SKILL.md "Humility over
showmanship" section — read it before invoking. The three hard rules the
draft MUST respect on first try (so it doesn't need re-trimming):

1. **No "happy to change" hedges on incomplete work.** Finish in-scope
   mechanical follow-throughs (tests, standards, naming) BEFORE drafting;
   don't defer them to the reviewer.
2. **No "separate follow-up" language without the three-part pre-follow-up
   search** from `drupal-issue` Q10 having been run and documented.
3. **No self-congratulatory filler** about tests passing or PHPCS clean.

Canonical failure example (#3560681) is in `drupal-issue-comment` SKILL.md.

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
5. **Spec reviewer verdict:** SPEC_COMPLIANT / SPEC_GAPS (if dispatched)
6. **Reviewer verdict:** APPROVED / NEEDS_WORK (if reviewer agent was dispatched)
7. **Verifier verdict:** VERIFIED / FAILED (if verifier agent was dispatched)
8. **Visual QA:** PASS with N screenshots / N/A (no frontend changes) (from verifier report)
9. **Comment draft:** path to the `.html` comment file (if drafted via `/drupal-issue-comment`)
10. **What will be pushed:** the branch name, remote, and commit message
11. **Diff summary:** files changed with +/- line counts

Then ask: **"Ready to push these changes to the issue fork? (yes/no)"**

Only push after the user explicitly confirms. If they say no, ask what they want to change.

### Interdiff (follow-up commits to an existing MR)

```bash
BASE=$(git log --oneline | head -2 | tail -1 | cut -d' ' -f1)
git diff $BASE..HEAD > DRUPAL_ISSUES/{issue_id}/interdiff-{issue_id}.patch
```
Reference the interdiff path in the push gate summary and the draft comment.

### After Successful Push

Dispatch `drupal-pipeline-watch` in the background (project path, MR IID,
GitLab token) to monitor CI. Tell the user push is complete and pipeline
monitoring is running. Then offer: monitor pipeline / post comment / stop
DDEV (confirm before stopping) / next issue / done.

## References

Load on demand, not by default. Each entry is "open when X":

- `references/ci-parity.md` — Step 0 reports failures you need to diagnose, or you need the full `local_ci_mirror.sh` flag list.
- `references/testing-patterns.md` — writing a new PHPUnit test and need a Drupal-specific pattern (kernel boot, entity setup, schema fixtures).
- `references/smoke-testing.md` — need curl/drush eval smoke-test patterns for runtime verification outside PHPUnit.
- `references/common-checks.md` — fix touches an area you don't immediately know how to verify (caches, routes, permissions).
- `references/core-testing.md` — fix is in Drupal core, not contrib (stricter test conventions).
- `references/issue-status-codes.md` — need to set issue status correctly ("Needs work" vs "Needs review" vs "RTBC").
- `references/patch-conventions.md` — maintainer asks for a patch file instead of an MR (legacy workflow).
- `references/hack-patterns.md` — you suspect your fix is a shortcut reviewers commonly reject.
- `agents/reviewer-prompt.md`, `agents/verifier-prompt.md` — templates filled with `[BRACKETED]` context vars when dispatching the review/verify agents.
- `examples/sample-report.md` — need a complete report example to mimic.
- `modes/{preflight,package,test,reroll}.md` — command reference for each mode.

## Handoffs

| When | Skill | Purpose |
|------|-------|---------|
| Need environment setup first | `/drupal-issue-review` | Scaffold DDEV, reproduce, verify |
| Drafting the push comment | `/drupal-issue-comment` | Auto-invoked at Step 6 |

