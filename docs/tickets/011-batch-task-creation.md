# TICKET-011: Reduce Task Creation Overhead

**Status:** COMPLETED
**Priority:** P2 (Medium)
**Affects:** All skills that create tasks
**Type:** Enhancement

## Problem

In the #3579478 session, 6 tasks were created sequentially between 08:43:52 and 08:43:59 (7 seconds). Each task required a ToolSearch + TaskCreate round trip. This happened in the preamble phase before any actual work began, contributing to the user's impatience (they interrupted at 08:44:08, just 9 seconds after the last task was created).

The task creation pattern across skills:

```
[Skill invoked]
-> ToolSearch for TaskCreate
-> TaskCreate "Read issue artifacts"
-> TaskCreate "Scaffold DDEV environment"
-> TaskCreate "Install required modules"
-> TaskCreate "Reproduce the bug"
-> TaskCreate "Capture evidence"
-> TaskCreate "Hand off to next skill"
[7+ seconds of overhead before any work starts]
```

## Current Impact

- ~8 seconds overhead per skill invocation
- User sees "creating tasks" instead of "doing work"
- Context window consumed by 6+ task management messages
- Tasks created for phases that may not apply (e.g., "Hand off to next skill" created before knowing if handoff is needed)

## Proposed Improvements

### 1. Lazy task creation

Create tasks only when starting a phase, not upfront:

```markdown
## Task Tracking

Do NOT create all tasks upfront. Instead:
1. Start working immediately
2. Create a task only when you BEGIN that phase
3. Mark it completed when done
4. This means you create tasks incrementally, not in a batch

Example:
- [start working on issue reading]
- TaskCreate "Reading issue and classifying action" (status: in_progress)
- [finish reading]
- TaskUpdate -> completed
- [start DDEV setup]
- TaskCreate "Setting up DDEV environment" (status: in_progress)
- etc.
```

### 2. Single-task tracking for simple flows

For straightforward flows, use a single task with status updates:

```markdown
For linear workflows, a single task with descriptive updates is sufficient:

TaskCreate "Processing issue #3579478" (in_progress)
  -> Update: "Fetching artifacts..."
  -> Update: "Classifying action: review/test MR"
  -> Update: "DDEV setup in progress..."
  -> Update: "Running tests..."
  -> Update: "Drafting comment..."
  -> Complete
```

### 3. Parallel task creation

If multiple tasks must be created, create them in parallel (single message with multiple tool calls):

```markdown
If you must create multiple tasks at once, batch them in a single
message with parallel tool calls. Never create tasks sequentially
in separate messages.
```

## Implementation Plan

### 1. Update all skill files

Add a "Task Tracking" section to each skill that currently creates upfront tasks:

```markdown
## Task Tracking

Use lazy task creation. Create each task only when starting that phase.
Do not create all tasks upfront. The first thing you do after being
invoked should be ACTUAL WORK, not task management.
```

### 2. Skills affected

- `/drupal-issue` - Currently creates classification + delegation tasks upfront
- `/drupal-issue-review` - Creates 6 tasks upfront (the main offender)
- `/drupal-contribute-fix` - Creates phase tasks upfront

## Acceptance Criteria

- [ ] No skill creates more than 1 task before starting work
- [ ] Time from skill invocation to first real work is under 3 seconds
- [ ] Tasks are created lazily (when starting a phase)
- [ ] Total task management overhead per skill is under 2 seconds

## Files to Modify

1. `.claude/skills/drupal-issue/SKILL.md` - Add lazy task creation guidance
2. `.claude/skills/drupal-issue-review/SKILL.md` - Replace upfront task list with lazy creation
3. `.claude/skills/drupal-contribute-fix/SKILL.md` - Replace upfront task list with lazy creation
