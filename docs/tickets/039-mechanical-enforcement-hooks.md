# TICKET-039: Mechanical Enforcement Hooks + bd Session Progress

**Status:** COMPLETED
**Priority:** P1
**Affects:** `.claude/hooks/`, `.claude/settings.json`, `/drupal-contribute-fix` SKILL.md
**Type:** Enhancement
**Depends on:** 033 (research verdict: ADOPT hooks only)

## Problem

The verification gate (ticket 022) and push gate IRON LAW are prose-only.
Session 9b75cb81 proved prose enforcement leaks: the workflow proposed
mocks despite IRON LAWS. Ticket 033 research confirmed that Claude Code
hooks with exit code 2 mechanically block actions.

## Solution

Two hooks:
1. **PreToolUse → push-gate.sh**: blocks `git push` without a clean
   `03-push-gate-checklist.json`
2. **Stop → workflow-completion.sh**: blocks stop mid-fix-workflow if
   review happened but push gate wasn't reached

Both write bd memories for cross-session progress tracking (best-effort).

## Resolution (2026-04-10)

Shipped with both hooks + bd writes. All 10 acceptance criteria pass.

### What shipped

- `.claude/hooks/push-gate.sh` (50 lines) — PreToolUse gate on git push
- `.claude/hooks/workflow-completion.sh` (37 lines) — Stop gate on workflow completion
- `.claude/settings.json` — PreToolUse + Stop entries added alongside existing SessionStart/PreCompact
- `.claude/skills/drupal-contribute-fix/SKILL.md` — Step 5.5: Write push-gate checklist (MANDATORY)
- `docs/workflow-state-files.md` — `03-push-gate-checklist.json` row added
- `docs/bd-schema.md` — 3 new phase notation prefixes
- `CLAUDE.md` — "Mechanical enforcement hooks" subsection

### Acceptance results

| # | Criterion | Result |
|---|---|---|
| 1 | git push blocked without checklist | PASS — exit 2, stderr message |
| 2 | git push blocked with NEEDS_WORK verdict | PASS — exit 2, shows failing field |
| 3 | git push passes with clean checklist | PASS — exit 0 |
| 4 | Stop blocked mid-fix-workflow | PASS — exit 2, stderr message |
| 5 | Stop passes when not in fix workflow | PASS — exit 0 |
| 6 | Stop passes when workflow complete | PASS — exit 0 |
| 7 | bd writes on push block | See Task 9 results |
| 8 | bd writes on session stop | See Task 9 results |
| 9 | Existing hooks still work | PASS — SessionStart/PreCompact preserved in settings.json |
| 10 | Step 5.5 in SKILL.md | PASS — wiring verified |

### Key design decisions

1. **PreToolUse over TaskCompleted.** TaskCompleted doesn't fire in our
   skill-based workflow (no explicit tasks created). PreToolUse fires on
   every tool call and can gate `git push` directly.
2. **Stop hook for "claiming done" enforcement.** Uses 120-min recency
   window on `01-review-summary.json` to avoid blocking unrelated sessions.
3. **60-min freshness on push checklist.** Prevents a stale checklist from
   issue A from greenlighting a push for issue B.
4. **bd writes are best-effort.** `2>/dev/null || true` — bd failure never
   blocks the hook's primary gate function.
