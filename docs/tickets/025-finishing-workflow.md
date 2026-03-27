# TICKET-025: Structured Finishing Workflow (Post-Push Options)

**Status:** COMPLETED
**Priority:** P3 (Low)
**Affects:** `.claude/skills/drupal-contribute-fix/SKILL.md` or new skill
**Inspired by:** Superpowers `finishing-a-development-branch` skill
**Type:** New Feature

## Pattern from Superpowers

After implementation is complete and verified, superpowers presents exactly 4 structured options:

```
1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work
```

Each option has a defined execution path. Option 4 requires explicit confirmation ("Type 'discard' to confirm"). This structure prevents ambiguity about what happens after work is done.

## What We Have Now

After pushing to an MR, the session just... ends. There's no structured "what next?" There are several things that could logically follow:

1. Monitor the CI pipeline (TICKET-007)
2. Post the comment to drupal.org (manual, but we can remind)
3. Clean up the DDEV environment
4. Move on to the next issue
5. Wait for reviewer feedback

## Proposed Finishing Options

After successful push:

```markdown
## Push Complete

Pushed to MR !20 on branch 3579478-add-litellm-guardrails.

What would you like to do next?

1. **Monitor pipeline** - Watch GitLab CI and report results
2. **Post comment** - Open the issue page to post the draft comment
3. **Clean up** - Stop DDEV, remove issue directory
4. **Next issue** - Start work on a different issue
5. **Done for now** - Keep everything as-is

Which option?
```

### Option 1: Monitor Pipeline
- Dispatch pipeline-watch agent (TICKET-007)
- Report results when done

### Option 2: Post Comment
- Open drupal.org issue page via Chrome MCP
- Navigate to comment form
- Paste the draft comment
- (Or just remind user to do it manually with the file path)

### Option 3: Clean Up
- Confirmation required: "This will stop DDEV project d3579478 and remove DRUPAL_ISSUES/3579478/. Confirm? [y/n]"
- `ddev stop` (NOT `ddev delete`)
- Keep artifacts for reference unless user says otherwise

### Option 4: Next Issue
- Ask for issue URL
- Start fresh `/drupal-issue` workflow

### Option 5: Done for Now
- Report: "Branch 3579478-add-litellm-guardrails pushed. DDEV project d3579478 still running."
- No cleanup

## Implementation Plan

### 1. Add finishing section to `/drupal-contribute-fix`

After the push succeeds:

```markdown
## After Successful Push

Present the finishing options to the user. Wait for their choice.
Execute the chosen option. Do not assume.
```

### 2. Create cleanup logic

```bash
# Safe cleanup (default)
cd DRUPAL_ISSUES/{issue_id}/{env_name}
ddev stop

# Full cleanup (user must confirm)
ddev stop
cd ../..
rm -rf {issue_id}/
```

## Acceptance Criteria

- [ ] Structured options presented after successful push
- [ ] Each option has a defined execution path
- [ ] Destructive options (cleanup) require confirmation
- [ ] Pipeline monitoring available as an option
- [ ] User can move to next issue seamlessly

## Files to Modify

1. `.claude/skills/drupal-contribute-fix/SKILL.md` - Add finishing section
