# TICKET-014: Clarify drupal-contributor Agent vs Skill Chain Overlap

**Status:** COMPLETED
**Priority:** P3 (Low)
**Affects:** `.claude/agents/drupal-contributor.md`, `.claude/skills/drupal-issue/SKILL.md`
**Type:** Cleanup / Documentation

## Problem

The `drupal-contributor` agent and the skill chain (`drupal-issue` -> `drupal-issue-review` -> `drupal-contribute-fix`) perform the same workflow:

**drupal-contributor agent (5 phases):**
1. Search First (search drupal.org)
2. Reproduce (install module, reproduce bug)
3. Fix (create branch, write fix)
4. Test (write tests, run PHPCS)
5. Package (generate diff, write summary)

**Skill chain (same 5 phases, distributed):**
1. `/drupal-issue` classifies, `/drupal-contribute-fix` preflight searches
2. `/drupal-issue-review` reproduces via `drupal-ddev-setup` agent
3. `/drupal-contribute-fix` writes the fix
4. `/drupal-contribute-fix` writes tests, runs PHPCS
5. `/drupal-contribute-fix` package mode generates artifacts

It is unclear when to use the agent vs. the skill chain. In practice, the skill chain is always used (it's what `/drupal-issue` triggers). The `drupal-contributor` agent is never dispatched.

## Options

### Option A: Remove the agent (Recommended)

The skill chain is more capable (it chains multiple specialized skills, dispatches sub-agents, has more detailed instructions). The `drupal-contributor` agent is a less detailed version of the same workflow. Remove it to avoid confusion.

Update CLAUDE.md to remove the agent from the "Available Agents" section.

### Option B: Repurpose the agent

Rename and repurpose `drupal-contributor` as a "quick fix" agent for simple, well-defined bugs that don't need the full skill chain:

```markdown
# drupal-quick-fix agent

For simple, well-scoped bugs with clear reproduction steps:
- Single file change
- Clear error message
- Known fix pattern

Skips the full skill chain and goes directly to:
1. Install module
2. Reproduce
3. Fix
4. Test
5. Package
```

### Option C: Make the agent the implementation of the skill

Instead of skills having inline instructions, have `/drupal-issue` dispatch the `drupal-contributor` agent to do all the work. This cleanly separates "what to do" (skill) from "how to do it" (agent).

## Recommendation

**Option A.** The skill chain is well-established, actively used, and more detailed. The agent is redundant. Removing it simplifies the system and eliminates the "which one do I use?" ambiguity.

## Acceptance Criteria

- [ ] Clear documentation on when to use agent vs. skill chain (or one removed)
- [ ] No overlapping workflow definitions
- [ ] CLAUDE.md updated to reflect the decision

## Files to Modify

1. `.claude/agents/drupal-contributor.md` - Remove or repurpose
2. `.claude/CLAUDE.md` - Update Available Agents section
