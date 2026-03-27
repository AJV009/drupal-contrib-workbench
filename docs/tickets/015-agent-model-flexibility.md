# TICKET-015: Allow Agent Model Override Per Task Complexity

**Status:** COMPLETED
**Priority:** P3 (Low)
**Affects:** All agent definitions in `.claude/agents/`
**Type:** Enhancement

## Problem

All 5 agents are hardcoded to `model: sonnet`:
- `drupal-reviewer.md` - sonnet
- `drupal-verifier.md` - sonnet
- `drupal-contributor.md` - sonnet
- `drupal-issue-fetcher.md` - sonnet
- `drupal-ddev-setup.md` - sonnet

For some agents, sonnet is appropriate (fetcher and ddev-setup are mechanical tasks). For others, a more capable model would produce better results:

| Agent | Ideal Model | Reasoning |
|-------|------------|-----------|
| `drupal-reviewer` | opus | Code review requires deep understanding of Drupal architecture, security patterns, and subtle bugs |
| `drupal-verifier` | sonnet | Mostly runs commands and checks output; mechanical |
| `drupal-contributor` | opus | Complex workflow orchestration (if kept per TICKET-014) |
| `drupal-issue-fetcher` | haiku | Pure API calls and file writing; no reasoning needed |
| `drupal-ddev-setup` | haiku | Mechanical: run commands in sequence, handle errors |

## Current Impact

- Reviewer agent on sonnet may miss subtle security issues or architectural problems that opus would catch
- Fetcher and DDEV setup agents on sonnet are overpowered for their tasks (wasting cost/speed)

## Proposed Changes

### 1. Update agent model defaults

```
drupal-reviewer.md:     model: opus    (upgraded for quality)
drupal-verifier.md:     model: sonnet  (no change)
drupal-contributor.md:  model: sonnet  (no change, or remove per TICKET-014)
drupal-issue-fetcher.md: model: haiku  (downgraded for speed/cost)
drupal-ddev-setup.md:   model: haiku   (downgraded for speed/cost)
```

### 2. Document model selection rationale

Add a comment in each agent file:

```markdown
# Model: opus
# Rationale: Code review requires understanding of Drupal architecture,
# security patterns, and subtle bugs. Sonnet may miss issues that opus catches.
```

### 3. Allow caller override

The Agent tool supports a `model` parameter. Skills that dispatch agents should be able to override the default:

```markdown
For critical reviews (pre-push to major MRs), dispatch the reviewer
with model: opus. For quick checks during development, sonnet is fine.
```

## Acceptance Criteria

- [ ] Each agent has an appropriate default model for its task complexity
- [ ] Model selection rationale is documented in each agent file
- [ ] Cost-sensitive agents (fetcher, ddev-setup) use haiku
- [ ] Quality-sensitive agents (reviewer) use opus
- [ ] Callers can override when needed

## Files to Modify

1. `.claude/agents/drupal-reviewer.md` - Change to opus
2. `.claude/agents/drupal-issue-fetcher.md` - Change to haiku
3. `.claude/agents/drupal-ddev-setup.md` - Change to haiku
