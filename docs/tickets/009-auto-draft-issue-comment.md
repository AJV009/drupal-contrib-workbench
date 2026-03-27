# TICKET-009: Auto-Draft Issue Comment Before Push Gate

**Status:** COMPLETED
**Priority:** P2 (Medium)
**Affects:** `.claude/skills/drupal-issue/SKILL.md`, `.claude/skills/drupal-issue-comment/SKILL.md`
**Type:** Enhancement

## Problem

In the #3579478 session, code was pushed to MR !20 but no drupal.org comment was drafted. The `/drupal-issue-comment` skill was never invoked. This means:

1. The maintainer reviewing MR !20 has no context about what the additional commit addresses
2. They have to read the commit message and diff to understand the changes
3. No test results or findings were communicated on the issue page
4. The transparency note (AI assistance disclosure) was not added

The commit message was good ("Cap entity ID length, propagate guardrails() errors, add unit tests") but a proper issue comment provides:
- Why these changes were needed (entity IDs exceeding 64 chars, swallowed errors)
- How they were discovered (during code review of MR !20)
- Test evidence (24 tests, what they cover)
- Context for the maintainer's review

## Current Behavior

```
Fix code -> Write tests -> PHPCS -> Push
(no comment drafted)
```

## Desired Behavior

```
Fix code -> Write tests -> PHPCS -> Draft comment -> Push gate
```

The comment draft should be part of the push gate summary, so the user can:
1. Review the comment
2. Edit if needed
3. Approve push + comment together

## Implementation Plan

### 1. Add auto-comment to the hands-free workflow (TICKET-001)

In the push gate, after all code/test work is complete:

```markdown
## Before Push Gate

1. All code changes complete
2. PHPCS passes
3. Tests pass
4. Reviewer agent: APPROVED
5. Verifier agent: VERIFIED
6. **Draft issue comment via /drupal-issue-comment** <-- NEW
7. Present push gate summary (including draft comment)
```

### 2. Pass context to the comment skill

When invoking `/drupal-issue-comment`, provide:
- Issue number and URL
- What was found during review
- What was fixed (summary of changes)
- Test results (count, types)
- Previous commenters to address
- Related issues found (if any)

### 3. Include comment in push gate summary

```markdown
## Push Gate Summary

### Changes
[diff summary]

### Quality
- Tests: 24/24 passing
- PHPCS: clean
- Reviewer: APPROVED
- Verifier: VERIFIED

### Draft Comment (for drupal.org)
---
[rendered HTML comment preview]
---

### Actions
- Push to 3579478-add-litellm-guardrails? [y/n]
- Post comment to drupal.org? [y/n] (manual, comment saved to file)
```

### 4. Save comment file for manual posting

The comment should be saved to:
```
DRUPAL_ISSUES/3579478/issue-comment-3579478.html
```

The user can then copy-paste it into the drupal.org comment box.

## Acceptance Criteria

- [ ] `/drupal-issue-comment` is auto-invoked before the push gate
- [ ] Comment draft is included in push gate summary
- [ ] Comment is saved to `DRUPAL_ISSUES/{id}/issue-comment-{id}.html`
- [ ] Comment follows all tone/style rules from the comment skill
- [ ] User can review and edit before posting
- [ ] Transparency note is included

## Files to Modify

1. `.claude/skills/drupal-issue/SKILL.md` - Add comment drafting to orchestration flow
2. `.claude/skills/drupal-contribute-fix/SKILL.md` - Add comment drafting to pre-push sequence
