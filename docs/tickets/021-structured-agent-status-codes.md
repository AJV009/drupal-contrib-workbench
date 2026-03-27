# TICKET-021: Structured Agent Status Codes and Handoff Protocol

**Status:** COMPLETED
**Priority:** P1 (High)
**Affects:** All agents
**Inspired by:** Superpowers implementer status system (DONE, DONE_WITH_CONCERNS, BLOCKED, NEEDS_CONTEXT)
**Type:** Enhancement

## Pattern from Superpowers

Superpowers implementer subagents report one of four statuses:

| Status | Meaning | Controller Action |
|--------|---------|-------------------|
| DONE | Task completed successfully | Proceed to review |
| DONE_WITH_CONCERNS | Completed but has questions/observations | Read concerns, address if relevant, proceed |
| NEEDS_CONTEXT | Missing information to proceed | Provide info, re-dispatch same model |
| BLOCKED | Cannot proceed at all | Escalate: more context? Better model? Break task? Ask human? |

The controller has explicit handling for each status. There's no ambiguity about what to do when an agent returns.

## What We Have Now

Our agents return free-text with loosely defined statuses:

```
# drupal-issue-fetcher: "COMPLETE" or "PARTIAL" or "FAILED"
# drupal-ddev-setup: "READY" or "FAILED"
# drupal-reviewer: "PASS" or "FAIL"
# drupal-verifier: "VERIFIED" or "FAILED" or "BLOCKED"
```

Problems:
- No "needs more info" status (agent either succeeds or fails)
- No "done with concerns" (observations are lost)
- No structured escalation path
- Controller doesn't know why an agent failed (just "FAILED")
- No standard way to re-dispatch with more context

## Proposed Universal Agent Status Protocol

### Status Codes

Every agent MUST report one of these statuses:

```markdown
## Status Protocol (All Agents)

### DONE
Agent completed its task. Return includes all requested outputs.
Controller action: Proceed to next phase.

### DONE_WITH_CONCERNS
Agent completed but has observations that may affect downstream work.
Return includes outputs + concerns list.
Controller action: Read concerns. If concerns affect next phase,
  address them. Otherwise note and proceed.

### NEEDS_CONTEXT
Agent cannot complete because it's missing specific information.
Return includes: what's missing, why it's needed, what was tried.
Controller action: Provide missing info and re-dispatch.
  Max 2 re-dispatches. After that, escalate to human.

### BLOCKED
Agent cannot proceed. The problem is beyond its scope.
Return includes: what was attempted, what failed, diagnosis.
Controller action:
  - Context problem? Provide more context, re-dispatch.
  - Capability problem? Re-dispatch with more capable model.
  - Task too large? Break into smaller tasks.
  - Fundamental issue? Escalate to human.

### FAILED
Agent encountered an unrecoverable error (network, permissions, etc.)
Return includes: error details, what was accomplished before failure.
Controller action: Retry once. If fails again, escalate to human.
```

### Return Value Format

```markdown
## Agent Return Format (Universal)

STATUS: [DONE|DONE_WITH_CONCERNS|NEEDS_CONTEXT|BLOCKED|FAILED]

## Summary
[1-3 sentences describing what was accomplished]

## Outputs
[Structured output specific to this agent type]

## Concerns (if DONE_WITH_CONCERNS)
- [Concern 1: what was observed, why it matters]
- [Concern 2: ...]

## Missing (if NEEDS_CONTEXT)
- [What's needed: description]
- [Why: how it blocks progress]
- [Tried: what was attempted to find it]

## Blocked (if BLOCKED)
- [Attempted: what was tried]
- [Failed because: root cause]
- [Diagnosis: what the controller should do]

## Error (if FAILED)
- [Error: description]
- [Partial work: what was accomplished]
- [Retry suggestion: what to change]
```

## Implementation Plan

### 1. Update each agent definition

Add the status protocol and return format to every agent file:

```markdown
## Status Protocol

You MUST report one of: DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED, FAILED

[include full protocol definition]

## Return Format

[include structured return template specific to this agent]
```

### 2. Update controller skills to handle all statuses

In `/drupal-issue` (controller):

```markdown
## Handling Agent Results

For each agent dispatch, handle the status:

- DONE: Extract outputs, pass to next phase
- DONE_WITH_CONCERNS: Read concerns, decide if they affect next phase
- NEEDS_CONTEXT: Provide missing info from conversation/artifacts, re-dispatch
- BLOCKED: Try escalation ladder (more context -> better model -> smaller task -> human)
- FAILED: Retry once with same parameters. If fails again, report to user.

Max re-dispatches per agent: 2
Max total retries across all agents: 5
After limits exceeded: Present status to user, ask for guidance
```

### 3. Add concerns propagation

When an agent reports DONE_WITH_CONCERNS, its concerns should be passed downstream:

```markdown
If fetcher reports DONE_WITH_CONCERNS:
  - "Comment count mismatch: issue says 5, fetched 4"
  → Pass concern to reviewer: "Note: comment #5 may be missing"

If DDEV setup reports DONE_WITH_CONCERNS:
  - "Module installed but drush en showed a deprecation warning"
  → Pass concern to verifier: "Check deprecation warning in watchdog"
```

## Acceptance Criteria

- [ ] All agents use the 5-status protocol
- [ ] Return values follow the universal format
- [ ] Controller handles all 5 statuses explicitly
- [ ] NEEDS_CONTEXT triggers re-dispatch with additional info
- [ ] BLOCKED triggers escalation ladder
- [ ] Concerns from early agents propagate to later agents
- [ ] Max retry limits enforced

## Files to Modify

1. `.claude/agents/drupal-issue-fetcher.md` - Add status protocol
2. `.claude/agents/drupal-ddev-setup.md` - Add status protocol
3. `.claude/agents/drupal-reviewer.md` - Add status protocol
4. `.claude/agents/drupal-verifier.md` - Add status protocol
5. `.claude/skills/drupal-issue/SKILL.md` - Add status handling in controller
6. `.claude/skills/drupal-contribute-fix/SKILL.md` - Add status handling for reviewer/verifier
