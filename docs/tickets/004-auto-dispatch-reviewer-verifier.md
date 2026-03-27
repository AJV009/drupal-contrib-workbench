# TICKET-004: Auto-Dispatch Reviewer and Verifier Agents

**Status:** COMPLETED
**Priority:** P1 (High)
**Affects:** `.claude/skills/drupal-contribute-fix/SKILL.md`, `.claude/skills/drupal-issue-review/SKILL.md`
**Type:** Bug / Enhancement

## Problem

The `drupal-reviewer` and `drupal-verifier` agents exist and are documented in CLAUDE.md, but in the #3579478 session, **neither was ever dispatched**. The main session did all code review and verification itself, consuming its own context window and taking ~40 minutes of iterative work.

The `drupal-contribute-fix` skill has a "Pre-Push Review Loop" section that says:

> For large changes (>3 files or >100 lines): dispatch `drupal-reviewer` agent

The #3579478 session had 6 files changed and 839 insertions. This clearly exceeded the threshold, but the reviewer was never dispatched.

The verifier agent was also never used. The main session ran `ddev drush eval` commands and phpunit itself instead of delegating.

## Why This Matters

1. **Context window bloat:** The main session loaded all test files, source files, PHPCS output, and test results into its own context. Delegating to agents keeps the main session's context clean for orchestration.

2. **Quality:** The reviewer agent has a specific checklist (8 categories) and red flags list. The main session's ad-hoc review may miss things the structured agent would catch.

3. **Speed:** Reviewer and verifier can run in parallel (reviewer reads code, verifier runs tests). Currently they are sequential because the main session does both.

4. **Consistency:** Every contribution should get the same review quality. Agent-based review is reproducible; ad-hoc main-session review varies.

## Current Behavior

The skills mention the agents but use weak language ("optionally", "for large changes"):

From `drupal-contribute-fix`:
```
3. For large changes (>3 files or >100 lines): dispatch `drupal-reviewer` agent
```

From `drupal-issue-review`:
```
#### Handoffs (What To Do Next):
- **Code review** -> `drupal-reviewer` agent
- **Verify fix** -> `drupal-verifier` agent
```

These are listed as options, not requirements. The main session routinely skips them.

## Desired Behavior

Make agent dispatch mandatory at specific gates:

```
After writing any code changes (fixes or tests):
  1. ALWAYS dispatch drupal-reviewer agent
  2. ALWAYS dispatch drupal-verifier agent
  3. Both can run in parallel
  4. Wait for both to complete
  5. If reviewer says NEEDS_WORK: fix issues, re-dispatch (max 2 iterations)
  6. If verifier says FAILED: investigate, fix, re-dispatch (max 2 iterations)
  7. Only proceed to push gate when both report APPROVED/VERIFIED
```

## Implementation Plan

### 1. Update `drupal-contribute-fix` skill

Replace the optional language in "Pre-Push Review Loop" with mandatory dispatch:

```markdown
## Pre-Push Quality Gate (MANDATORY)

After all code changes are complete and PHPCS passes:

1. Dispatch `drupal-reviewer` agent (in worktree or current dir)
   - Pass: list of changed files, module path, PHPCS results
   - Wait for: APPROVED | NEEDS_WORK | CONCERNS

2. Dispatch `drupal-verifier` agent (needs DDEV running)
   - Pass: module path, test file paths, DDEV project name
   - Wait for: VERIFIED | FAILED | BLOCKED

3. Both agents can run in parallel (use run_in_background for one)

4. Handle results:
   - Both APPROVED/VERIFIED: proceed to push gate
   - NEEDS_WORK: fix issues from reviewer, re-run PHPCS, re-dispatch reviewer
   - FAILED: investigate verifier output, fix, re-dispatch verifier
   - CONCERNS: include in push gate summary for user to review
   - BLOCKED: report to user, do not proceed
   - Max 2 fix-and-re-dispatch cycles. After that, present to user.
```

### 2. Update `drupal-issue-review` skill

Add mandatory verification after reproduction:

```markdown
After reproducing the bug or verifying the MR fix:

1. Dispatch `drupal-verifier` agent to independently confirm findings
2. If verifier disagrees with your findings, investigate the discrepancy
3. Use verifier's structured output in the summary
```

### 3. Update agent prompts to accept structured input

The reviewer and verifier agents should accept specific context to avoid re-discovery:

```markdown
## Input (provided by caller)

- Module path: {path}
- Changed files: {list}
- PHPCS result: PASS/FAIL
- Test result: X/Y passing
- DDEV project: d{issue_id}
- Specific concerns to check: {list from static review}
```

### 4. Add reviewer/verifier verdicts to push gate summary

The push gate summary (from TICKET-001) should include:

```
## Quality Gate Results
- Reviewer: APPROVED (no issues found)
- Verifier: VERIFIED (24/24 tests pass, service loads, config correct)
```

## Acceptance Criteria

- [ ] Reviewer agent is dispatched for every code change before push
- [ ] Verifier agent is dispatched for every code change before push
- [ ] Both run in parallel when possible
- [ ] NEEDS_WORK/FAILED results trigger automatic fix-and-retry (max 2)
- [ ] Push gate summary includes both agent verdicts
- [ ] No code reaches push gate without passing both agents

## Files to Modify

1. `.claude/skills/drupal-contribute-fix/SKILL.md` - Make Pre-Push Review Loop mandatory
2. `.claude/skills/drupal-issue-review/SKILL.md` - Add mandatory verification after reproduction
3. `.claude/agents/drupal-reviewer.md` - Accept structured input context
4. `.claude/agents/drupal-verifier.md` - Accept structured input context
