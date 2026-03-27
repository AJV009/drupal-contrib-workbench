# TICKET-001: Make /drupal-issue Hands-Free Until Push Gate

**Status:** COMPLETED
**Priority:** P0 (Critical)
**Affects:** `.claude/skills/drupal-issue/SKILL.md`, `.claude/skills/drupal-issue-review/SKILL.md`
**Type:** Enhancement

## Problem

In the session for issue #3579478, the user had to intervene twice:
1. First interrupt at 08:30:54 (7 seconds in) because the skill was spending time on preamble (ToolSearch for TaskCreate, announcing intent) instead of doing work.
2. Second interrupt at 08:44:08 during task creation for `/drupal-issue-review`, then user re-sent with clarification.

The current flow requires user confirmation at multiple transition points:
- After issue classification ("this looks like a review/fix task, proceed?")
- After DDEV setup ("environment ready, what next?")
- After test results ("tests pass, should I push?")

The user wants ZERO interaction until the final push gate. The workflow should auto-chain through all phases and only stop when it is time to push to the issue fork.

## Current Flow (With Stops)

```
User: /drupal-issue <url>
  -> Skill announces what it will do          [STOP: preamble]
  -> Fetcher agent collects artifacts
  -> Skill reads artifacts, classifies        [STOP: asks user what to do]
  -> User says "set it up"
  -> /drupal-issue-review invoked
  -> Creates 6 tasks sequentially             [STOP: preamble]
  -> DDEV setup agent runs
  -> Main session waits idle                  [STOP: waiting]
  -> Tests run, fixes written
  -> Push happens                             [SHOULD STOP BUT DIDN'T]
```

## Desired Flow (Hands-Free)

```
User: /drupal-issue <url>
  -> Fetcher agent dispatched immediately (no preamble)
  -> Classification happens automatically
  -> Based on classification, auto-delegates to appropriate companion skill
  -> DDEV setup agent runs in background
  -> WHILE DDEV sets up: static code review of diff runs in parallel
  -> When DDEV ready: tests run, verification happens
  -> IF issues found: auto-fix, auto-test, auto-PHPCS
  -> Reviewer agent dispatched automatically
  -> Verifier agent dispatched automatically
  -> Comment drafted via /drupal-issue-comment
  -> FULL STOP: Present summary to user:
      - What was found
      - What was fixed
      - Test results
      - PHPCS results
      - Reviewer verdict
      - Verifier verdict
      - Draft comment
      - Diff of changes
      - "Ready to push to <branch>. Proceed? [y/n]"
```

## Implementation Plan

### 1. Modify `/drupal-issue` skill (SKILL.md)

Remove all "present classification and wait for user" language. Replace with:

```markdown
After classifying the action type, IMMEDIATELY delegate to the appropriate
companion skill. Do not present the classification to the user or wait
for confirmation. The only point where you stop and wait for user input
is BEFORE pushing to a remote.

Auto-chain rules:
- Category A (reproduce bug) -> auto-invoke /drupal-issue-review
- Category B (review/test MR) -> auto-invoke /drupal-issue-review
- Category C (adapt/port) -> auto-invoke /drupal-contribute-fix
- Category D (version bump) -> handle directly, stop before push
- Category E (reviewer feedback) -> handle directly, stop before push
- Category F (just reply) -> auto-invoke /drupal-issue-comment, present draft
- Category G (write fix) -> auto-invoke /drupal-issue-review then /drupal-contribute-fix
- Category H (cherry-pick) -> handle directly, stop before push
- Category I (re-review) -> auto-invoke /drupal-issue-review (lightweight)
```

### 2. Modify `/drupal-issue-review` skill (SKILL.md)

Add auto-continuation after environment setup:

```markdown
After DDEV environment is ready and tests/verification complete:
- IF issues found that need fixing: auto-invoke /drupal-contribute-fix
- IF review-only (no fixes needed): auto-invoke /drupal-issue-comment
- NEVER stop between phases to ask the user what to do next
```

### 3. Reduce preamble in all skills

Replace patterns like:
```
I'm using the drupal-issue skill to analyze issue #3579478.
Let me create tasks to track progress...
[creates 6 tasks one by one]
Now let me fetch the issue data...
```

With:
```
[immediately dispatch fetcher agent]
[create tasks in batch or lazily]
[start working]
```

### 4. Add explicit PUSH GATE to all skills that touch git

Every skill that could result in a `git push` must include:

```markdown
## Push Gate (MANDATORY)

Before ANY git push, you MUST:
1. Present a complete summary of all changes
2. Show the diff
3. Show test results
4. Show PHPCS results
5. Show the draft comment (if applicable)
6. Ask: "Ready to push to <remote>/<branch>? [y/n]"
7. Wait for explicit user confirmation
8. Only then execute git push

This is the ONLY point in the entire workflow where you stop and wait.
```

## Acceptance Criteria

- [ ] `/drupal-issue <url>` runs from start to "ready to push" with zero user interaction
- [ ] All skill transitions happen automatically based on classification
- [ ] Preamble time (from user command to first real work) is under 5 seconds
- [ ] Push gate always fires before any git push
- [ ] Summary at push gate includes: changes, diff, test results, PHPCS, reviewer/verifier verdicts, draft comment

## Files to Modify

1. `.claude/skills/drupal-issue/SKILL.md` - Remove user-confirmation stops, add auto-chain rules
2. `.claude/skills/drupal-issue-review/SKILL.md` - Remove intermediate stops, add auto-continuation
3. `.claude/skills/drupal-contribute-fix/SKILL.md` - Ensure push gate is explicit and mandatory
4. `.claude/CLAUDE.md` - Update workflow description to reflect hands-free behavior
