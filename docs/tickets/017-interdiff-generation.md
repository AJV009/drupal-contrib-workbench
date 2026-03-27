# TICKET-017: Generate Interdiff for Follow-Up Commits

**Status:** COMPLETED
**Priority:** P3 (Low)
**Affects:** `.claude/skills/drupal-contribute-fix/SKILL.md`
**Type:** Enhancement

## Problem

When pushing follow-up commits to an existing MR (as happened in #3579478 where we added fixes on top of nikro's original MR !20), reviewers benefit from seeing an interdiff: what changed between the previous state and the new state.

Currently, the push gate summary shows the full diff of our changes but doesn't generate an interdiff file. On drupal.org, interdiffs are commonly posted as attachments or referenced in comments.

## What is an Interdiff?

An interdiff shows only the differences between two versions of a patch. If the MR had 6 files and we changed 2 of them + added 4 test files, the interdiff shows exactly those changes, not the entire MR diff.

```bash
# Generate interdiff between the MR's original state and our changes
git diff <commit-before-our-changes>..<our-commit> > interdiff-3579478.patch
```

## Implementation Plan

### 1. Add interdiff generation to push gate

When pushing follow-up commits to an existing MR:

```markdown
## Interdiff Generation (When Pushing to Existing MR)

Before presenting the push gate summary:

1. Identify the base commit (last commit before our changes):
   ```bash
   BASE_COMMIT=$(git log --oneline | head -2 | tail -1 | cut -d' ' -f1)
   ```

2. Generate interdiff:
   ```bash
   git diff $BASE_COMMIT..HEAD > DRUPAL_ISSUES/{issue_id}/interdiff-{issue_id}.patch
   ```

3. Include in push gate summary:
   ```
   ## Interdiff
   - File: interdiff-{issue_id}.patch (832 lines)
   - Changes from previous MR state:
     - Modified: src/LiteLLM/LiteLlmAiClient.php (+5, -12)
     - Modified: src/Form/LiteLlmAiConfigForm.php (+3, -1)
     - Added: tests/src/Unit/LiteLlmAiClientGuardrailsTest.php (+180)
     - Added: tests/src/Unit/LiteLlmAiConfigFormSyncTest.php (+195)
     - Added: tests/src/Unit/LiteLlmGuardrailTest.php (+125)
     - Added: tests/src/Unit/LiteLlmAiProviderGuardrailTest.php (+139)
   ```

4. Reference interdiff in the issue comment draft (TICKET-009):
   ```html
   Pushed a follow-up commit addressing entity ID length and error propagation.
   Interdiff from the previous state covers the test additions and two source fixes.
   ```
```

### 2. Only generate for follow-up commits

If this is the first commit on the MR branch (we created the MR), an interdiff doesn't apply. Only generate when:
- Pushing to an existing MR that already has commits from others
- The MR branch already existed before our changes

## Acceptance Criteria

- [ ] Interdiff generated when pushing follow-up commits to existing MR
- [ ] Saved to `DRUPAL_ISSUES/{issue_id}/interdiff-{issue_id}.patch`
- [ ] Included in push gate summary
- [ ] Referenced in draft comment
- [ ] Not generated for new MRs (first commit)

## Files to Modify

1. `.claude/skills/drupal-contribute-fix/SKILL.md` - Add interdiff generation to push gate
