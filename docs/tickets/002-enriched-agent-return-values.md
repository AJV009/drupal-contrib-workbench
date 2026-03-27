# TICKET-002: Enriched Agent Return Values to Eliminate Re-Reading

**Status:** COMPLETED
**Priority:** P0 (Critical)
**Affects:** `.claude/agents/drupal-issue-fetcher.md`, `.claude/agents/drupal-ddev-setup.md`
**Type:** Enhancement

## Problem

In the #3579478 session, the `drupal-issue-fetcher` agent spent 71.6 seconds fetching 8 artifacts and returned:

```
COMPLETE: 3 requests, 0 errors
```

The main session then had to **re-read** `issue.json`, `comments.json`, and `merge-requests.json` to extract the same information the agent already had in its context. This cost an additional ~20 seconds and wasted context window tokens.

Similarly, the `drupal-ddev-setup` agent completed but the main session had to manually verify what state the environment was in (was the MR applied? what's the module path? is phpunit available?).

This pattern of "agent does work, returns minimal status, caller re-reads everything" is the #1 source of redundant work across the entire skill chain.

## Current Agent Return Format

### drupal-issue-fetcher
```
COMPLETE: All artifacts fetched.
- comment_count: 5
- mr_count: 1
- primary_mr_iid: 20
- file_count: 8
```

### drupal-ddev-setup
```
READY: Environment at DRUPAL_ISSUES/3579478/ai_provider_litellm/
- Drupal: 11
- Module: ai_provider_litellm
- DDEV: d3579478 (running)
```

## Desired Agent Return Format

### drupal-issue-fetcher

Add a structured `## Summary` section to the return value:

```markdown
COMPLETE: All artifacts fetched.

## Summary
- **Issue:** #3579478 "Add LiteLLM guardrails type and sync from proxy"
- **Project:** ai_provider_litellm
- **Status:** Needs review
- **Category:** Feature request
- **Version:** 1.3.x-dev
- **Author:** nikro
- **Comments:** 5 (last by nikro on 2026-03-25)
- **Primary MR:** !20 (pipeline: success, mergeable: true, 6 files changed)

## Key Context
- Author (nikro) is working on this actively, posted implementation details in comment #5
- MR !20 has passing pipeline and no conflicts
- Testing steps provided in comment #5 by nikro

## Classification Hint
This looks like: Review/test existing MR (category B)
- MR exists with passing pipeline
- Status is "Needs review"
- No blocking issues noted

## Artifacts
- issue.json (metadata)
- comments.json (5 comments, 1 page)
- merge-requests.json (1 MR)
- mr-20-diff.patch (15,334 bytes, 6 files)
- mr-20-notes.json (review threads)
- fetch-log.json
- files.index
```

The "Classification Hint" is particularly valuable because it lets `/drupal-issue` skip most of its analysis phase. The fetcher already read the issue, comments, and MR status; it can make a reasonable guess at the action type.

### drupal-ddev-setup

Add environment readiness details:

```markdown
READY: Environment at DRUPAL_ISSUES/3579478/ai_provider_litellm/

## Environment Details
- **URL:** https://d3579478.ddev.site
- **Login:** ddev drush uli (admin/admin)
- **Drupal:** 11.1.x
- **PHP:** 8.3.30
- **Module:** ai_provider_litellm at web/modules/contrib/ai_provider_litellm
- **Module version:** 1.3.x-dev

## Test Infrastructure
- **PHPUnit:** vendor/bin/phpunit (v11.5.x via drupal/core-dev)
- **PHPCS:** vendor/bin/phpcs (Drupal + DrupalPractice standards available)
- **PHPStan:** vendor/bin/phpstan (if configured)

## MR Status
- **MR !20 diff applied:** Yes (6 files: 4 modified, 2 new)
- **Files changed:**
  - config/schema/ai_provider_litellm.schema.yml
  - src/Form/LiteLlmAiConfigForm.php
  - src/LiteLLM/LiteLlmAiClient.php
  - src/Plugin/AiGuardrail/LiteLlmGuardrail.php (NEW)
  - tests/src/Unit/LiteLlmGuardrailTest.php (NEW)
  - tests/src/Unit/LiteLlmAiProviderGuardrailTest.php (NEW)

## Ready For
- `ddev exec ../vendor/bin/phpunit modules/contrib/ai_provider_litellm/tests/`
- `ddev exec ../vendor/bin/phpcs --standard=Drupal,DrupalPractice modules/contrib/ai_provider_litellm/`
- `ddev drush uli` for browser testing
```

## Implementation Plan

### 1. Update `drupal-issue-fetcher.md`

In the "Step 5: Report" section, change the COMPLETE report format to include:
- Issue summary (title, status, category, version, author)
- Key context extracted from comments (who said what that matters)
- Classification hint based on: has MR? MR passing? status field?
- Full artifact listing with sizes

Add instructions:
```markdown
When reporting COMPLETE, you MUST include a structured summary that
eliminates the need for the caller to re-read any artifact files.
Extract and present:
1. All issue metadata fields
2. Key decisions/context from comments (who is working on it, what was decided)
3. MR status details (pipeline, mergeability, files changed)
4. A classification hint suggesting what action type this likely is
```

### 2. Update `drupal-ddev-setup.md`

In the READY report format, add:
- Exact paths to phpunit, phpcs, phpstan binaries
- List of files changed by MR (if MR was applied)
- Module path relative to DDEV docroot
- Version details (Drupal core, PHP, module)

### 3. Update caller skills to USE the enriched data

In `/drupal-issue` skill, add:
```markdown
When the fetcher agent returns, use its Summary and Classification Hint
directly. Do NOT re-read artifact files unless you need details not
included in the summary (e.g., full diff content, specific comment text).
```

In `/drupal-issue-review` skill, add:
```markdown
When the DDEV setup agent returns READY, use its Environment Details
and Test Infrastructure sections directly. Do NOT re-verify file
existence, binary paths, or module installation status.
```

## Acceptance Criteria

- [ ] Fetcher agent returns structured summary with issue metadata, key context, and classification hint
- [ ] DDEV setup agent returns environment details including exact binary paths and MR application status
- [ ] `/drupal-issue` skill does not re-read artifact files after fetcher returns
- [ ] `/drupal-issue-review` skill does not re-verify environment after DDEV agent returns
- [ ] Time between "agent returns" and "next phase starts" is under 5 seconds

## Files to Modify

1. `.claude/agents/drupal-issue-fetcher.md` - Enrich COMPLETE report format
2. `.claude/agents/drupal-ddev-setup.md` - Enrich READY report format
3. `.claude/skills/drupal-issue/SKILL.md` - Use enriched data, skip re-reading
4. `.claude/skills/drupal-issue-review/SKILL.md` - Use enriched data, skip re-verification
