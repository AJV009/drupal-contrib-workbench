# TICKET-005: Split drupal-contribute-fix Into Focused Modes

**Status:** COMPLETED
**Priority:** P1 (High)
**Affects:** `.claude/skills/drupal-contribute-fix/SKILL.md`
**Type:** Refactor

## Problem

The `drupal-contribute-fix` skill is 29KB in a single SKILL.md file. Every invocation loads the entire 29KB into context, even when only one mode is needed. The skill has 4 distinct modes (preflight, package, test, reroll), 7 phases, 4 exit codes, a false-positive guard, local CI parity instructions, reroll instructions, and extensive reference file listings.

Most invocations only need 1 of the 4 modes. Loading the full 29KB wastes context tokens and increases the chance of the model getting confused by irrelevant instructions.

## Size Breakdown (Estimated)

| Section | Approx Size | Used By |
|---------|-------------|---------|
| Common (trigger rules, iron laws, Git workflow) | ~5KB | All modes |
| Preflight mode | ~4KB | preflight only |
| Package mode | ~6KB | package only |
| Test (RTBC comment) mode | ~3KB | test only |
| Reroll (legacy patches) mode | ~3KB | reroll only |
| Reference file listings | ~3KB | Varies |
| Agent dispatch rules | ~3KB | package + preflight |
| Local CI parity | ~2KB | Rarely used |

## Proposed Structure

Split into a router skill + mode-specific files:

```
.claude/skills/drupal-contribute-fix/
  SKILL.md              (router: ~5KB, common rules + mode detection)
  modes/
    preflight.md        (~4KB, search-only mode)
    package.md          (~6KB, generate artifacts mode)
    test.md             (~3KB, RTBC comment mode)
    reroll.md           (~3KB, legacy patch mode)
  agents/
    reviewer-prompt.md  (unchanged)
    verifier-prompt.md  (unchanged)
  scripts/
    contribute_fix.py   (unchanged)
    fetch_issue.py      (unchanged)
  references/           (unchanged, loaded on-demand)
  lib/                  (unchanged)
```

### Router SKILL.md Content

The main SKILL.md becomes a lightweight router:

```markdown
## Mode Detection

Determine which mode to use:

| Signal | Mode |
|--------|------|
| "search for existing fix" or first encounter with bug | preflight |
| Code changes made, ready to generate artifacts | package |
| Testing someone else's MR for RTBC | test |
| Legacy patch needs rerolling | reroll |

## Common Rules (All Modes)
[Iron laws, git workflow, security handling, dependency rules]

## Mode Execution
Once mode is determined, read the appropriate mode file:
- Preflight: Read `modes/preflight.md` and follow its instructions
- Package: Read `modes/package.md` and follow its instructions
- Test: Read `modes/test.md` and follow its instructions
- Reroll: Read `modes/reroll.md` and follow its instructions
```

### Mode File Format

Each mode file contains:
1. When this mode applies
2. Step-by-step instructions
3. Script commands specific to this mode
4. Output format
5. What to do next (handoff rules)

## Benefits

1. **Context savings:** ~15-20KB saved per invocation (only load router + 1 mode)
2. **Clarity:** Each mode file is self-contained and easy to understand
3. **Maintainability:** Can update one mode without risking others
4. **Testability:** Can invoke a specific mode file for testing

## Risks

1. Common rules must be in the router, not duplicated across modes
2. If the model fails to read the mode file, it falls back to nothing (mitigate: include "MUST read mode file" language)
3. Reference files are already separate; no change needed there

## Implementation Plan

1. Extract each mode's instructions from SKILL.md into separate `modes/*.md` files
2. Reduce SKILL.md to router + common rules
3. Ensure each mode file has clear entry/exit conditions
4. Test by invoking each mode in isolation
5. Verify that no instructions were lost in the split

## Acceptance Criteria

- [ ] SKILL.md is under 8KB
- [ ] Each mode file is under 7KB
- [ ] All 4 modes work correctly when invoked
- [ ] No instructions lost from the original 29KB skill
- [ ] Common rules (iron laws, git workflow) are in the router, not duplicated
- [ ] Reference files remain separate and on-demand

## Files to Modify

1. `.claude/skills/drupal-contribute-fix/SKILL.md` - Reduce to router
2. `.claude/skills/drupal-contribute-fix/modes/preflight.md` - NEW
3. `.claude/skills/drupal-contribute-fix/modes/package.md` - NEW
4. `.claude/skills/drupal-contribute-fix/modes/test.md` - NEW
5. `.claude/skills/drupal-contribute-fix/modes/reroll.md` - NEW
