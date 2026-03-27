# TICKET-023: Explicit State Handoff Artifacts Between Phases

**Status:** COMPLETED
**Priority:** P2 (Medium)
**Affects:** All workflow skills
**Inspired by:** Superpowers design doc -> plan doc -> execution -> finishing chain
**Type:** Enhancement

## Pattern from Superpowers

Superpowers uses concrete file artifacts to pass state between phases:

```
brainstorming → docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
writing-plans → docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md
execution     → git commits (each task)
finishing     → merge/PR/keep/discard decision
```

Each phase reads the previous phase's artifact. State is never implicit (conversation memory). If context is lost (session restart, compression), the artifacts preserve everything needed to continue.

## What We Have Now

Our skill chain passes state through conversation context:

```
drupal-issue-fetcher → artifacts/ directory (good! concrete files)
drupal-issue (classify) → conversation memory (bad! implicit)
drupal-issue-review → DDEV environment state (implicit)
drupal-contribute-fix → code changes in git (good for code, bad for metadata)
drupal-issue-comment → DRUPAL_ISSUES/{id}/issue-comment-{id}.html (good!)
```

The problem: classification decisions, review findings, test plans, and verification results live only in conversation context. If the session is long (like #3579478 at 643 messages), early context gets compressed and decisions are lost.

## Proposed State Artifacts

Each phase should produce a concrete file that the next phase reads:

```
DRUPAL_ISSUES/{issue_id}/
  artifacts/              (from fetcher agent, already exists)
    issue.json
    comments.json
    merge-requests.json
    mr-{iid}-diff.patch
    ...
  workflow/                (NEW: workflow state files)
    00-classification.json
    01-review-findings.md
    02-test-plan.md
    03-verification-results.json
    04-push-gate-summary.md
    05-issue-comment.html
```

### 00-classification.json

```json
{
  "issue_id": 3579478,
  "classified_at": "2026-03-26T08:34:37Z",
  "action_type": "review_existing_mr",
  "category": "B",
  "needs_ddev": true,
  "needs_reproduction": false,
  "primary_mr": 20,
  "target_branch": "1.3.x",
  "next_skill": "drupal-issue-review",
  "rationale": "MR !20 exists with passing pipeline, status is Needs Review"
}
```

### 01-review-findings.md

```markdown
# Review Findings: Issue #3579478

## Static Code Review (pre-DDEV)
- Entity ID in LiteLlmAiConfigForm.php:298 not capped to 64 chars
- guardrails() in LiteLlmAiClient.php swallows all exceptions via catch(\Throwable)
- Missing test coverage for error propagation paths

## Functional Review (post-DDEV)
- Config entities created with long names would fail silently
- Connection errors in guardrails() invisible to users

## Related Issues
- None found
```

### 02-test-plan.md

```markdown
# Test Plan: Issue #3579478

## From Diff Analysis
- [ ] LiteLlmGuardrail::processInput() returns PassResult
- [ ] LiteLlmGuardrail::processOutput() returns PassResult
- [ ] guardrails() parses valid response
- [ ] guardrails() handles empty response
- [ ] guardrails() propagates connection error
...

## Test Type: Unit (UnitTestCase)
## Files to Create: 4 test files
```

### 03-verification-results.json

```json
{
  "phpcs": {"status": "pass", "errors": 0, "warnings": 0},
  "phpunit": {"status": "pass", "tests": 24, "assertions": 56, "failures": 0},
  "test_validation": {"status": "pass", "legitimate": 22, "trivial": 2},
  "spec_review": "SPEC_COMPLIANT",
  "code_review": "APPROVED",
  "verified_at": "2026-03-26T09:30:00Z"
}
```

### 04-push-gate-summary.md

Complete summary with all evidence, ready for user review.

## Benefits

1. **Resumability:** If session crashes or is restarted, workflow state is preserved
2. **Auditability:** Can review what was decided and why at each phase
3. **Context efficiency:** Later phases read small state files instead of searching conversation
4. **Agent independence:** Agents read state files, don't need conversation context
5. **Debugging:** When something goes wrong, state files show where the workflow went off track

## Implementation Plan

### 1. Add workflow directory creation to `/drupal-issue`

At the start of any issue workflow:
```bash
mkdir -p DRUPAL_ISSUES/{issue_id}/workflow
```

### 2. Each phase writes its state file

Add to each skill's completion section:
```markdown
Before handing off to the next phase, write your state file:
  DRUPAL_ISSUES/{issue_id}/workflow/{phase_num}-{phase_name}.{json|md}
```

### 3. Each phase reads the previous state file

Add to each skill's initialization section:
```markdown
Before starting, read the previous phase's state file:
  DRUPAL_ISSUES/{issue_id}/workflow/{previous_phase}.{json|md}
Use this to understand what was decided and what context you need.
```

## Acceptance Criteria

- [ ] Each workflow phase produces a state artifact file
- [ ] Subsequent phases read previous state files
- [ ] Workflow can be resumed from any phase by reading state files
- [ ] State files contain sufficient context for agent dispatch
- [ ] push-gate-summary.md includes all verification evidence

## Files to Modify

1. `.claude/skills/drupal-issue/SKILL.md` - Write classification.json
2. `.claude/skills/drupal-issue-review/SKILL.md` - Write review-findings.md, test-plan.md
3. `.claude/skills/drupal-contribute-fix/SKILL.md` - Write verification-results.json, push-gate-summary.md
4. `.claude/skills/drupal-issue-comment/SKILL.md` - Already writes HTML file (no change)
