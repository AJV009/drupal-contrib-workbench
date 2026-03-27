# TICKET-010: Related Issue Discovery Agent

**Status:** COMPLETED
**Priority:** P2 (Medium)
**Affects:** `.claude/agents/drupal-issue-fetcher.md` or new agent
**Type:** New Feature

## Problem

In the #3579478 session, the user specifically asked to "verify any other related issues that might help in this reviewing activity." This was never addressed. No search for related issues was performed.

For a thorough review, knowing about related issues helps:
- Avoid duplicating work someone else has done
- Understand the broader context (is this part of a larger effort?)
- Find edge cases others have reported
- Discover blocking/dependent issues
- Identify if the fix might break something else

## Current Behavior

The fetcher agent fetches data for the specific issue requested. It does not search for related issues. The `drupal-contribute-fix` preflight searches for similar issues but only by keyword matching on error messages, not by module-level context.

## Desired Behavior

After fetching the primary issue, automatically search for related issues:

```
1. Same module, recent issues (last 6 months)
2. Issues linked/referenced in comments
3. Issues with similar keywords/error messages
4. Parent/child issues (if any)
5. Issues in the same component
```

## Implementation Plan

### Option A: Extend drupal-issue-fetcher (Recommended)

Add a "related issues" phase to the fetcher agent:

```markdown
## Step 6: Discover Related Issues (Optional but Recommended)

After fetching the primary issue:

1. Extract keywords from issue title and description
2. Search drupal.org API:
   - Same project, status=open: GET /api-d7/node.json?type=project_issue&field_project={nid}&status=1,13,8,14
   - Similar keywords: GET /api-d7/node.json?type=project_issue&field_project={nid}&title={keywords}
3. Scan comments for issue references:
   - Regex: #(\d{7}) or /node/(\d{7}) or /issues/(\d{7})
   - Fetch titles/statuses for referenced issues
4. Write results to artifacts/related-issues.json:
   ```json
   {
     "same_module_recent": [
       {"nid": 3578000, "title": "...", "status": "Active", "relevance": "same component"}
     ],
     "referenced_in_comments": [
       {"nid": 3575000, "title": "...", "status": "Fixed", "context": "mentioned in comment #3"}
     ],
     "similar_keywords": [
       {"nid": 3577000, "title": "...", "status": "Needs work", "similarity": "shares 'guardrail' keyword"}
     ]
   }
   ```
```

### Option B: Separate `drupal-issue-context` Agent

Create a lightweight agent focused on contextual discovery:

```markdown
# drupal-issue-context agent
Model: haiku (fast, lightweight)
Tools: Bash, Read, Write

## Input
- Project NID (from issue.json)
- Issue title and description keywords
- Comment references (extracted by fetcher)

## Output
- related-issues.json with categorized related issues
- brief summary of what's relevant
```

### Include in Summary

The related issues should be mentioned in the fetcher's enriched return (TICKET-002):

```markdown
## Related Issues
- #3578123 "Guardrail config entity validation" (Active, same component)
- #3575000 "LiteLLM client error handling" (Fixed, referenced in comment #3)
- No blocking issues found
```

## Acceptance Criteria

- [ ] Related issues are discovered automatically during issue fetching
- [ ] Results saved to `artifacts/related-issues.json`
- [ ] Same-module recent issues searched
- [ ] Issue references in comments are extracted and fetched
- [ ] Related issues summary included in fetcher return value
- [ ] Search respects API rate limits (max 5 requests for related issues)

## Files to Modify

1. `.claude/agents/drupal-issue-fetcher.md` - Add related issue discovery phase
2. `.claude/skills/drupal-contribute-fix/scripts/fetch_issue.py` - Add related issue search (optional, could be agent-only)
