---
name: drupal-issue
description: >
  Generic entry point for working on any drupal.org issue. Invoke with
  `/drupal-issue <issue-url-or-number>`. Reads the issue and all comments
  carefully, figures out what kind of action is needed, and either handles
  it directly or delegates to the right companion skill. Covers: bug
  reproduction, version bumps, MR adaptation, comment replies, reviews,
  cherry-picks, porting between branches, and general triage.
license: GPL-2.0-or-later
metadata:
  author: ajv009
  version: "1.0.0"
---

# drupal-issue

> **IRON LAW:** NO ACTION WITHOUT READING EVERY COMMENT. Skipping comments leads to duplicate work, wrong classifications, and wasted reviewer time.

The "figure out what to do" skill. Reads a d.o issue, understands the full
context, and takes the right action.

Invoke: `/drupal-issue <issue-url-or-number> [--pre-work-gate]`

## What this skill does

1. **Reads the issue thoroughly** — title, description, ALL comments, status
   changes, MRs, linked issues, file attachments
2. **Classifies what action is needed** — see action types below
3. **Immediately delegates** to the right companion skill (no user confirmation needed)

This is the skill you use when you're not sure which other skill to use.

## Hands-Free Operation (CRITICAL)

This skill runs **hands-free from invocation to push gate.** The ONLY point
where you stop and wait for user input is BEFORE pushing to a remote.

Rules:
- Do NOT announce what you are about to do. Just do it.
- Do NOT present the classification and ask "should I proceed?" Just proceed.
- Do NOT create all tasks upfront. Create them lazily as you start each phase.
- Do NOT wait for user confirmation between phases. Auto-chain to the next skill.
- The workflow stops ONCE: at the push gate in `/drupal-contribute-fix`.
- If there is nothing to push (review-only, comment-only), stop when presenting the draft comment for user review.

### Pre-Work Gate (optional)

If the invocation includes `--pre-work-gate`, the workflow gains an additional stop
point AFTER analysis/reproduction but BEFORE writing any code fix. This lets the
user review findings and steer the approach before the agent invests time in a fix.

When `--pre-work-gate` is present:
- Pass it through when delegating to `/drupal-issue-review`
- `/drupal-issue-review` will present the pre-work gate and wait for user input
- The user chooses: proceed with fix, comment only, adjust approach, or abort
- After the user responds, the workflow resumes hands-free until the push gate

When `--pre-work-gate` is NOT present (default): fully hands-free as before.

### Additional Instructions

If the prompt includes a preamble starting with `ADDITIONAL INSTRUCTIONS`, treat
it as session-level guidance. Apply these instructions throughout all phases and
when delegating to companion skills. Do not repeat them back to the user.

## Controller Pattern (Context Management)

When running the full workflow, act as a controller that orchestrates agents:
- Prefer dispatching agents for heavy work (DDEV setup, code review, verification)
- Use enriched agent return values instead of re-reading files yourself
- Keep your own context lean for orchestration decisions
- Pass context FORWARD between phases via agent return values and artifact files
- The goal: controller stays under 50K tokens, agents get focused context

## Before You Begin

Before classifying or taking action, answer these questions internally:
1. Have I read EVERY comment chronologically (not just the last one)?
2. Do I know the CURRENT status (not what it was when filed)?
3. Are there MRs? Have I read their diffs?
4. Did any maintainer comment? What did they say?
5. Are there related/parent/blocking issues referenced? Have I read those?
6. What branch/version is this targeting?

If any answer is "no," go read more before proceeding.

### Rationalization Prevention

| Thought | Reality |
|---------|---------|
| "Let me just do a quick look before invoking the full workflow" | The workflow IS the quick look. Shortcuts create blind spots. |
| "I don't need to read all the comments" | Comment #7 always has the critical context you'd miss. Read them all. |
| "This issue is straightforward, I can handle it without the skill chain" | Every issue feels straightforward until you find the edge case. |
| "Let me start coding, I'll check for existing fixes later" | Coding first, searching second = duplicate MRs. Always preflight. |
| "The user just wants this done fast" | Fast and wrong wastes more time than thorough and right. |
| "I already know what kind of issue this is" | Classify AFTER reading, not before. Assumptions miss context. |

## Step 0: Fetch issue data

Immediately dispatch the `drupal-issue-fetcher` agent (no preamble, no announcement):

1. Parse the issue URL to extract project name and issue ID
2. Dispatch the `drupal-issue-fetcher` agent with:
   - Issue URL or ID
   - Output directory: `DRUPAL_ISSUES/{issue_id}/artifacts`
3. Wait for the agent to report COMPLETE, PARTIAL, or FAILED
4. If COMPLETE: use the agent's **Summary** and **Classification Hint** directly.
   Do NOT re-read artifact files unless you need details not in the summary
   (e.g., full diff content, specific comment text for quoting).
5. If PARTIAL: proceed with available data, note gaps
6. If FAILED: fall back to browser-based reading (original approach)

The artifacts are at `DRUPAL_ISSUES/{issue_id}/artifacts/`:
- `issue.json` for metadata (title, status, version, component, author, tags, etc.)
- `comments.json` for the complete comment thread (numbered, chronological)
- `merge-requests.json` for all MRs with the primary MR flagged
- `mr-{iid}-diff.patch` for MR diffs
- `mr-{iid}-discussions.json` for GitLab review discussions (general comments + inline diff comments with file/line positions)

## Step 1: Read the issue

Accept either format:
- `https://www.drupal.org/project/{project}/issues/{id}`
- Just the number: `3577386`

Use the browser (Claude Chrome) to read the full issue page. WebFetch can work
but may miss nuance in long threads — prefer the browser for issues with many
comments.

### What to read (in order)

1. **Sidebar metadata** — status, version, component, tags, assigned
2. **Issue body** — problem, steps to reproduce, proposed resolution
3. **Every single comment** — chronologically. Don't skip any.
4. **MR descriptions and diffs** — if merge requests exist, read them
5. **Linked/related issues** — if comments reference other issues (like a
   parent issue or blocking issue), read those too
6. **File attachments** — screenshots, videos, patches. View screenshots
   if they exist.

### When artifacts are available (Step 0 succeeded)

Read the artifacts instead of scrolling the browser:
- `artifacts/issue.json` for sidebar metadata (status, version, component, priority, tags)
- `artifacts/comments.json` for the full comment thread (already numbered and chronological)
- `artifacts/merge-requests.json` for MR details and the primary MR flag
- `artifacts/mr-{iid}-diff.patch` for MR diffs
- `artifacts/mr-{iid}-discussions.json` for MR review discussions — read these **in conjunction with** `comments.json` to get the full picture. Issue comments capture the high-level thread on drupal.org, while MR discussions capture inline code review feedback on specific files/lines in GitLab. Both are needed for complete understanding of what reviewers asked for and what was addressed.
- Use the browser ONLY for: viewing screenshots, visual verification, or when artifacts are incomplete

### When artifacts are NOT available (Step 0 failed)

Fall back to the original browser-based approach described above.

### What to extract

- What is the **current state** of the issue? (not what it was when filed)
- What did the **last commenter** ask for or flag?
- What did **maintainers** say? (their usernames usually show in RTBC/commit
  history or have the "maintainer" badge)
- Is there a **parent issue**? What's its status?
- Are there **blocking issues** or **related issues** that provide context?
- What **version/branch** is this targeting?

### Verify claims against source code (especially AI-generated issues)

If the issue describes **what code does** (service behavior, method signatures,
configuration effects), don't take it at face value. Read the actual source files
and verify:

- Does the service/method actually work as described?
- Are the use cases described accurate, or does the description conflate similar
  but distinct concepts? (e.g., "structured output" vs "extracting from unstructured text")
- Are function signatures, parameter names, and return types correct?
- For **structural/placement changes** (nav entries, config organization, menu
  hierarchy): check how existing files already reference or cross-link the items
  being placed. Filesystem path alone is not a reliable indicator of where
  something belongs conceptually. Read the surrounding documentation to understand
  the project's information architecture before deciding placement.

This is especially important for issues tagged "[x] AI Assisted Issue" or
"[x] AI Generated Code", where descriptions often sound authoritative but
contain subtle inaccuracies.

**Rule of thumb:** If you will write code or documentation based on an issue's
description of how something works, read the source file first. 30 seconds of
verification prevents a "Needs work" round-trip.

## Step 2: Classify the action needed

After reading, determine which category the issue falls into and **immediately
take action**. Do not present the classification to the user or ask for confirmation.

### Review Mode Detection (Code-Review-Only vs Full DDEV)

For categories B (review MR) and I (re-review), determine if DDEV is needed:
- **MR pipeline passing** + **feature request** (not bug) + **user said "review"** -> Code-review-only mode (no DDEV)
- **Bug report** or **need to reproduce** or **need to run tests** -> Full DDEV mode

Code-review-only skips `/drupal-issue-review` DDEV phases and goes straight
to static diff review + `/drupal-issue-comment`. This takes ~10 min vs ~25 min.

### Detecting Contrib/Core Bugs (When to Trigger /drupal-contribute-fix)

When reading an issue, look for signals that this involves a contrib/core bug:

**Error pattern recognition:**
```
# Error FROM contrib/core -> triggers /drupal-contribute-fix
Drupal\metatag\MetatagManager->build()
docroot/modules/contrib/mcp/src/Plugin/Mcp/General.php
web/modules/contrib/webform/src/...
core/lib/Drupal/Core/...

# Error in CUSTOM module -> may not need contribute-fix
# (unless custom code triggers a bug in contrib/core)
modules/custom/mymodule/src/...
```

**Path triggers** (user mentions or stack trace shows):
- `web/core/`, `web/modules/contrib/`, `web/themes/contrib/`
- `docroot/core/`, `docroot/modules/contrib/`, `docroot/themes/contrib/`

**Conversational triggers** (user says):
- Any contrib module name (metatag, webform, paragraphs, ai, etc.) + problem indicator (error, bug, broken, not working, exception)
- "Acquia/Pantheon/Platform.sh" + module problem

When these patterns are detected, `/drupal-contribute-fix` must be invoked for
preflight search before any code changes.

### A) Reproduce a bug
The issue reports a bug and either nobody confirmed it, a reviewer couldn't reproduce, or it was reopened.

**Action:** Immediately invoke `/drupal-issue-review` to set up an environment and reproduce.

### B) Review/test an existing MR
An MR exists and needs review, or was marked "Needs work" with specific feedback.

**Action:** Immediately invoke `/drupal-issue-review` to set up an env with the MR applied.

### C) Adapt/port code between branches
A fix exists on one branch and needs porting to another, or a maintainer asked for changes from a parent issue.

**Action:**
1. Read the source issue/MR to understand what was done
2. Read the target branch to understand divergence
3. Adapt the code
4. Immediately invoke `/drupal-contribute-fix` to package the result

### D) Version bump / update target
A maintainer commented asking to retarget to a different version or branch.

**Action:** Handle directly. Update the MR target branch. Stop before push for user confirmation.

### E) Respond to reviewer feedback
A reviewer or maintainer left specific feedback.

**Action:** Address each point, then stop before push for user confirmation.

**Scope escalation:** If addressing the feedback requires creating NEW files
or rewriting existing files from scratch (not just editing a few lines),
escalate to the full skill chain: invoke `/drupal-contribute-fix` to package
the result. A rewrite is not "responding to feedback"; it is writing new code
that needs the reviewer and verifier gates. The threshold: if you are writing
more than ~30 lines of new code, or placing files in directories you haven't
verified against the project's canonical structure, escalate.

### F) Just reply with context
The issue just needs a knowledgeable reply.

**Action:** Immediately invoke `/drupal-issue-comment`, then present the draft for user review.

### G) Write a fix from scratch
The issue describes a bug with no MR yet, or existing MRs were closed/abandoned.

**Action:** Immediately invoke `/drupal-issue-review` for reproduction, then `/drupal-contribute-fix` for the fix.

### H) Cherry-pick or backport
A fix was committed on one branch and needs backporting.

**Action:** Cherry-pick, resolve conflicts, test, package. Stop before push for user confirmation.

### I) Re-review an existing MR (no code changes needed)
The MR already looks good. Just needs confirmation it works.

**Action:** Immediately invoke `/drupal-issue-review`, verify the fix works,
then invoke `/drupal-issue-comment` to draft a confirming comment.
Do NOT refactor, add tests, or "improve" working code.

## Step 3: Take action

Based on the classification, **immediately** either:

1. **Handle it directly** — for simple actions (version bump, reply, cherry-pick)
2. **Delegate to a companion skill** — for complex actions. Invoke the Skill tool NOW, do not ask the user first.

### Companion Skills (Explicit Handoffs)

| When | REQUIRED NEXT SKILL | Purpose |
|------|---------------------|---------|
| Need to reproduce/test | `/drupal-issue-review` | Set up env, reproduce bug, test MR |
| Need to write/package a fix | `/drupal-contribute-fix` | Fix code, add tests, package for MR |
| Need to write a d.o comment | `/drupal-issue-comment` | Draft conversational HTML comment |
| Need code review | `drupal-reviewer` agent | Review before submitting |
| Need to verify a fix | `drupal-verifier` agent | Verify with drush eval, curl tests |
| Need coding standards check | `/drupal-coding-standards` | PHPCS, PHPStan, file-type review |

**CRITICAL:** Invoke companion skills via the Skill tool. Never inline their behavior from memory.

**Test coverage is enforced by `/drupal-contribute-fix`.** See that skill for the full test gate requirements.

## Progress Tracking

Use lazy task creation. Do NOT create all tasks upfront. Create each task
only when you START that phase. The first thing after invocation should be
dispatching the fetcher agent, not creating tasks.

1. Create task when starting a phase (status: in_progress)
2. Mark completed when done
3. Create next task when starting next phase

## Reading related issues

When comments reference other issues like `[#3491351]` or link to parent issues,
**go read them**. Common patterns:

- **"See parent issue #X"** — The parent has context you need. Read it.
- **"This MR is missing changes from #X"** — Go read #X's MR diff to see
  what's missing.
- **"Related to #X"** — Might have useful context or a fix you can reuse.
- **"Duplicate of #X"** — Check if #X was resolved. If so, this one might
  need closing.
- **"Blocked by #X"** — Check #X's status. If it's fixed, this one might
  be unblocked now.

## Working with MRs

### Reading an MR diff
```
https://git.drupalcode.org/project/{project}/-/merge_requests/{id}/diffs
```

### Applying an MR locally for testing
```bash
cd web/modules/contrib/{module}
curl -L "https://git.drupalcode.org/project/{project}/-/merge_requests/{id}.diff" | git apply
```

### Checking MR pipeline status
Look at the issue page — pipeline status shows next to the MR link (green check,
red X, or yellow circle).

## Output

The output depends on the action type:

- **Bug reproduction** → screenshots + comment HTML (via `/drupal-issue-review` + `/drupal-issue-comment`)
- **Code fix** → MR artifacts (via `/drupal-contribute-fix`)
- **Comment/reply** → `issue-comment-{id}.html` (via `/drupal-issue-comment`)
- **Review** → inline feedback summary
- **Triage** → summary of findings + recommended next steps

Do NOT stop to tell the user what you found before acting. Just act. The user will see your work in the push gate summary.

## Examples

```
/drupal-issue 3561693
→ Reads issue, sees it's "Needs work" because reviewer couldn't reproduce
→ Classifies as: Reproduce a bug + respond to reviewer
→ Delegates to /drupal-issue-review, then drafts comment

/drupal-issue 3577386
→ Reads issue, sees maintainer flagged missing third-party module changes
→ Classifies as: Adapt code (port from parent issue)
→ Reads parent issue #3491351, identifies missing pieces, adapts MR

/drupal-issue https://www.drupal.org/project/ai/issues/3558728
→ Reads issue, sees it's RTBC with a working MR
→ Classifies as: Review/test existing MR
→ Reviews the code, optionally sets up env to verify

/drupal-issue 3577812
→ Reads issue, sees it was closed as "cannot reproduce"
→ Classifies as: Just reply with context
→ Drafts a comment explaining when/how it can be reproduced

/drupal-issue 3580001
→ Reads issue, sees "Needs review" with a clean MR and no objections
→ Classifies as: Re-review (no code changes needed)
→ Sets up env, verifies the fix, drafts a confirming comment
→ Does NOT add "improvements" or refactor working code
```
