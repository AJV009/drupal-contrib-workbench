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
  version: "1.8.0"
---

# drupal-contribute-fix

> **IRON LAW:** NO CODE PUSHED WITHOUT KERNEL TESTS. Every fix MUST include tests that fail against pre-fix code and pass against fixed code.

> **IRON LAW (TDD):** NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST. Write the test, watch it fail, write the minimal fix, watch it pass. In that order.

> **IRON LAW (DEBUGGING):** NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST. Read the error message. Reproduce consistently. Check recent changes. Then fix.

> **IRON LAW (VERIFICATION):** NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE. Run PHPCS. Run tests. See them pass. Only then say "done."

## Attempt state check (MANDATORY first action)

Before running anything, check whether this is a fresh run or a re-run after a
post-fix gate failure. Read `DRUPAL_ISSUES/{issue_id}/workflow/attempt.json` if
it exists:

```bash
if [ -f "$CLAUDE_PROJECT_DIR/DRUPAL_ISSUES/{issue_id}/workflow/attempt.json" ]; then
  cat "$CLAUDE_PROJECT_DIR/DRUPAL_ISSUES/{issue_id}/workflow/attempt.json"
fi
```

Expected shape:
```json
{
  "current_attempt": 2,
  "approach": "architectural",
  "recovery_brief_path": "DRUPAL_ISSUES/{issue_id}/workflow/02c-recovery-brief.md"
}
```

**Branching:**
- If no `attempt.json` exists, or `current_attempt == 1`: this is a fresh run.
  Proceed with preflight + Step 0.5 (pre-fix gate) normally.
- If `current_attempt == 2`: this is a rerun after a failed post-fix gate.
  - **Skip preflight** (already done, `UPSTREAM_CANDIDATES.json` is still valid).
  - **Skip Step 0.5 (pre-fix gate)** (the recovery brief at
    `recovery_brief_path` IS the pre-fix analysis — re-running opus risks
    flip-flopping between attempts).
  - Read the recovery brief and use it as the fix plan.
  - Jump directly into the TDD loop with the architectural approach.
- If `current_attempt >= 3`: **FATAL**. The circuit breaker should have fired
  at the end of attempt 2 and escalated to the user. If you see this, STOP
  and report the state to the user. Do not attempt a third run.

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
| "I already know the architectural option won't work for this module" | The pre-fix gate exists because that confidence is exactly the anchoring bias we're fighting. Run the gate. If you're right, it'll say narrow. |

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

## Step 0.5: Pre-fix solution-depth gate (MANDATORY)

After preflight returns (exit 0) and before any test or code is written, dispatch
the `drupal-solution-depth-gate-pre` agent. This forces a genuine narrow-vs-
architectural comparison before the workflow commits to an approach.

> **IRON LAW:** NO FIX WITHOUT PRE-FIX DEPTH ANALYSIS. Every autonomous run goes
> through Step 0.5. The gate is non-negotiable even on seemingly trivial fixes.

### When to skip

Skip Step 0.5 **only** when `workflow/attempt.json` shows `current_attempt == 2`
(this is the architectural rerun after a failed post-fix gate — the recovery
brief replaces the pre-fix analysis). See "Attempt state check" at the top of
this file.

### Dispatch

```
Dispatch: drupal-solution-depth-gate-pre
Inputs:
  issue_id = {issue_id}
  artifacts_dir = $CLAUDE_PROJECT_DIR/DRUPAL_ISSUES/{issue_id}/artifacts
  review_summary_path = $CLAUDE_PROJECT_DIR/DRUPAL_ISSUES/{issue_id}/workflow/01-review-summary.json
  depth_signals_path = $CLAUDE_PROJECT_DIR/DRUPAL_ISSUES/{issue_id}/workflow/01a-depth-signals.json
```

The agent writes:
- `DRUPAL_ISSUES/{issue_id}/workflow/01b-solution-depth-pre.md` (human-readable)
- `DRUPAL_ISSUES/{issue_id}/workflow/01b-solution-depth-pre.json` (machine-readable)
- `bd update <bd-id> --design ...` (best-effort)

**bd write (best-effort):** Mirror the pre-fix analysis to bd:

```bash
BD_ID=$(scripts/bd-helpers.sh ensure-issue "$ISSUE_ID" "Drupal issue $ISSUE_ID" 2>/dev/null)
if [[ -n "$BD_ID" ]] && [[ -f "$WORKFLOW_DIR/01b-solution-depth-pre.json" ]]; then
  scripts/bd-helpers.sh phase-depth-pre "$BD_ID" "$WORKFLOW_DIR/01b-solution-depth-pre.json"
fi
```

And returns `SOLUTION_DEPTH_PRE: decision={narrow|architectural|hybrid} must_run_post_fix={true|false}`.

### What the controller does with the result

1. **Read `01b-solution-depth-pre.md` in full before writing any test or code.**
   The narrow/architectural trade-off table is the plan for what you're about to
   implement.
2. **Honor the `decision` field.** If the gate says `architectural`, you write
   the architectural fix. If it says `hybrid`, you write the narrow fix now and
   file the architectural follow-up via `bd issue create --dep
   "discovered-from:bd-<this>"` at the end.
3. **Remember `must_run_post_fix`.** Stash its value so you know to run Step 2.5
   post-fix gate unconditionally, regardless of patch size.

### What if the review-summary / depth-signals files don't exist?

If `workflow/01-review-summary.json` or `workflow/01a-depth-signals.json` is
missing — e.g., because `/drupal-contribute-fix` was invoked directly without
first running `/drupal-issue-review` — create minimal versions from what you
know and dispatch the gate anyway:

```bash
mkdir -p "$CLAUDE_PROJECT_DIR/DRUPAL_ISSUES/{issue_id}/workflow"
cat > "$CLAUDE_PROJECT_DIR/DRUPAL_ISSUES/{issue_id}/workflow/01-review-summary.json" <<'JSON'
{
  "issue_id": {issue_id},
  "category": "unknown",
  "module": "{module}",
  "module_version": "{version}",
  "reproduction_confirmed": false,
  "existing_mr": null,
  "static_review_findings": []
}
JSON

cat > "$CLAUDE_PROJECT_DIR/DRUPAL_ISSUES/{issue_id}/workflow/01a-depth-signals.json" <<JSON
{
  "category": "unknown",
  "resonance_bucket": "NONE",
  "resonance_report_path": null,
  "reviewer_narrative": "No prior review; /drupal-contribute-fix invoked directly",
  "recent_maintainer_comments": $(jq '[.[-5:] | .[] | {author, date: .created, body}]' "$CLAUDE_PROJECT_DIR/DRUPAL_ISSUES/{issue_id}/artifacts/comments.json" 2>/dev/null || echo '[]'),
  "proposed_approach_sketch": "none — direct invocation"
}
JSON
```

The gate will still produce a depth analysis; it just won't have review-phase
signals to lean on.

### Rationalization Prevention (Pre-fix Gate)

| Thought | Reality |
|---|---|
| "This fix is 5 lines, skip the gate" | Step 0.5 is mandatory. 5-line fixes still have a narrow-vs-architectural question. |
| "I already know what the architectural alternative is" | You know what you ANCHORED on. The fresh subagent may see one you missed. |
| "Dispatching another agent is slow" | Opus runtime for pre-fix is ~60 seconds. That's cheaper than reverting after push. |

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

## Testing, Pre-Push Quality Gate, and Post-Fix Depth Gate

> **Load on demand:** See `references/testing-and-push-gate.md` for the full
> testing workflow (TDD Steps 1-3), Pre-Push Quality Gate (CI parity, PHPCS,
> PHPUnit), and the post-fix solution-depth gate (Step 2.5) with its
> compute-stats / should-run / dispatch-or-skip logic.

## Failure Path, Recovery Brief, Circuit Breaker, and Push Gate

> **Load on demand:** See `references/failure-path-and-push-gate.md` for the
> full failure path (recovery brief template, attempt-1 diff preservation,
> destructive revert, attempt.json write, re-invoke), the circuit breaker at
> attempt 2, Step 5.5 (push-gate checklist + bd writes), and the Push Gate
> (THE ONLY STOP POINT — never auto-push, present summary, wait for user).

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

