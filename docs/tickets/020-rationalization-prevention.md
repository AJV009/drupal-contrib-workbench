# TICKET-020: Add Rationalization Prevention Tables to All Skills

**Status:** COMPLETED
**Priority:** P2 (Medium)
**Affects:** All skill files
**Inspired by:** Superpowers TDD, debugging, and verification skills
**Type:** Enhancement

## Pattern from Superpowers

Every discipline-enforcing skill in superpowers includes explicit "rationalization tables" and "red flag lists." These aren't just rules. They are specific thoughts the model might have that indicate it's about to skip a required step, with refutations.

Example from TDD skill:

| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks; test takes 30 seconds |
| "I'll test after" | Tests passing immediately proves nothing |
| "Already manually tested" | Ad-hoc is not systematic |
| "TDD will slow me down" | TDD faster than debugging |

Example from verification skill:

| Thought | Stop! |
|---------|-------|
| "Should work now" | Run the command |
| Expressing satisfaction before verification | STOP |
| About to commit without verification | VERIFY FIRST |
| "probably", "seems to", "should" | RED FLAG |

These tables are remarkably effective because they pattern-match against the model's own internal states and short-circuit rationalization before it leads to skipped steps.

## What We Have Now

Our skills have "Iron Laws" (one-liners) but no rationalization prevention:

```
IRON LAW: NO CODE PUSHED WITHOUT KERNEL TESTS
IRON LAW: NEVER AUTO-PUSH
```

These state the rule but don't address WHY the model might skip it. The model can still rationalize: "This is just a test file change, it doesn't need its own test" or "The user seems impatient, they probably want me to push."

## Proposed Rationalization Tables

### For `/drupal-contribute-fix`

```markdown
## Rationalization Prevention

| Thought | Reality |
|---------|---------|
| "This is just a small fix, no test needed" | Every fix needs a test. Small fixes break in surprising ways. |
| "The existing tests cover this" | If they did, they would have caught the bug. Write a new test. |
| "Let me push now and add tests later" | Tests-later means tests-never. The MR will be reviewed without them. |
| "PHPCS is probably fine" | Run it. "Probably" is not evidence. |
| "The user seems impatient, skip the review" | The user wants quality. Skipping review wastes their time later. |
| "This is similar to the existing code, so it's fine" | Existing code may have the same bug. Verify independently. |
| "The preflight search will just slow us down" | Duplicate MRs waste maintainer time. 30 seconds of search saves hours. |
| "I already know this module well enough" | Read the issue comments. Context you missed costs more than reading time. |
```

### For `/drupal-issue-review`

```markdown
## Rationalization Prevention

| Thought | Reality |
|---------|---------|
| "The pipeline is green, the code must be fine" | Pipelines test what's written. They don't test what's missing. |
| "I can see the fix is correct from the diff" | Can you see it's correct for all input combinations? Set up DDEV. |
| "Let me skip DDEV and just review the code" | Static review misses runtime behavior. Both are needed. |
| "The maintainer wrote this, it's probably correct" | Maintainers are human. Review everything with fresh eyes. |
| "Setting up the environment takes too long" | 3 minutes of setup prevents hours of debugging a bad review. |
```

### For `/drupal-issue` (Orchestrator)

```markdown
## Rationalization Prevention

| Thought | Reality |
|---------|---------|
| "Let me just do a quick look before invoking the full workflow" | The workflow IS the quick look. Shortcuts create blind spots. |
| "I don't need to read all the comments" | Comment #7 always has the critical context you'd miss. Read them all. |
| "This issue is straightforward, I can handle it without the skill chain" | Every issue feels straightforward until you find the edge case. |
| "Let me start coding, I'll check for existing fixes later" | Coding first, searching second = duplicate MRs. Always preflight. |
| "The user just wants this done fast" | Fast and wrong wastes more time than thorough and right. |
```

### For `/drupal-issue-comment`

```markdown
## Rationalization Prevention

| Thought | Reality |
|---------|---------|
| "I should mention how thorough my testing was" | Let the MR speak for itself. Boasting reduces credibility. |
| "Let me explain the technical depth of the fix" | The maintainer knows the code. Be brief. |
| "I should document everything I found" | Document what's USEFUL, not everything. |
| "A longer comment shows more effort" | A concise comment shows more respect for the reader's time. |
```

## Implementation Plan

### 1. Add rationalization tables to each skill

Every skill that enforces discipline should have a `## Rationalization Prevention` section with:
- 5-8 specific "Thought | Reality" pairs
- Tailored to that skill's specific failure modes
- Written from experience (the #3579478 session provides real examples)

### 2. Add red flag detection

```markdown
## Red Flags (Stop and Reconsider)

If you catch yourself thinking any of these, STOP:
- "probably", "seems to", "should work"
- Expressing satisfaction before running verification
- About to commit without PHPCS + test evidence
- Skipping a phase because "it will be fine"
- Starting code before reading all comments
- Pushing without presenting summary to user
```

### 3. Place tables near the rules they protect

Don't put all rationalization tables at the end. Put each table immediately after the rule it protects:

```markdown
## Preflight Search (MANDATORY)
[instructions]

### Rationalization Prevention (Preflight)
| Thought | Reality |
| "This is a feature, not a bug, no need to search" | Features get duplicated too. Search. |
...
```

## Acceptance Criteria

- [ ] Every skill with iron laws has a corresponding rationalization table
- [ ] Tables contain 5-8 specific thought/reality pairs
- [ ] Red flag list included in each skill
- [ ] Tables placed near the rules they protect
- [ ] Tables are based on real failure modes (not hypothetical)

## Files to Modify

1. `.claude/skills/drupal-contribute-fix/SKILL.md` - Add rationalization tables
2. `.claude/skills/drupal-issue-review/SKILL.md` - Add rationalization tables
3. `.claude/skills/drupal-issue/SKILL.md` - Add rationalization tables
4. `.claude/skills/drupal-issue-comment/SKILL.md` - Add rationalization tables
