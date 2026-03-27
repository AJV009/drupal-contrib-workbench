# TICKET-003: Parallel DDEV Setup and Static Code Review

**Status:** COMPLETED
**Priority:** P1 (High)
**Affects:** `.claude/skills/drupal-issue-review/SKILL.md`
**Type:** Enhancement

## Problem

In the #3579478 session, the `drupal-ddev-setup` agent took ~3.5 minutes to scaffold the environment. During this time, the main session was largely idle. It had already fetched the MR diff (15KB patch, 6 files) and could have been reviewing it.

This is 3.5 minutes of completely wasted time. Code review of a diff requires no running Drupal environment. It is pure static analysis.

## Current Behavior

```
[Sequential]
1. Read issue + classify          (~2 min)
2. Dispatch DDEV setup agent      (~3.5 min, blocking)
3. Wait for DDEV to complete      (idle)
4. Verify environment             (~30 sec)
5. Run tests                      (~2 min)
6. Review code                    (~10 min)
7. Write fixes + tests            (~40 min)
```

Total wall time for phases 1-6: ~18 minutes

## Desired Behavior

```
[Parallel where possible]
1. Read issue + classify          (~2 min)
2. SIMULTANEOUSLY:
   a. Dispatch DDEV setup agent   (~3.5 min, background)
   b. Static code review of diff  (~5 min, foreground)
   c. Search for related issues   (~1 min, background agent)
3. When DDEV ready: run tests     (~2 min)
4. Write fixes + tests            (~40 min)
```

Total wall time for phases 1-3: ~7 min (saved ~11 min by parallelizing)

## What Can Run Without DDEV

These activities require only the MR diff file (already fetched by the issue-fetcher agent):

1. **Static code review of the diff:**
   - Coding standards compliance (visual inspection, not PHPCS which needs installed code)
   - Security patterns (SQL injection, XSS, access control)
   - Architecture review (DI patterns, service usage)
   - API compatibility check
   - PHPDoc completeness
   - Type safety review

2. **Related issue search:**
   - Search drupal.org for similar issues in the same module
   - Check for parent/child/blocking issues
   - Look for duplicate reports

3. **Test coverage gap analysis:**
   - From the diff, identify new/changed methods
   - Determine which code paths need test coverage
   - Scaffold test stubs (actual test execution needs DDEV)

4. **Comment thread analysis:**
   - Extract reviewer feedback from previous comments
   - Identify maintainer requests
   - Note any architectural decisions made in discussion

## Implementation Plan

### 1. Update `/drupal-issue-review` to specify parallel phases

Add a "Parallel Execution" section:

```markdown
## Parallel Execution (MANDATORY)

When setting up an environment AND reviewing an MR, these phases MUST
run in parallel:

### Background (dispatched as agents):
- DDEV setup agent (drupal-ddev-setup)
- Related issue search (if requested)

### Foreground (main session, while DDEV sets up):
- Read the full MR diff
- Perform static code review:
  - Security patterns (check references/security-patterns.md)
  - DI compliance (no \Drupal:: static calls)
  - Type safety (strict_types, type hints)
  - PHPDoc completeness
  - Architecture concerns
- Analyze test coverage gaps from the diff
- Extract key context from comment thread
- Prepare list of things to verify once DDEV is ready

### After DDEV Ready:
- Run PHPCS on actual files
- Run existing tests
- Verify static review findings with running code
- Execute reproduction steps
```

### 2. Add diff-based review checklist to the skill

```markdown
## Static Diff Review Checklist

For each file in the diff, check:
- [ ] declare(strict_types=1) present (new PHP files)
- [ ] No \Drupal:: static calls in services/controllers
- [ ] Constructor injection used correctly
- [ ] PHPDoc on all public methods
- [ ] $this->t() for user-facing strings
- [ ] No hardcoded credentials or paths
- [ ] Proper exception handling (not swallowing errors)
- [ ] Access checks on new routes
- [ ] Cache metadata on render arrays
- [ ] Entity ID constraints respected (64 char max for config entities)
- [ ] Input validation at system boundaries
```

### 3. Modify the skill to use `run_in_background: true` for DDEV agent

The DDEV agent dispatch should explicitly use background mode so the main session can continue working:

```markdown
Dispatch the drupal-ddev-setup agent with run_in_background: true.
While it runs, begin the static code review phase immediately.
You will be notified when the agent completes.
```

## Acceptance Criteria

- [ ] DDEV setup runs in background while main session reviews the diff
- [ ] Static code review findings are documented before DDEV is ready
- [ ] No idle waiting for DDEV setup to complete
- [ ] Wall time for "classify + setup + initial review" is under 8 minutes (down from ~18)
- [ ] Related issue search runs in parallel when requested

## Files to Modify

1. `.claude/skills/drupal-issue-review/SKILL.md` - Add parallel execution section, diff review checklist
