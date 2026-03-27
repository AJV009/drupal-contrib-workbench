# TICKET-016: Lightweight Review-Only Path (No DDEV Required)

**Status:** COMPLETED
**Priority:** P3 (Low)
**Affects:** `.claude/skills/drupal-issue/SKILL.md`, `.claude/skills/drupal-issue-review/SKILL.md`
**Type:** Enhancement

## Problem

When the action is "review existing MR" and the reviewer only needs to check code quality (not reproduce a bug or run tests), the current workflow still scaffolds a full DDEV environment. This takes 3-4 minutes and is unnecessary for:

- Architecture review (DI patterns, service design)
- Security review (input handling, access control)
- Standards review (PHPCS, PHPDoc, naming)
- Logic review (algorithm correctness, edge cases)

These can all be done by reading the MR diff. DDEV is only needed when:
- Running tests
- Reproducing a bug
- Verifying functional behavior
- Checking config entity behavior

## Proposed: Two Review Modes

### Mode 1: Full Review (Current, with DDEV)

Use when:
- Bug reproduction needed
- Tests need to run
- Functional verification required
- Config/entity behavior needs checking

### Mode 2: Code Review Only (New, no DDEV)

Use when:
- MR already has passing pipeline
- Review is for code quality, not bug verification
- The issue is a feature (not a bug) and just needs review
- Maintainer asked for "code review" specifically

Workflow:
```
1. Fetch MR diff (already done by fetcher agent)
2. Read diff
3. Apply coding standards checklist
4. Apply security checklist
5. Check DI/architecture patterns
6. Check test coverage adequacy
7. Dispatch reviewer agent (works on diff, no DDEV)
8. Draft comment with findings
9. Done (no push gate, no code changes)
```

Time: ~5-10 minutes vs ~20+ minutes for full review.

## Implementation Plan

### 1. Add mode detection to `/drupal-issue`

```markdown
## Review Mode Detection

When classifying as category B (review/test MR) or I (re-review):

Check these signals to determine if DDEV is needed:
- Pipeline status: if passing, DDEV less critical
- Issue category: bug (DDEV needed) vs feature (maybe not)
- User request: "review the code" (no DDEV) vs "test the fix" (DDEV)
- Reviewer feedback: "check the logic" (no DDEV) vs "verify it works" (DDEV)

If DDEV not needed:
- Skip /drupal-issue-review DDEV phases
- Go directly to static code review
- Dispatch reviewer agent with diff only
```

### 2. Add "code-review-only" path to `/drupal-issue-review`

```markdown
## Code Review Only Mode

When DDEV is not required (no bug reproduction, no test execution):

1. Read the full MR diff from artifacts
2. Perform static review:
   - Coding standards (visual, no PHPCS without installed code)
   - Security patterns
   - Architecture / DI patterns
   - Test coverage assessment
3. Dispatch reviewer agent with diff
4. Draft comment with findings
5. Skip: DDEV setup, test execution, functional verification
```

## Acceptance Criteria

- [ ] Review-only mode available for MRs that don't need reproduction
- [ ] Mode auto-detected based on issue signals
- [ ] Review-only completes in under 10 minutes
- [ ] Full review remains available when DDEV is needed
- [ ] User can force either mode

## Files to Modify

1. `.claude/skills/drupal-issue/SKILL.md` - Add review mode detection
2. `.claude/skills/drupal-issue-review/SKILL.md` - Add code-review-only path
