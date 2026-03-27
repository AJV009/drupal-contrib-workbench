# TICKET-022: Verification Gate Pattern (Evidence Before Claims)

**Status:** COMPLETED
**Priority:** P1 (High)
**Affects:** All workflow skills
**Inspired by:** Superpowers `verification-before-completion` skill
**Type:** Enhancement

## Pattern from Superpowers

Superpowers has a dedicated skill that enforces: **No completion claims without fresh verification evidence.**

The gate function:
1. **IDENTIFY:** What command proves this claim?
2. **RUN:** Execute FULL command (fresh, complete)
3. **READ:** Full output, check exit code, count failures
4. **VERIFY:** Does output confirm claim?
5. **ONLY THEN:** Make the claim WITH EVIDENCE

Forbidden patterns:
- Using "should", "probably", "seems to"
- Expressing satisfaction before verification
- Trusting agent success reports without independent verification
- About to commit/push without verification

## What We Have Now

Our skills say "run PHPCS" and "run tests" but don't enforce the verification gate pattern. In the #3579478 session:

- Tests were run multiple times, but the FINAL run's output was consumed by context; the push happened based on "I already ran them and they passed" (memory, not fresh evidence).
- PHPCS was run but the path was wrong the first time. The retry succeeded, but there's no gate ensuring the FINAL state is verified.

## The Verification Gate

Add to every skill that makes completion claims:

```markdown
## Verification Gate (MANDATORY Before Any Completion Claim)

Before claiming ANY of the following, you MUST have FRESH evidence:

| Claim | Required Evidence | NOT Sufficient |
|-------|-------------------|----------------|
| "Tests pass" | Test output showing 0 failures (from THIS run) | "I ran them earlier" |
| "PHPCS clean" | PHPCS output showing 0 errors (from THIS run) | "I fixed the issues" |
| "Fix works" | Test/drush output confirming behavior | "The code looks correct" |
| "No regressions" | Full test suite output (not just new tests) | "Only changed X file" |
| "Tests are legitimate" | Stash validation showing tests fail without fix | "Tests cover the changes" |
| "Ready to push" | ALL of the above, fresh, in this message | Previous messages |

### The Rule

If your most recent message does not contain the ACTUAL OUTPUT of the
verification command, you have not verified. Run it again.

### Fresh Means Fresh

"I ran PHPCS 10 minutes ago" is not fresh. Between then and now, you
may have edited files. Run it again. The cost of re-running a 2-second
command is zero. The cost of pushing broken code is hours.
```

## Implementation Plan

### 1. Add verification gate to `/drupal-contribute-fix`

Before the push gate summary:

```markdown
## Pre-Push Verification (MANDATORY)

Run these commands and include their output in the push gate summary:

1. PHPCS:
   ```bash
   ddev exec ../vendor/bin/phpcs --standard=Drupal,DrupalPractice [changed files]
   ```
   Required: 0 errors, 0 warnings

2. PHPUnit (all module tests, not just new ones):
   ```bash
   ddev exec ../vendor/bin/phpunit modules/contrib/{module}/tests/
   ```
   Required: 0 failures, 0 errors

3. Test validation (TICKET-006):
   Required: New tests fail without fix

4. Drush cache rebuild:
   ```bash
   ddev drush cr
   ```
   Required: No errors

Include the ACTUAL OUTPUT of each command in the push gate summary.
Not a summary. Not "tests pass." The output.
```

### 2. Add verification to agent results

When the controller receives an agent result:

```markdown
## Agent Result Verification

Do NOT trust agent self-reports at face value. For critical claims:
- Agent says "all tests pass" → Re-run tests independently
- Agent says "PHPCS clean" → Re-run PHPCS independently
- Agent says "fix works" → Run drush eval to verify independently

Trust but verify. Agent context may have drifted.
```

### 3. Forbidden language enforcement

```markdown
## Forbidden Language in Completion Claims

NEVER use these phrases unless accompanied by evidence:
- "should work"
- "probably fine"
- "seems correct"
- "looks good"
- "I believe"
- "as we saw earlier"
- "from the previous run"

ALWAYS use these instead:
- "Output shows: [actual output]"
- "Exit code: 0"
- "PHPCS reports: 0 errors, 0 warnings"
- "PHPUnit: 24 tests, 56 assertions, 0 failures"
```

## Acceptance Criteria

- [ ] Verification gate runs fresh commands before every push gate
- [ ] Push gate summary includes actual command output (not summaries)
- [ ] Agent results independently verified for critical claims
- [ ] Forbidden language patterns documented
- [ ] No "should work" in any completion claim

## Files to Modify

1. `.claude/skills/drupal-contribute-fix/SKILL.md` - Add verification gate
2. `.claude/skills/drupal-issue/SKILL.md` - Add agent verification protocol
3. `.claude/skills/drupal-issue-review/SKILL.md` - Add verification for reproduction claims
