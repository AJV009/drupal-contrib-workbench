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

## Hands-Free Operation

Hands-free from invocation to push gate. The canonical rules (no announcing,
no inter-phase confirmation, lazy tasks, auto-chain, stop only at push gate)
live in `CLAUDE.md` "Hands-Free Workflow (Critical)". They apply here
unmodified.

Pre-work gate: if the invocation includes `--pre-work-gate`, pass it through
when delegating to `/drupal-issue-review` (its Step 4.5 handles the gate).
Default is no gate, fully hands-free.

Additional instructions: if the prompt includes an `ADDITIONAL INSTRUCTIONS`
preamble, apply it throughout all phases and when delegating. Do not repeat
it back to the user.

## Controller Pattern (Context Management)

When running the full workflow, act as a controller that orchestrates agents:
- Prefer dispatching agents for heavy work (DDEV setup, code review, verification)
- Use enriched agent return values instead of re-reading files yourself
- Keep your own context lean for orchestration decisions
- Pass context FORWARD between phases via agent return values and artifact files
- The goal: controller stays under 50K tokens, agents get focused context

## Before You Begin

Before classifying or taking action, answer these questions internally:

1. Have I read every comment chronologically, not just the last one?
2. Do I know the current status (not what it was when filed)?
3. Are there MRs? Have I read their diffs?
4. Did a maintainer comment, and what did they say?
5. Are there related/parent/blocking issues referenced? Have I read those?
6. What branch/version is this targeting?
7. **Absence verification.** Does the issue claim something does NOT exist
   (no event, no hook, no extension point, "module X bypasses Y")? If yes,
   grep the source to confirm the absence before taking the claim at face
   value. Hard gate — false absence claims produce entire MRs built on a
   wrong premise (#3581952).
8. **Cross-issue premise sharing.** Do companion/blocking issues share an
   assumption with this one? If yes, verify the shared assumption once,
   before reviewing either.
9. **Bug class vs. reported symptom.** For scanning, validation, or
   guardrail code: does the reported symptom describe ONE manifestation
   or ALL of them? "processOutput doesn't scan text" may imply
   "processOutput doesn't scan any LLM-authored field, including tool
   calls and streamed chunks." A fix covering only the reported symptom
   comes back as Needs Work (#3580690).
10. **Pre-follow-up search.** Am I about to propose a "separate follow-up",
    file a new related issue, defer work as "out of scope", or suggest a
    defensive fix at a caller layer? If yes, run all three checks before
    mentioning the follow-up in writing:

    a. **Issue queue.** `./scripts/drupalorg issue:search <project> "<keywords>" --format=llm`
       plus `https://www.drupal.org/project/issues/search/<project>?text=<keywords>&status%5B0%5D=Open`.
       If something matches, link it (related), wait for it (if active), or
       cross-reference both directions (if sibling-but-distinct).
    b. **Existing MRs.** `./scripts/drupalorg mr:list <nid> --format=llm`
       plus a grep of recent commits on the target branch for the
       function/class you plan to touch.
    c. **Existing code pattern.** Grep the module and its immediate
       dependencies for the pattern you're about to "invent". Many
       "follow-up hardening" suggestions are actually bringing an outlier
       call site in line with an idiom that already exists 3 directories over.

    If all three come back empty, the follow-up is legitimate — state what
    was searched in the comment so the reviewer sees the check was done.
    Canonical failure (#3560681): proposed a defensive fix in
    `OpenAiBasedProviderClientBase::chat()` without running any of (a)/(b)/(c).
    Sibling issue #3582345 already existed, and
    `StreamedChatMessageIterator::assembleToolCalls()` already implemented
    the exact pattern the "follow-up" was proposing to invent.

If any answer is "no," read more before proceeding. Questions 7-10 are part
of the hands-free flow, not interruptions: each takes 60 seconds to resolve
and prevents hours of wrong-direction work.

### Rationalization Prevention

| Thought | Reality |
|---------|---------|
| "Let me just do a quick look before invoking the full workflow" | The workflow IS the quick look. Shortcuts create blind spots. |
| "I don't need to read all the comments" | Comment #7 always has the critical context you'd miss. Read them all. |
| "This issue is straightforward, I can handle it without the skill chain" | Every issue feels straightforward until you find the edge case. |
| "Let me start coding, I'll check for existing fixes later" | Coding first, searching second = duplicate MRs. Always preflight. |
| "The user just wants this done fast" | Fast and wrong wastes more time than thorough and right. |
| "I already know what kind of issue this is" | Classify AFTER reading, not before. Assumptions miss context. |
| "Resonance check is slow, let me just classify" | Resonance runs in under 2 minutes and catches scope-expansion cases the classifier would miss entirely. The user had to manually notice these in session evidence — that is the problem this step solves. |
| "The issue says no extension point exists, so we need one" | Verify the absence first. The AI module's ProviderProxy dispatches events for ALL calls. Issue #3581952 was built on a false "no events" claim. |
| "The MR code looks correct, so the approach must be right" | Correct code on a wrong premise is still wrong. Check the premise before the code. |

## Gotchas

- **Read artifacts, not the browser.** `DRUPAL_ISSUES/{id}/artifacts/` has
  `issue.json`, `comments.json`, `merge-requests.json`, `mr-{iid}-diff.patch`,
  `mr-{iid}-discussions.json`. The fetcher agent pre-populates these. No
  need to re-fetch from the page.
- **Comments and MR discussions are separate data sources.** `comments.json`
  is the d.o thread; `mr-{iid}-discussions.json` is the GitLab inline review
  (with file/line positions). Reading only one misses half the review.
- **MR freshness check before code review.** A passing GitLab pipeline does
  NOT guarantee the MR applies to current target branch. Always dry-run
  `git apply --check` first (see Step 2 MR Freshness Check).
- **Companion issues share premises.** If issue B says "blocked by A",
  verify A's premise critically BEFORE reviewing either. Approving B after
  approving A independently means missing the same flaw twice (#3581952,
  #3581955).
- **"[x] AI Assisted Issue" tag signals extra scrutiny.** Descriptions
  often sound authoritative but contain subtle inaccuracies about
  signatures, behavior, or claimed absences.
- **drupal.org `api-d7` rejects full-text search.** `text=` returns HTTP 412.
  Use the UI search for keyword queries:
  `https://www.drupal.org/project/issues/search/<project>?text=<keywords>`.

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

## Step 0.5: Resonance Check (MANDATORY)

After the fetcher returns COMPLETE or PARTIAL, **immediately** dispatch the
`drupal-resonance-checker` agent. Do not skip this — it catches scope
expansion and duplicate scenarios that would otherwise require the user to
notice manually mid-work.

```
Dispatch: drupal-resonance-checker
Inputs:
  issue_id = {issue_id}
  artifacts_dir = DRUPAL_ISSUES/{issue_id}/artifacts
```

The agent runs `.claude/skills/drupal-issue/scripts/resonance_search.py` and
returns a `RESONANCE_REPORT` with candidates bucketed into:

- **DUPLICATE_OF** (confidence >= 80) — strong signal that this issue is a
  duplicate of an existing one. Agent includes a draft close-as-duplicate
  comment template. Classification gains category **J** as the top candidate.
- **SCOPE_EXPANSION_CANDIDATE** (confidence 60-79) — this issue overlaps with
  an active/in-progress issue in the same module. Category **J** is a valid
  option but classification MUST still run normally.
- **RELATED_TO** (confidence 40-59) — informational only, no flow change.
- **NONE** — proceed with classification as usual.

**Read the RESONANCE_REPORT before Step 1** and incorporate it into your
classification decision. Specifically:

- If the report suggests category J, read the candidate issue via
  `./scripts/fetch-issue --mode full --issue {candidate_nid} --out DRUPAL_ISSUES/{candidate_nid}/artifacts`
  to verify the overlap is real (confidence is heuristic, not ground truth).
- If the candidate is an active MR the user has push access to, consider
  whether to fold the current issue into the existing MR rather than opening
  a new one.
- If the report returns NONE, proceed directly to Step 1.

The report is written to `DRUPAL_ISSUES/{issue_id}/workflow/00-resonance.md`
(human-readable) and `00-resonance.json` (machine-readable) for any
downstream skill that needs to reread it.

**bd write (best-effort):** Mirror the resonance report to bd:

```bash
if [[ -n "$BD_ID" ]] && [[ -f "$WORKFLOW_DIR/00-resonance.json" ]]; then
  scripts/bd-helpers.sh phase-resonance "$BD_ID" "$WORKFLOW_DIR/00-resonance.json"
fi
```

**Empty bd is normal.** The workbench bd database started empty per ticket
028 (no backfill). Layer A (bd-local) will return zero candidates for the
first N issues worked after this ships. Layer B (d.o) carries the load
until bd fills up organically.

**Layer B degradation is survivable.** If the scorer reports
`layer_b.status: "degraded"` (network failure or d.o API issue), continue
classification normally; do not block on resonance.

## Step 1: Read the issue

Accept either format:
- `https://www.drupal.org/project/{project}/issues/{id}`
- Just the number: `3577386`

### Primary path: API artifacts (from Step 0)

Read the artifacts fetched by the `drupal-issue-fetcher` agent:
- `artifacts/issue.json` for sidebar metadata (status, version, component, priority, tags)
- `artifacts/comments.json` for the full comment thread (already numbered and chronological)
- `artifacts/merge-requests.json` for MR details and the primary MR flag
- `artifacts/mr-{iid}-diff.patch` for MR diffs
- `artifacts/mr-{iid}-discussions.json` for MR review discussions -- read these **in conjunction with** `comments.json` to get the full picture. Issue comments capture the high-level thread on drupal.org, while MR discussions capture inline code review feedback on specific files/lines in GitLab. Both are needed for complete understanding of what reviewers asked for and what was addressed.

The API artifacts contain all textual data: metadata, comments with HTML bodies, MR diffs, and review discussions. No browser is needed for reading issue content.

### When artifacts are NOT available (Step 0 failed)

Fall back to `./scripts/fetch-issue --mode refresh --issue <url-or-id> --project <project> --out DRUPAL_ISSUES/{issue_id}/artifacts --gitlab-token-file git.drupalcode.org.key` to force a fresh fetch that bypasses caches. For issues with embedded screenshots that need visual inspection, use `agent-browser` (see the `agent-browser` skill for usage).

### What to read (in order)

1. **Sidebar metadata** -- status, version, component, tags, assigned
2. **Issue body** -- problem, steps to reproduce, proposed resolution
3. **Every single comment** -- chronologically. Don't skip any.
4. **MR descriptions and diffs** -- if merge requests exist, read them
5. **Linked/related issues** -- if comments reference other issues (like a
   parent issue or blocking issue), read those too
6. **File attachments** -- screenshots referenced in comment HTML can be
   viewed with `agent-browser` if visual inspection is needed

### What to extract

- What is the **current state** of the issue? (not what it was when filed)
- What did the **last commenter** ask for or flag?
- What did **maintainers** say? (their usernames usually show in RTBC/commit
  history or have the "maintainer" badge)
- Is there a **parent issue**? What's its status?
- Are there **blocking issues** or **related issues** that provide context?
- What **version/branch** is this targeting?

### Verify claims against source code

Issue descriptions, especially on issues tagged `[x] AI Assisted Issue` or
`[x] AI Generated Code`, can sound authoritative while being subtly wrong.
If you will write code or documentation based on a claim about how something
works, read the source file first. 30 seconds of verification prevents a
"Needs work" round-trip.

- **Claims about behavior** (service methods, signatures, config effects):
  open the source, confirm the method does what the issue says. Watch for
  conflations (e.g., "structured output" vs "extracting from unstructured text").
- **Claims of absence** ("no event exists", "no hook", "module X bypasses Y"):
  grep for the thing the issue says is missing. Trace the call chain from
  entry point through to the provider/service call and check every layer.
  Verifying an absence is harder than verifying a presence, so it needs more
  diligence. Accepting a false absence claim means an entire MR built on a
  wrong premise (see #3581952).
- **Claims for new extension points** (events, hooks, alter hooks): before
  reviewing the implementation, check whether the parent module already has
  a generic extension point that covers the case. Example: the AI module's
  `PreGenerateResponseEvent` fires for ALL provider calls via `ProviderProxy`,
  including submodule calls.
- **Structural/placement changes** (nav entries, config sections, menu
  hierarchy): filesystem path is not a reliable indicator of conceptual
  category. Read how existing files already cross-link the items being placed
  before deciding the target location.

## Step 2: Classify the action needed

After reading, determine which category the issue falls into and **immediately
take action**. Do not present the classification to the user or ask for confirmation.

### MR Freshness Check (MANDATORY for categories B and I)

Before deciding code-review-only vs full DDEV, verify the MR still applies
to the current target branch. This takes under 30 seconds and prevents
reviewing stale diffs:

1. Clone the target branch (shallow):
   `git clone --depth=1 -b {target_branch} https://git.drupalcode.org/project/{project}.git /tmp/mr-check-{issue_id}`
2. Fetch the MR diff and dry-run apply:
   `./scripts/fetch-issue --mode mr-diff --issue {issue_id} --mr-iid {mr_id} --out /tmp/mr-{mr_id}.diff --gitlab-token-file git.drupalcode.org.key`
   `cd /tmp/mr-check-{issue_id} && git apply --check /tmp/mr-{mr_id}.diff`
3. If `--check` **FAILS**: the MR is stale. Do NOT review the code. Instead:
   - Classify as "MR needs rebase"
   - Draft a comment (via `/drupal-issue-comment`) noting the MR no longer
     applies cleanly, listing which files/hunks conflict
   - Skip to `/drupal-issue-comment`. Do NOT mark RTBC.
4. If `--check` **PASSES**: proceed with Review Mode Detection below.
5. Clean up: `rm -rf /tmp/mr-check-{issue_id}`

A passing GitLab pipeline does NOT guarantee the MR applies to current
upstream. The pipeline runs against the MR's own branch base, which may
be behind the target branch.

### Review Mode Detection (Code-Review-Only vs Full DDEV)

For categories B (review MR) and I (re-review), determine if DDEV is needed:
- **MR pipeline passing** + **feature request** (not bug) + **user said "review"** + **diff has NO .css/.twig/.theme/.js files** -> Code-review-only mode (no DDEV)
- **Bug report** or **need to reproduce** or **need to run tests** -> Full DDEV mode
- **Diff includes .css, .twig, .theme, or .js files** -> Full DDEV mode (visual verification required, regardless of category)

Code-review-only skips `/drupal-issue-review` DDEV phases and goes straight
to static diff review + `/drupal-issue-comment`. This takes ~10 min vs ~25 min.

CSS, Twig, and template changes cannot be verified by reading code alone.
A single class rename can break icon positioning or miss entire components
that also need updating. Always use Full DDEV mode when the diff touches
frontend files so the verifier agent can take screenshots.

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

### Action categories

| # | Condition | Action |
|---|---|---|
| A | Bug report, not yet confirmed, reviewer couldn't reproduce, or reopened | Invoke `/drupal-issue-review` to set up env + reproduce |
| B | MR exists and needs review OR marked "Needs work" with specific feedback | Invoke `/drupal-issue-review` to set up env with MR applied |
| C | Fix exists on one branch, needs porting (or maintainer asked for changes from a parent issue) | Read source MR, read target branch, adapt, invoke `/drupal-contribute-fix` to package |
| D | Maintainer asked to retarget to a different version/branch | Handle directly: update the MR target branch; stop at push gate |
| F | Issue just needs a knowledgeable reply | Invoke `/drupal-issue-comment`, present draft |
| H | Fix already committed on one branch, needs backport | Cherry-pick, resolve conflicts, test, package; stop at push gate |
| I | MR looks good, just needs confirmation it works | Invoke `/drupal-issue-review` to verify, then `/drupal-issue-comment` for confirming comment. Do NOT refactor or "improve" working code |
| J | Resonance check flagged this as DUPLICATE_OF (>=80% confidence) or SCOPE_EXPANSION_CANDIDATE (>=60%) with an active target | Verify the overlap by fetching the candidate issue. If confirmed: draft a close-as-duplicate or fold-into-existing comment via `/drupal-issue-comment`, stop at push gate. If the overlap is thematic not actionable, fall through to categories A-I. |

> **Note on post-fix recovery:** If the solution-depth gate at
> `/drupal-contribute-fix` Step 2.5 returns `failed-revert`, the fix skill
> handles the revert-and-rerun internally. The A-J classification above is
> unaffected — there is no category K for "post-fix retry". The controller
> does not need to do anything special; it just sees `/drupal-contribute-fix`
> take longer because it ran twice.

Categories with escalation logic:

**E) Respond to reviewer feedback.** Address each point, then stop at push gate.

- *Test check (bug fixes):* before pushing, verify the MR has test coverage
  for the bug scenario. If not, write one. A bug fix without a test that
  proves the bug existed is incomplete, even if the code change is tiny.
  Contributing a missing test is more valuable than paragraphs of analysis
  in a comment. When in doubt, escalate to `/drupal-contribute-fix`.
- *Scope escalation:* if addressing the feedback requires creating NEW files
  or rewriting existing files from scratch (more than ~30 lines of new code,
  or placing files in directories not verified against project structure),
  escalate to `/drupal-contribute-fix`. A rewrite is not "responding to
  feedback"; it is writing new code that needs the full reviewer/verifier gates.

**G) Write a fix from scratch.** Issue describes a bug with no MR, or existing
MRs were abandoned. Invoke `/drupal-issue-review` for reproduction, then
`/drupal-contribute-fix` for the fix.

## Step 2.5: Persist classification (MANDATORY)

After deciding the category and gathering the metadata in Step 2, write
the classification artifact and mirror it to bd. The disk write is
required; the bd mirror is best-effort (failure does not fail the skill).

This step is the contract enforced by `/drupal-issue-review`'s
"Classification Sentinel Check" preflight. If you skip Step 2.5,
downstream skills will detect the missing classification and reinstate
this skill (see `docs/workflow-state-files.md`).

### Write the classification artifact

```bash
ISSUE_ID={issue_id}
SENTINEL="$CLAUDE_PROJECT_DIR/DRUPAL_ISSUES/$ISSUE_ID/workflow/00-classification.json"
mkdir -p "$(dirname "$SENTINEL")"

# Preserve launched_at and session_id from the sentinel if present
LAUNCHED_AT=""
SESSION_ID=""
if [ -f "$SENTINEL" ]; then
  LAUNCHED_AT=$(jq -r '.launched_at // ""' "$SENTINEL")
  SESSION_ID=$(jq -r '.session_id // ""' "$SENTINEL")
fi

cat > "$SENTINEL" <<JSON
{
  "issue_id": $ISSUE_ID,
  "status": "classified",
  "launched_at": "$LAUNCHED_AT",
  "session_id": "$SESSION_ID",
  "classified_at": "$(date -Iseconds)",
  "category": "{A-J}",
  "category_description": "{one-line description from the action table}",
  "module": "{machine name}",
  "module_version": "{version}",
  "component": "{component name or null}",
  "existing_mr": {"iid": {iid_or_null}, "source_branch": "{branch_or_null}", "apply_clean": null},
  "rationale": "{1-2 sentences explaining the classification decision}"
}
JSON
```

The substitutions in `{...}` come from your Step 1 reading of the issue:
- `{A-J}` → the letter from the classification action table
- `{module}`, `{version}`, `{component}` → from `artifacts/issue.json`
- `{iid_or_null}` → the existing MR's iid as a number, OR the literal `null` (no quotes) if no MR exists
- `{branch_or_null}` → the source branch as a quoted string, OR `null`
- `{rationale}` → your own 1-2 sentence reasoning

### Mirror to bd (best-effort)

```bash
BD_ID=$(scripts/bd-helpers.sh ensure-issue "$ISSUE_ID" "Drupal issue $ISSUE_ID: {issue title}" "{module}")
if [[ -n "$BD_ID" ]]; then
  scripts/bd-helpers.sh phase-classification "$BD_ID" "$WORKFLOW_DIR/00-classification.json"
fi
```

Best-effort: all bd writes go through `scripts/bd-helpers.sh` which
handles failures internally (logs to stderr, never blocks). The workflow
file is the source of truth; bd is the queryability layer for cross-issue
memory (ticket 034).

### Why this step exists

Ticket 023 established the "every phase writes an artifact" contract.
Audit on 2026-04-09 found 5 recent issues missing
`00-classification.json` despite being post-ticket-023, indicating the
prose contract was leaking under load. Ticket 031 added the launcher
sentinel + reinstate flow to enforce mechanically what prose was failing
to enforce.

### Rationalization Prevention (Step 2.5)

| Thought | Reality |
|---|---|
| "Step 3 will pick this up anyway, I can skip the disk write" | Step 3 chains to a downstream skill that reads the sentinel. If you skip, the downstream skill reinstates this skill. You will run twice. |
| "The bd write is failing, I should fix it before continuing" | bd is best-effort. Log the failure and continue. The workflow file is the source of truth. |
| "I already wrote the classification in my reasoning, the JSON is redundant" | The JSON is the durable artifact. Your reasoning is in your context window only. |


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

## Reading related issues

When comments reference `[#NNNNNN]` or parent issues, go read them. "See
parent issue" = read for context; "missing changes from #X" = read #X's diff;
"related to" = optional but often useful; "duplicate of" = check if #X was
resolved; "blocked by" = check if #X is fixed and this is now unblocked.

### Cross-reference validation for companion issues

When two issues share a premise (e.g., "ai_ckeditor needs a new event" in
#3581952 and "ai_context subscribes to that new event" in #3581955), verify
the shared premise holds before reviewing EITHER issue independently. If you
review and approve Issue A, then later review Issue B which depends on A's
premise, you will miss the same flaw twice.

Concrete check: if Issue B says "blocked by Issue A" or "consumes the event
from Issue A," read Issue A's premise critically FIRST. If Issue A's premise
is false, Issue B is also invalid regardless of how clean its code is.

This was the failure pattern in #3581952/#3581955: both issues assumed
ai_ckeditor lacked an extension point. We reviewed both independently and
approved both without noticing the shared false premise.

## Working with MRs

### Reading an MR diff
```
https://git.drupalcode.org/project/{project}/-/merge_requests/{id}/diffs
```

### Applying an MR locally for testing
```bash
cd web/modules/contrib/{module}
# Stream the MR diff from our consolidated fetcher and pipe to git apply.
# --out - writes to stdout, --issue provides the project context (URL form
# derives it automatically; bare nid needs --project).
./scripts/fetch-issue --mode mr-diff --issue {issue_id} --mr-iid {id} --out - --gitlab-token-file git.drupalcode.org.key | git apply
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

See `examples/classification-walkthroughs.md` for worked examples of how
real issue states map to the A-I categories above.
