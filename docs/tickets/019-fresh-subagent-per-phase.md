# TICKET-019: Fresh Subagent Per Phase (Controller Pattern)

**Status:** COMPLETED
**Priority:** P1 (High)
**Affects:** `.claude/skills/drupal-issue/SKILL.md`, all workflow skills
**Inspired by:** Superpowers `subagent-driven-development` skill
**Type:** Architecture

## Pattern from Superpowers

Superpowers uses a "controller + fresh subagent" architecture:

```
Controller (main session):
  - Reads plan
  - Dispatches implementer subagent with FULL task text
  - Receives result
  - Dispatches spec reviewer with FULL requirements + code
  - Receives result
  - Dispatches code quality reviewer
  - Receives result
  - Moves to next task

Key insight: Controller NEVER reads files directly.
             Controller provides FULL context to subagents.
             Each subagent starts fresh (no inherited context).
```

This keeps the controller's context window clean for orchestration while giving each subagent exactly the context it needs.

## What We Do Now

Our main session does EVERYTHING:
- Reads all issue artifacts (context consumed)
- Sets up DDEV (context consumed by command output)
- Reads all source files (context consumed)
- Writes tests (context consumed by iterations)
- Runs PHPCS (context consumed)
- Runs tests (context consumed)
- Reviews code (context consumed)
- Drafts comments (context consumed)

By the time we reach the push gate, the context window is bloated with hundreds of file reads, command outputs, and intermediate work. This is why the session took 66 minutes and 643 messages.

## Proposed Architecture

```
Controller (main session, stays lean):
  Phase 0: Dispatch fetcher agent -> receives enriched summary
  Phase 1: Classify action (using summary, minimal context)
  Phase 2: Dispatch DDEV setup agent (background) -> receives READY report
  Phase 3: Dispatch code-review agent (foreground while DDEV sets up)
           -> provides: diff content, issue requirements
           -> receives: review findings, test plan
  Phase 4: Dispatch fix-and-test agent (foreground)
           -> provides: findings, test plan, module path, DDEV info
           -> receives: list of changes, test results, PHPCS results
  Phase 5: Dispatch spec-reviewer agent
           -> provides: issue requirements, change list
           -> receives: SPEC_COMPLIANT or SPEC_GAPS
  Phase 6: Dispatch code-quality-reviewer agent
           -> provides: changed files, PHPCS results
           -> receives: APPROVED or NEEDS_WORK
  Phase 7: Dispatch comment-drafter agent
           -> provides: issue context, findings, changes
           -> receives: HTML comment draft
  Phase 8: Present push gate summary (controller has all results)
  Phase 9: Push (if user confirms)
```

The controller never reads source files, never runs PHPCS, never writes tests. It orchestrates and passes context between agents.

## Benefits

1. **Context window:** Controller stays under 50K tokens instead of 185K+
2. **Speed:** Each agent starts fresh, no context search overhead
3. **Quality:** Each agent gets exactly the context it needs, no noise
4. **Parallelism:** Independent agents can run concurrently
5. **Recovery:** If an agent fails, only that phase needs re-running

## Implementation Plan

### 1. Define the controller flow in `/drupal-issue`

```markdown
## Controller Mode (Hands-Free)

When running hands-free, act as a controller:

1. DO NOT read files directly (except artifacts summary from fetcher)
2. DO NOT run shell commands (except git push at the end)
3. Dispatch agents for ALL file reading, code changes, and command execution
4. Pass context FORWARD between agents via their return values
5. Keep your context clean for orchestration decisions

Each phase produces a structured output that feeds the next phase.
```

### 2. Create a `drupal-fix-and-test` agent

This is the heavy-lifting agent that does the actual code work:

```markdown
# drupal-fix-and-test agent
Model: opus (complex code work)
Tools: Read, Write, Edit, Bash, Glob, Grep

## Input
- Review findings (from code-review agent)
- Test plan (from code-review agent)
- Module path (from DDEV setup agent)
- DDEV project name
- Issue requirements

## Process
1. Read relevant source files
2. Write fixes based on findings
3. Write tests based on test plan
4. Run tests (iterate until passing)
5. Run PHPCS (fix until clean)
6. Validate tests (stash/unstash per TICKET-006)

## Output
- List of changed files with descriptions
- Test results (count, passing)
- PHPCS results
- Test validation results
- Git diff of all changes
```

### 3. Update all existing agents to return structured output

Every agent return value should be structured enough that the controller can pass it to the next agent without re-reading files.

## Key Superpowers Insight

> "Controller provides FULL task text to subagents. Never make subagent read plan file."

Applied to our system: the controller should extract and provide the relevant context (issue summary, diff content, findings) directly in the agent prompt, not tell the agent "go read the artifacts directory."

## Acceptance Criteria

- [ ] Controller (main session) never reads source files directly
- [ ] Each phase dispatched as an agent with full context provided
- [ ] Agent return values are structured and sufficient for next phase
- [ ] Controller context stays under 50K tokens
- [ ] Total workflow time reduced (agents work with focused context)

## Files to Create/Modify

1. `.claude/skills/drupal-issue/SKILL.md` - Add controller mode
2. `.claude/agents/drupal-fix-and-test.md` - NEW heavy-lifting agent
3. `.claude/agents/drupal-code-review.md` - NEW static review agent (separate from drupal-reviewer)
4. All existing agents - Structured output format
