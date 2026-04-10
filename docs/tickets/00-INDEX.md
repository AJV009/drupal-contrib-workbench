# Workflow Improvement Tickets — Phase 2 Index

This index covers **phase 2** tickets (027+), the next round of orchestration and workflow improvements after the original 26 tickets all reached COMPLETED status.

For phase 1 (tickets 001-026), see [README.md](README.md).

## Why phase 2 exists

The original 26 tickets focused on adopting the controller pattern, structured agent returns, hands-free orchestration, and verification gates — largely inspired by the superpowers plugin. Phase 2 addresses problems that became visible only AFTER phase 1 was running in production:

1. **Cross-issue connections are still manual** — when issue A is actually a scope expansion of issue B, the user has to notice and intervene
2. **Solution depth is shallow** — the workflow proposes narrow fixes when architectural ones exist; the user has to demand "the proper way"
3. **Workflow determinism leaks** — phase artifacts (00-classification.json) are missing in 5 of the most recent worked issues despite ticket 023 being marked complete
4. **No persistent memory across sessions** — every issue starts blank; prior knowledge from related issues is not retrievable
5. **Operational sprawl** — orphaned DDEV stacks accumulate; the launcher resume path is broken (stale SESSION_DIR)

Phase 2 brings in `bd` (steveyegge/beads) as the persistent data layer, adds mechanical enforcement where prose IRON LAWS were leaking, and gates research before broad implementation.

## Tickets

| #   | Title                                                      | P  | Status      | Type         | Depends on |
|-----|------------------------------------------------------------|----|-------------|--------------|------------|
| 027 | Fix stale SESSION_DIR in drupal-issue.sh                   | P0 | COMPLETED   | Bug Fix      | —          |
| 028 | Adopt bd as workbench data store + lifecycle               | P0 | COMPLETED   | Architecture | 027        |
| 029 | Pre-classification cross-issue resonance check             | P0 | COMPLETED   | Enhancement  | 028        |
| 030 | Solution-depth gate (pre-fix AND post-fix)                 | P0 | COMPLETED   | Enhancement  | —          |
| 031 | Workflow determinism via sentinel + reinstate              | P1 | COMPLETED   | Enhancement  | 027        |
| 032 | DDEV auto-pause for orphaned stacks                        | P2 | COMPLETED   | Tooling      | —          |
| 033 | RESEARCH: Agent Teams TaskCompleted hook prototype         | P0 | COMPLETED   | Research     | —          |
| 034 | Cross-issue long-term memory via bd                        | P1 | COMPLETED   | Enhancement  | 028, 029   |
| 035 | RESEARCH: Mine orc/bernstein/kodo for launcher v2          | P0 | COMPLETED   | Research     | —          |
| 036 | Comment quality gate (anti-filler)                         | P2 | COMPLETED   | Enhancement  | —          |
| 037 | Cleanup deprecated agents/tickets/scripts                  | P3 | COMPLETED   | Cleanup      | —          |
| 038 | Session pattern evidence log (for future skill tuning)     | P3 | COMPLETED   | Knowledge    | —          |
| 039 | Mechanical enforcement hooks + bd session progress       | P1 | COMPLETED   | Enhancement  | 033        |

## Suggested execution order

Research first (per user direction: "I'd rather have research tickets pulled to the top to avoid reworking stuff later"):

### Phase 2.1 — Research (do first; informs everything else)
1. **033** — Agent Teams TaskCompleted hook prototype
2. **035** — Mine orc/bernstein/kodo for launcher v2

### Phase 2.2 — Quick wins (under 1 hour each)
3. **027** — Fix stale SESSION_DIR
4. **032** — DDEV auto-pause
5. **037** — Cleanup deprecated

### Phase 2.3 — Foundation
6. **028** — Adopt bd

### Phase 2.4 — Workflow improvements (depend on bd)
7. **031** — Sentinel + reinstate
8. **029** — Resonance check
9. **030** — Solution-depth gate
10. **034** — bd cross-issue memory
11. **036** — Comment quality gate

### Phase 2.5 — Knowledge preservation
12. **038** — Session pattern evidence log

## Dependency graph

```
027 (stale path) ──┬──> 028 (bd data store) ──┬──> 029 (resonance)
                   │                            └──> 034 (long-term memory)
                   └──> 031 (sentinel)

030 (solution depth) — independent
032 (ddev pause)     — independent
033 (research)       — informs 031, 028, possibly 030
035 (research)       — informs 027, 028, 031
036 (comment gate)   — independent
037 (cleanup)        — independent
038 (evidence log)   — reference material, not blocking
```

## Status legend

- **NOT_STARTED**: not begun
- **IN_PROGRESS**: currently being worked
- **BLOCKED**: waiting on dependency or external decision
- **COMPLETED**: implementation merged and verified
- **OBSOLETE**: superseded; will not be implemented

## Reading order for new sessions

When picking a ticket to implement, FIRST read this index file. THEN read the ticket itself. Each ticket header lists its dependencies — read those briefly to understand what already exists.

## Phase 1 reference

The original 26 tickets are all in COMPLETED status. They establish:
- Controller pattern with sub-agents
- Hands-free workflow from invocation to push gate
- Structured agent status codes (DONE/NEEDS_CONTEXT/BLOCKED/FAILED)
- Verification gate (prose-only, ticket 022)
- State handoff artifacts (workflow/0X-*.json|md, ticket 023)
- Two-stage review (spec + quality, ticket 018)
- Fresh subagent per phase / controller pattern (ticket 019)

Phase 2 builds on this foundation. It does NOT re-do any of phase 1; it adds enforcement and memory layers that phase 1's prose-only approach cannot provide.

## Removed in phase 2 cleanup

(Updated as ticket 037 lands. Initial removals planned:)
- `docs/tickets/012-chrome-mcp-for-screenshots.md` — obsolete; the actual implementation went via `agent-browser` Rust binary instead. Title was misleading.
- `.claude/agents/drupal-contributor.md` — marked DEPRECATED in CLAUDE.md but ticket 014 missed deleting the file.
