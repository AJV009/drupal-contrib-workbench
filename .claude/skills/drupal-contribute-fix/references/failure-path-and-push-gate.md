# Failure Path, Recovery Brief, Circuit Breaker, and Push Gate

> This file is extracted from SKILL.md for readability.
> It covers the recovery brief template (when post-fix gate returns failed-revert),
> the circuit breaker at attempt 2, Step 5.5 (push-gate checklist),
> and the Push Gate (the only stop point in the workflow).

## What the narrow attempt tried
{2-4 sentences extracted from the "Narrow approach" block of 01b-solution-depth-pre.md}

## Why it was rejected
{3-5 sentences extracted from the "Smell check" + "Architectural reconsideration" blocks of 02b-solution-depth-post.md}

## Architectural plan (for the re-run)
{The full "Architectural approach" block from 01b-solution-depth-pre.md, plus any refinements from 02b}

## Reference: narrow attempt diffs
See `.drupal-contribute-fix/attempt-1-narrow/` for the full diff, test files,
and report of the rejected attempt. Do not blindly copy — the architectural
rewrite may need different tests, different file boundaries, and different
module touchpoints.

## Constraints that carry forward
- Module: {module_name} {module_version}
- DDEV project: d{issue_id}
- Preflight verdict (still valid): {summary from UPSTREAM_CANDIDATES.json}
- Reproduction steps: {from issue, still valid}

## Constraints that are RESET
- Test suite: start fresh or adapt from attempt-1
- PHPCS / CI parity evidence: must be re-run
- Spec / code / verifier reports: must be re-dispatched
BRIEF
```

**B. Preserve attempt-1 diffs** (copy, not move):

```bash
ATTEMPT_DIR=".drupal-contribute-fix/attempt-1-narrow"
mkdir -p "$ATTEMPT_DIR"
cp -r .drupal-contribute-fix/${ISSUE_ID}-*/ "$ATTEMPT_DIR/" 2>/dev/null || true

# Capture the actual source diff as a standalone patch for reference
cd "$MODULE_PATH"
git diff > "/home/alphons/drupal/CONTRIB_WORKBENCH/$ATTEMPT_DIR/source-changes.patch"
cd - > /dev/null
```

**C. Destructive revert**, scoped to production source paths only:

```bash
cd "$MODULE_PATH"
git checkout -- .
git clean -fd -- tests/ src/ config/
cd - > /dev/null
```

**D. Write the attempt-2 state file** so the re-invocation knows what to do:

```bash
cat > "$WORKFLOW_DIR/attempt.json" <<JSON
{
  "current_attempt": 2,
  "approach": "architectural",
  "recovery_brief_path": "$WORKFLOW_DIR/02c-recovery-brief.md"
}
JSON
```

**E. Write to bd (best-effort):**

```bash
BD_ID=$(scripts/bd-helpers.sh ensure-issue "$ISSUE_ID" "Drupal issue $ISSUE_ID" 2>/dev/null)
if [[ -n "$BD_ID" ]]; then
  scripts/bd-helpers.sh phase-depth-post-fail "$BD_ID" \
    "$WORKFLOW_DIR/02b-solution-depth-post.json" \
    "$WORKFLOW_DIR/02c-recovery-brief.md"
fi
```

**F. Re-invoke `/drupal-contribute-fix`** from the top. The attempt-state
check at the top of this SKILL.md will detect `current_attempt == 2` and
skip preflight + Step 0.5, reading the recovery brief as the fix plan.

### Circuit breaker — attempt 2 failure

If the post-fix gate runs on the architectural attempt (attempt 2) and ALSO
returns `failed-revert`, DO NOT start a third attempt. Instead, STOP and
escalate to the user:

```
SOLUTION DEPTH ESCALATION — Issue #{issue_id}

Attempt 1 (narrow): failed post-fix gate, score {N1}
  → DRUPAL_ISSUES/{issue_id}/workflow/02b-solution-depth-post.md
  → .drupal-contribute-fix/attempt-1-narrow/

Attempt 2 (architectural): failed post-fix gate, score {N2}
  → DRUPAL_ISSUES/{issue_id}/workflow/02b-solution-depth-post.md (overwritten this run)
  → current working tree

Neither approach satisfied the gate. Options:
  1. Review both analyses and tell me which to keep
  2. Propose a third approach manually
  3. Abort — close DDEV, file bd follow-up

What would you like to do?
```

Wait for the user's response. Do NOT take any further automatic action.

How do you know if this is attempt 2? Check `workflow/attempt.json`:

```bash
if [ -f "$WORKFLOW_DIR/attempt.json" ]; then
  CURRENT_ATTEMPT=$(jq -r '.current_attempt' "$WORKFLOW_DIR/attempt.json")
  if [ "$CURRENT_ATTEMPT" == "2" ]; then
    echo "CIRCUIT_BREAKER: second attempt failed, escalating"
    # present the escalation block above to the user
  fi
fi
```

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

**Step 5.5: Write push-gate checklist (MANDATORY)**

After ALL three agents (spec reviewer, reviewer, verifier) have reported,
write the push-gate checklist. This file enables the mechanical push gate
hook — without it, `git push` will be blocked and Claude cannot stop.

```bash
ISSUE_ID={issue_id}
WORKFLOW_DIR="$CLAUDE_PROJECT_DIR/DRUPAL_ISSUES/$ISSUE_ID/workflow"
mkdir -p "$WORKFLOW_DIR"

jq -n \
  --argjson ci "$CI_EXIT_CODE" \
  --argjson phpunit "$PHPUNIT_PASSED" \
  --arg depth "$DEPTH_DECISION" \
  --arg spec "$SPEC_VERDICT" \
  --arg review "$REVIEWER_VERDICT" \
  --arg verify "$VERIFIER_VERDICT" \
  --arg ts "$(date -Iseconds)" \
  --arg id "$ISSUE_ID" \
  '{
    ci_parity_exit_code: $ci,
    phpunit_passed: $phpunit,
    depth_gate_decision: $depth,
    spec_reviewer_verdict: $spec,
    reviewer_verdict: $review,
    verifier_verdict: $verify,
    timestamp: $ts,
    issue_id: $id
  }' > "$WORKFLOW_DIR/03-push-gate-checklist.json"
```

Substitute the actual values from the preceding steps. The variables are
placeholders — use the real exit codes and verdict strings from Steps 0-5.

**Do NOT skip this step.** The `.claude/hooks/push-gate.sh` (PreToolUse)
and `.claude/hooks/workflow-completion.sh` (Stop) hooks enforce this
mechanically — there is no way to push or claim "done" without this file.

**bd writes (best-effort):** Mirror the verification and push-gate data to bd:

```bash
BD_ID=$(scripts/bd-helpers.sh ensure-issue "$ISSUE_ID" "Drupal issue $ISSUE_ID" 2>/dev/null)
if [[ -n "$BD_ID" ]]; then
  scripts/bd-helpers.sh phase-verification "$BD_ID" "$WORKFLOW_DIR/03-push-gate-checklist.json"
  scripts/bd-helpers.sh phase-push-gate "$BD_ID" "$WORKFLOW_DIR/03-push-gate-checklist.json"
fi
```

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
git diff $BASE..HEAD > "$CLAUDE_PROJECT_DIR/DRUPAL_ISSUES/{issue_id}/interdiff-{issue_id}.patch"
```
Reference the interdiff path in the push gate summary and the draft comment.

### After Successful Push

Dispatch `drupal-pipeline-watch` in the background (project path, MR IID,
GitLab token) to monitor CI. Tell the user push is complete and pipeline
monitoring is running. Then offer: monitor pipeline / post comment / stop
DDEV (confirm before stopping) / next issue / done.
