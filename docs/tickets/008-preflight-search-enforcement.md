# TICKET-008: Enforce Preflight Search Before Any Code Changes

**Status:** COMPLETED
**Priority:** P1 (High)
**Affects:** `.claude/skills/drupal-contribute-fix/SKILL.md`, `.claude/skills/drupal-issue/SKILL.md`
**Type:** Bug

## Problem

The `drupal-contribute-fix` skill has a MANDATORY preflight phase:

> FIRST STEP: Preflight (MANDATORY Before Any Code)

In the #3579478 session, this was completely skipped. The session went directly from "review MR" to "write additional fixes and tests" without ever running:

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" preflight \
  --project ai_provider_litellm \
  --keywords "entity ID length guardrails error propagation" \
  --out .drupal-contribute-fix
```

This means:
- No search for existing upstream fixes
- No check for duplicate issues
- No check if someone else already identified these problems
- No UPSTREAM_CANDIDATES.json generated

The preflight search exists to prevent duplicate work. If someone else had already filed a separate issue about entity ID truncation, we'd have created a duplicate fix.

## Root Cause

The skill says "MANDATORY Before Any Code" but this instruction is in the `drupal-contribute-fix` skill. The actual code changes in #3579478 were initiated from within the `/drupal-issue-review` workflow, which doesn't mention preflight. The review skill found issues during code review and started fixing them without ever invoking `drupal-contribute-fix`'s preflight.

The gap: **code changes can originate from `/drupal-issue-review` without ever passing through `/drupal-contribute-fix`'s preflight gate.**

## Desired Behavior

Preflight must run before ANY code change to contrib/core files, regardless of which skill initiated the change.

```
[Any skill] -> "I want to change contrib code"
  -> MUST invoke preflight search first
  -> IF upstream fix exists: STOP, report to user
  -> IF no upstream fix: proceed with changes
```

## Implementation Plan

### 1. Add preflight gate to `/drupal-issue-review`

When the review skill discovers issues that need fixing:

```markdown
## Before Writing Fixes

If during review you identify issues that need code changes:

1. STOP. Do not write code yet.
2. Run preflight search via drupal-contribute-fix:
   ```bash
   python3 "$DCF_ROOT/scripts/contribute_fix.py" preflight \
     --project {module} \
     --keywords "{brief description of issue found}" \
     --out .drupal-contribute-fix
   ```
3. Check UPSTREAM_CANDIDATES.json:
   - If fix exists upstream: note it in findings, do not duplicate
   - If related issue exists: reference it in your work
   - If nothing found: proceed to writing fix
4. THEN invoke /drupal-contribute-fix for the actual fix
```

### 2. Add a cross-skill guard to `/drupal-issue`

The orchestrator skill should ensure preflight runs at the right time:

```markdown
## Preflight Guard

Before delegating to /drupal-contribute-fix or allowing code changes
from /drupal-issue-review:

1. Check: has preflight been run for this issue?
   - Look for .drupal-contribute-fix/UPSTREAM_CANDIDATES.json
2. If not: run preflight first
3. If yes: proceed
```

### 3. Make preflight results part of the push gate

Include in the push gate summary:

```markdown
## Upstream Search
- Preflight search: COMPLETED
- Upstream candidates found: 0
- Duplicate issues: none
```

Or if skipped (should never happen but as a safety net):
```markdown
## Upstream Search
- WARNING: Preflight search was NOT run
- Cannot confirm no upstream fix exists
- Recommend running before pushing
```

## Acceptance Criteria

- [ ] Preflight search runs before any code changes to contrib/core, regardless of entry skill
- [ ] `/drupal-issue-review` invokes preflight when transitioning to fix mode
- [ ] Push gate summary includes preflight results
- [ ] If preflight finds an upstream fix, workflow stops and reports to user
- [ ] UPSTREAM_CANDIDATES.json is always generated before code changes

## Files to Modify

1. `.claude/skills/drupal-issue-review/SKILL.md` - Add preflight gate before fixing
2. `.claude/skills/drupal-issue/SKILL.md` - Add cross-skill preflight guard
3. `.claude/skills/drupal-contribute-fix/SKILL.md` - Ensure preflight section is clearly mandatory even when invoked from other skills
