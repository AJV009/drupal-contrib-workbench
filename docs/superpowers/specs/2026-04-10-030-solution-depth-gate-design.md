# Design: Solution-Depth Gate (Ticket 030)

**Date:** 2026-04-10
**Ticket:** `docs/tickets/030-solution-depth-gate.md`
**Status:** Design approved, ready for implementation plan
**Phase:** Phase 2.4 (Workflow improvements)

## Problem

The `/drupal-contribute-fix` workflow tends to propose narrow/shallow fixes
when an architectural fix exists. The user has to interject mid-session and
demand "the proper way." Two real session examples (3581952, 3583760) show
the user manually surfacing the architectural option after the workflow had
already committed to the narrow one.

We want the workflow to surface the architectural alternative **without** user
prompting — at two distinct moments:

1. **Before** any code is written (pre-fix) — the common case for autonomous
   runs where the user isn't watching closely.
2. **After** the fix is drafted (post-fix) — the rare case where the pre-fix
   gate was wrong and the hack smell only becomes visible once the code
   exists.

## Solution summary

A new subagent `drupal-solution-depth-gate` with two modes, owned by
`/drupal-contribute-fix` so the gate is unskippable regardless of entry
point. Pre-fix mode runs always. Post-fix mode runs conditionally based on
three triggers: a reasoning-driven decision from the pre-fix agent
(`must_run_post_fix`), and two objective patch-level facts (`lines > 50`,
`files > 3`).

Failure path: if the post-fix gate returns `score >= 4`, the controller
writes a recovery brief, preserves the attempt-1 diffs under
`.drupal-contribute-fix/attempt-1-narrow/`, destructively reverts the
module working tree, and re-invokes `/drupal-contribute-fix --approach
architectural --recovery-brief <path>`. Circuit breaker: maximum 2 attempts
per issue before escalating to the user.

## Architecture

```
/drupal-issue-review
    │
    ├─ classifies (A-J), reproduces, static-reviews
    ├─ emits workflow/01-review-summary.json
    ├─ emits workflow/01a-depth-signals.json      ← raw context for the gate
    │    { category, resonance_bucket, resonance_report_path,
    │      reviewer_narrative, recent_maintainer_comments,
    │      proposed_approach_sketch }
    │
    v  auto-chain
/drupal-contribute-fix
    │
    ├─ FIRST STEP: preflight (unchanged)
    │
    ├─ STEP 0.5: drupal-solution-depth-gate-pre (opus)    ← ALWAYS runs
    │     reads 01-review-summary.json + 01a-depth-signals.json
    │     writes workflow/01b-solution-depth-pre.md + .json
    │     bd update <bd-id> --design "$(cat 01b-solution-depth-pre.md)"
    │     returns decision = narrow | architectural | hybrid
    │     returns must_run_post_fix = true | false
    │
    ├─ TDD loop (test first, minimal fix, validate) — existing
    │
    ├─ PRE-PUSH QUALITY GATE
    │     Step 0: CI parity
    │     Step 1-2: phpcs, phpunit
    │     Step 2.5: drupal-solution-depth-gate-post (sonnet) ← CONDITIONAL
    │         runs if pre_fix.must_run_post_fix OR lines>50 OR files>3
    │         reads the patch, workflow/01b-*.md
    │         writes workflow/02b-solution-depth-post.md + .json
    │         bd comment <bd-id> "bd:phase.solution_depth.post ..."
    │         if score >= 4 → FAILURE PATH (below)
    │     Step 3: spec reviewer
    │     Step 4: code reviewer
    │     Step 5: verifier
    │     Step 6: draft comment
    │
    └─ PUSH GATE (unchanged)
```

## Components

### 1. New agent files (two, not one)

Split because Claude Code's agent frontmatter takes a single `model:` value
per file; we need opus for pre-fix and sonnet for post-fix.

**`.claude/agents/drupal-solution-depth-gate-pre.md`** — opus model.

Frontmatter:

```yaml
---
name: drupal-solution-depth-gate-pre
description: Pre-fix solution-depth analysis for /drupal-contribute-fix.
  Proposes narrow vs architectural approaches BEFORE code is written, using
  review artifacts, resonance report, maintainer comments, and reviewer
  findings. Returns narrow|architectural|hybrid decision plus a
  must_run_post_fix flag for the controller. Fresh subagent to avoid the
  controller's anchoring bias on whatever it already proposed.
tools: Read, Grep, Glob, Bash
model: opus
---
```

Inputs (via command args):
- `--issue-id <nid>`
- `--artifacts-dir DRUPAL_ISSUES/{nid}/artifacts`
- `--review-summary DRUPAL_ISSUES/{nid}/workflow/01-review-summary.json`
- `--depth-signals DRUPAL_ISSUES/{nid}/workflow/01a-depth-signals.json`

Outputs:
- `DRUPAL_ISSUES/{nid}/workflow/01b-solution-depth-pre.md` (human-readable)
- `DRUPAL_ISSUES/{nid}/workflow/01b-solution-depth-pre.json` (machine-readable)
- bd write: `bd update <bd-id> --design "..."`
- Text summary returned to the controller

Markdown format:

```markdown
# Solution Depth Analysis (Pre-Fix) — Issue #<nid>

## Context
- Category: <A-J>
- Module: <name> <version>
- Resonance bucket: <NONE | RELATED_TO | SCOPE_EXPANSION_CANDIDATE | DUPLICATE_OF>
- Signals reviewed: <short list>

## Narrow approach
<2-4 sentences: the smallest change that makes the symptom go away>

## Architectural approach
<2-4 sentences: the underlying class of bug, where a centralized or upstream
solution would live, what other code paths share the same root cause, whether
this could be solved one level higher in the abstraction>

## Trade-offs
| Dimension          | Narrow | Architectural |
|--------------------|--------|---------------|
| Lines changed      | est.   | est.          |
| Files touched      | est.   | est.          |
| Risk of regression | L/M/H  | L/M/H         |
| Solves latent bugs | no/yes | yes           |
| Reviewer surface   | small  | larger        |
| BC concerns        | none   | note          |

## Decision
<narrow | architectural | hybrid>

## must_run_post_fix: <true|false>

## Rationale
<3-6 sentences — why this decision given the signals>

## Deferred follow-up (if narrow chosen and architectural alternative is real)
bd issue create --title "..." --description "..." \
  --dep "discovered-from:bd-<this>"

## IRON LAW
Propose at least two distinct approaches. The architectural one MUST consider
centralization, upstream fixes, and shared-codepath impact. Do not pre-commit
to either before completing the trade-off table.
```

JSON companion format:

```json
{
  "decision": "narrow|architectural|hybrid",
  "must_run_post_fix": true,
  "signals_fired": ["resonance:SCOPE_EXPANSION_CANDIDATE", "category:E"],
  "narrow_lines_est": 15,
  "narrow_files_est": 1,
  "architectural_lines_est": 80,
  "architectural_files_est": 4,
  "follow_up_bd_title": "Centralize null-check validation across FooService"
}
```

**`.claude/agents/drupal-solution-depth-gate-post.md`** — sonnet model.

Frontmatter:

```yaml
---
name: drupal-solution-depth-gate-post
description: Post-fix solution-depth analysis for /drupal-contribute-fix.
  Runs AFTER phpunit passes but BEFORE the spec/code/verifier agents. Reads
  the actual diff and scores 1-5 for architectural reconsideration. Returns
  approved-as-is | approved-with-recommendation | failed-revert. When the
  gate fails, the controller reverts and re-invokes /drupal-contribute-fix
  with the architectural plan.
tools: Read, Grep, Glob, Bash
model: sonnet
---
```

Inputs:
- `--issue-id <nid>`
- `--patch-dir web/modules/contrib/<module>`
- `--pre-analysis DRUPAL_ISSUES/{nid}/workflow/01b-solution-depth-pre.json`
- `--patch-stats DRUPAL_ISSUES/{nid}/workflow/02a-patch-stats.json`

Outputs:
- `DRUPAL_ISSUES/{nid}/workflow/02b-solution-depth-post.md`
- `DRUPAL_ISSUES/{nid}/workflow/02b-solution-depth-post.json`
- bd write: `bd comment <bd-id> "bd:phase.solution_depth.post ..."`
- Text summary returned to the controller

Markdown format:

```markdown
# Solution Depth Analysis (Post-Fix) — Issue #<nid>

## What we built
<summary of the actual patch — files, lines, approach taken>

## Pre-fix recommendation vs actual
- Pre-fix said: <narrow|architectural|hybrid>
- Actually built: <narrow|architectural|hybrid>
- Delta: <none | "we went narrow despite pre-fix recommending architectural">

## Smell check
- [ ] Mocks/stubs/fakes in production code? <list each with justification or reject>
- [ ] Validation duplicated across sites? <list>
- [ ] Early-return for null without root cause? <list>
- [ ] Hard-coded values that should be config? <list>
- [ ] Test only covers specific repro, not the bug class? <yes/no + which inputs missed>
- [ ] Shortcut pattern matched hack-patterns.md? <list>

## Architectural reconsideration
Given what we now know after writing the fix, would architectural have been
better? Score 1-5 (5 = definitely should have gone architectural).

Score: <N>
Reasoning: <3-5 sentences>

## Decision
<approved-as-is | approved-with-recommendation | failed-revert>

Mapping:
- Score 1:    approved-as-is    (gate passes clean)
- Score 2-3:  approved-with-recommendation (gate passes; note added to draft comment)
- Score >= 4: failed-revert     (gate FAILS; controller reverts and re-invokes)
```

JSON companion format:

```json
{
  "decision": "approved-as-is|approved-with-recommendation|failed-revert",
  "score": 3,
  "smells_found": ["mock_in_production_code", "hard_coded_admin_role"],
  "pre_fix_delta": "went_narrow_despite_architectural_recommendation",
  "recommendation_for_comment": "Consider centralizing null-check..."
}
```

### 2. Trigger logic module

`.claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py` — ~80
lines, stateless, unit-testable.

```python
"""Post-fix gate trigger logic for drupal-contribute-fix.

Three trigger conditions:
  1. Pre-fix agent set must_run_post_fix = true
  2. Objective lines_changed > 50
  3. Objective files_touched > 3

Keyword matching, category lookups, resonance bucket checks, and
rationalization pattern detection all live inside the pre-fix agent (opus),
which reads raw context and reasons about it. This module only handles the
objective patch-level facts and the handoff from the pre-fix decision.
"""

import json
import subprocess
from pathlib import Path


def compute_patch_stats(module_path: Path) -> dict:
    """git diff --numstat against the module's current state.

    Returns:
        {
            "lines_added": int,
            "lines_removed": int,
            "lines_changed": int,
            "files_touched": int,
            "file_list": list[str],
        }
    """
    result = subprocess.run(
        ["git", "diff", "--numstat"],
        cwd=module_path,
        capture_output=True,
        text=True,
        check=True,
    )
    added = removed = files = 0
    file_list = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        a, r, path = line.split("\t", 2)
        # Binary files show "-\t-\t"; treat as 0 changes, still counts as a file
        added += 0 if a == "-" else int(a)
        removed += 0 if r == "-" else int(r)
        files += 1
        file_list.append(path)
    return {
        "lines_added": added,
        "lines_removed": removed,
        "lines_changed": added + removed,
        "files_touched": files,
        "file_list": file_list,
    }


def should_run_post_fix(pre_fix_json: dict, patch_stats: dict) -> tuple[str | None, bool]:
    """Decide whether to run the post-fix gate.

    Returns (trigger_reason, should_run). trigger_reason is None when
    should_run is False.
    """
    if pre_fix_json.get("must_run_post_fix"):
        return ("pre_fix_agent_demanded", True)
    if patch_stats["lines_changed"] > 50:
        return (f"lines_changed_gt_50 ({patch_stats['lines_changed']})", True)
    if patch_stats["files_touched"] > 3:
        return (f"files_touched_gt_3 ({patch_stats['files_touched']})", True)
    return (None, False)


def write_trigger_decision(issue_id: str, workflow_dir: Path,
                           trigger_reason: str | None, should_run: bool) -> None:
    """Write workflow/02a-trigger-decision.json so the decision is auditable."""
    out = {
        "issue_id": issue_id,
        "post_fix_gate": {
            "will_run": should_run,
            "trigger_reason": trigger_reason or "no_triggers_fired",
        },
    }
    (workflow_dir / "02a-trigger-decision.json").write_text(json.dumps(out, indent=2))
```

### 3. Failure path (recovery brief + revert + re-run)

When the post-fix gate returns `decision: failed-revert`:

**Step A** — write `DRUPAL_ISSUES/{nid}/workflow/02c-recovery-brief.md`:

```markdown
# Recovery Brief — Issue #<nid>

## What the narrow attempt tried
<2-4 sentences from 01b-solution-depth-pre.md narrow approach block>

## Why it was rejected
<3-5 sentences from 02b-solution-depth-post.md: smell findings + score reasoning>

## Architectural plan (for the re-run)
<The architectural approach block from 01b-solution-depth-pre.md, plus any
refinements the post-fix agent added in 02b-solution-depth-post.md>

## Reference: narrow attempt diffs
See `.drupal-contribute-fix/attempt-1-narrow/` for the full diff, test files,
and report of the rejected attempt. Do not blindly copy — the architectural
rewrite may need different tests, different file boundaries, and different
module touchpoints.

## Constraints that carry forward
- Module: <name> <version>
- DDEV project: d<nid>
- Preflight verdict (still valid): <from the narrow run>
- Reproduction steps: <from issue, still valid>

## Constraints that are RESET
- Test suite: start fresh or adapt from attempt-1
- PHPCS / CI parity evidence: must be re-run
- Spec / code / verifier reports: must be re-dispatched
```

**Step B** — preserve attempt-1 by copy (not move):

```bash
ATTEMPT_DIR=".drupal-contribute-fix/attempt-1-narrow"
mkdir -p "$ATTEMPT_DIR"
cp -r .drupal-contribute-fix/<nid>-<slug>/* "$ATTEMPT_DIR/"
cd web/modules/contrib/<module>
git diff > "$WORKBENCH_ROOT/$ATTEMPT_DIR/source-changes.patch"
```

**Step C** — destructive revert, scoped to production source directories:

```bash
cd web/modules/contrib/<module>
git checkout -- .
git clean -fd -- tests/ src/ config/
```

Narrowed `git clean` avoids nuking `.vscode/`, scratch files in the module
root, or untracked docs.

**Step D** — re-invoke:

```
/drupal-contribute-fix --approach architectural --recovery-brief DRUPAL_ISSUES/<nid>/workflow/02c-recovery-brief.md
```

Inside the re-invocation:
- Preflight is skipped — already run, still valid via `UPSTREAM_CANDIDATES.json`.
- Pre-fix gate is skipped — the recovery brief IS the pre-fix analysis;
  running opus again risks flip-flopping between attempts.
- TDD loop resumes with the recovery brief as the plan.
- Post-fix gate runs again at the end, operating against the architectural
  attempt.

**Circuit breaker: maximum 2 attempts per issue.** If the architectural
attempt also fails the post-fix gate, the controller stops and escalates:

```
SOLUTION DEPTH ESCALATION — Issue #<nid>

Attempt 1 (narrow): failed post-fix gate, score <N>
  → workflow/02b-solution-depth-post.md
  → .drupal-contribute-fix/attempt-1-narrow/

Attempt 2 (architectural): failed post-fix gate, score <N>
  → workflow/02b-solution-depth-post-attempt-2.md
  → current working tree

Neither approach satisfied the gate. Options:
  1. Review both analyses and tell me which to keep
  2. Propose a third approach manually
  3. Abort — close DDEV, file bd follow-up

What would you like to do?
```

bd writes during failure path:
- `bd update <bd-id> --design "<content of 01b + 02c combined>"`
- `bd comment <bd-id> "bd:phase.solution_depth.post.failed_revert ..."`
- `bd comment <bd-id> "bd:phase.solution_depth.attempt_2_start ..."`

bd writes are best-effort. If bd fails (config issue, dolt server down),
log the failure and continue. The workflow files are the source of truth.

## Data flow

### `/drupal-issue-review` → gate (via workflow/)

`/drupal-issue-review` emits two files at the end of the review phase:

**`workflow/01-review-summary.json`** — structured review outcome:

```json
{
  "issue_id": 3581952,
  "category": "E",
  "module": "ai",
  "module_version": "1.2.x-dev",
  "reproduction_confirmed": true,
  "existing_mr": {"iid": 1288, "source_branch": "...", "apply_clean": false},
  "static_review_findings": [
    {"file": "src/Plugin/AiProvider.php", "concern": "..."},
    ...
  ]
}
```

**`workflow/01a-depth-signals.json`** — raw context for the pre-fix agent,
**not parsed mechanically**:

```json
{
  "category": "E",
  "resonance_bucket": "SCOPE_EXPANSION_CANDIDATE",
  "resonance_report_path": "DRUPAL_ISSUES/{nid}/workflow/00-resonance.md",
  "reviewer_narrative": "<full text of the static review findings>",
  "recent_maintainer_comments": [
    {"author": "marcus", "date": "2026-04-08", "body": "<full comment text>"}
  ],
  "proposed_approach_sketch": "<the review's plan for the fix, if any>"
}
```

Note what is NOT in `01a-depth-signals.json`: `criticism_keywords_hit`,
`rationalization_matches`. These are reasoning tasks for the opus agent,
not regex matches from the controller.

### Gate → `/drupal-contribute-fix` (via workflow/ + JSON)

- `01b-solution-depth-pre.json` tells the controller `decision` and
  `must_run_post_fix`.
- `02b-solution-depth-post.json` tells the controller `decision` and
  `score`. A `decision: failed-revert` triggers the failure path.

### Gate → bd

- Pre-fix writes design via `bd update <bd-id> --design "..."`.
- Post-fix appends a comment via `bd comment <bd-id> "bd:phase.solution_depth.post ..."`.

Notation prefixes follow ticket 028's phase schema. New prefixes added in
this ticket:

- `bd:phase.solution_depth.pre`
- `bd:phase.solution_depth.post`
- `bd:phase.solution_depth.post.failed_revert`
- `bd:phase.solution_depth.attempt_2_start`

## Files created

1. `.claude/agents/drupal-solution-depth-gate-pre.md` — opus
2. `.claude/agents/drupal-solution-depth-gate-post.md` — sonnet
3. `.claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py`

## Files modified

1. `.claude/skills/drupal-contribute-fix/SKILL.md` — adds Step 0.5 (pre-fix
   dispatch), Step 2.5 (post-fix dispatch + failure path), new
   Rationalization row ("I already know the architectural option won't
   work"), version bump to 1.8.0.
2. `.claude/skills/drupal-issue-review/SKILL.md` — emits
   `workflow/01-review-summary.json` and `workflow/01a-depth-signals.json`
   at the end of review phase.
3. `.claude/skills/drupal-issue/SKILL.md` — notes that post-fix failure
   recovery is internal to `/drupal-contribute-fix` and does not change the
   A-J classification table.
4. `CLAUDE.md` — adds a "Solution Depth Gate" subsection under workflow
   patterns, covering the 3-trigger rule and the recovery brief format.
5. `docs/bd-schema.md` — adds the 4 new `bd:phase.solution_depth.*`
   notation prefixes.
6. `docs/tickets/030-solution-depth-gate.md` — Resolution note.
7. `docs/tickets/00-INDEX.md` — flip 030 to COMPLETED.

## Scope addition: haiku → sonnet migration

Per a standing user preference (saved to memory 2026-04-10: "user doesn't
trust haiku enough"), all existing `model: haiku` agents are migrated to
`sonnet` as part of this ticket's implementation, since we're already
touching agent definitions:

8. `.claude/agents/drupal-issue-fetcher.md` — haiku → sonnet
9. `.claude/agents/drupal-ddev-setup.md` — haiku → sonnet
10. `.claude/agents/drupal-resonance-checker.md` — haiku → sonnet

These were spec'd as haiku during tickets 028 and 029 when the preference
hadn't been surfaced yet. No behavioral change expected beyond "stronger
reasoning on the same structured outputs."

## Acceptance criteria

Mapping to the ticket's original 5 criteria:

| # | Requirement | Verification |
|---|---|---|
| 1 | Replay issue 3581952: pre-fix gate produces `01b-solution-depth-pre.md` whose architectural option includes "solve without the MR using docs marcus mentioned about" | Run `/drupal-contribute-fix --issue 3581952` up to pre-fix gate, grep architectural approach block for `without.*MR\|marcus\|docs`. Any of those phrases appearing = pass. |
| 2 | Replay issue 3583760: pre-fix gate's architectural option includes "centralize null-check validation" | Same procedure; grep for `centraliz.*null\|null.*centraliz\|scope.*validation` in the architectural block. |
| 3 | Synthetic test issue with a hacky mock-based fix triggers post-fix gate to fail and return "approved-with-recommendation" or "failed-revert" | Craft a scratch module fix in a temp DDEV adding a `MockExternalApiClient` that production code routes through. Run `/drupal-contribute-fix`. Post-fix gate must return score >= 2 AND decision != "approved-as-is". |
| 4 | Low-complexity issues (<50 lines, single file, category F) only run pre-fix; no `02b-*.md` created | Pick a small recent fix or craft a tiny single-file fix. Confirm `workflow/02b-solution-depth-post.md` does NOT exist, AND `workflow/02a-trigger-decision.json` logs `no_triggers_fired`. |
| 5 | Post-fix score >= 4 causes workflow to revert and re-run | Using the synthetic test case from #3, tune smells so score hits 4. Verify two `/drupal-contribute-fix` invocations in session JSONL, `.drupal-contribute-fix/attempt-1-narrow/` exists with rejected diff, `workflow/02c-recovery-brief.md` present. |

Additional smoke test beyond the ticket's 5 criteria:

**Circuit breaker test.** Synthetic case where both attempts fail the
post-fix gate. Verify controller stops after attempt 2, presents the
escalation prompt, does NOT start attempt 3.

## Design decisions locked in

1. **Pre-fix gate owned by `/drupal-contribute-fix`, fed by
   `/drupal-issue-review` via `workflow/` files.** Unskippable regardless
   of entry point; matches the Step 0.5 resonance pattern from ticket 029.

2. **Post-fix triggers are agent-driven + minimal objective.** One opus
   judgment (`must_run_post_fix`) plus two hard patch-size facts. No
   keyword regex, no category lookup tables, no rationalization pattern
   matching. These moved into the opus agent's reasoning context.

3. **Two agent files instead of one.** Claude Code agent frontmatter has a
   single `model:` value per file; we need opus for pre-fix and sonnet for
   post-fix, so two files is the simplest path.

4. **Failure path uses a recovery brief, not stash.** `git stash` carries
   test files we may not want anyway, and the brief + preserved attempt-1
   diffs give the architectural rerun a cleaner starting point.

5. **Circuit breaker at 2 attempts, not N.** One revert matches the user's
   "rare case" framing; two attempts bounding is the safety net against
   infinite loops on over-sensitive gates.

6. **bd writes are best-effort.** Workflow files are the source of truth.
   bd is the queryability layer (ticket 034 turns it into long-term memory).

7. **Preflight is skipped on architectural rerun.** Already written to
   `UPSTREAM_CANDIDATES.json` by the narrow attempt; re-running wastes
   time.

8. **Pre-fix gate is skipped on architectural rerun.** The recovery brief
   IS the pre-fix analysis; running opus again risks flip-flopping between
   attempts.

9. **Haiku → sonnet migration is included in this ticket's scope** because
   it touches agent definitions anyway. Three files: fetcher, ddev-setup,
   resonance-checker.

## Out of scope (future work)

- **Hook-based bd syncing.** A SessionEnd or phase-end hook that syncs
  `workflow/` files to bd would remove the need for gate-level bd writes.
  Deferred to ticket 034.
- **Per-invocation model override for agent frontmatter.** Would collapse
  the two gate files into one. Upstream Claude Code feature request, not
  our ticket.
- **Rationalization-pattern auto-extractor.** A script that scans all
  SKILL.md files and compiles a rationalization-pattern corpus. Rejected in
  favor of agent-driven reasoning.

## Open risks

- **Pre-fix gate false positives** — opus proposing an architectural
  alternative for every issue, even trivial typo fixes. Mitigation: the
  narrow approach is always the first proposal in the trade-off table, and
  the agent is explicitly told "decision may be narrow when the issue is
  genuinely single-site." If this becomes a problem, a `--mode
  minimal-for-triviality` short-circuit can be added.
- **Post-fix gate score inflation from sonnet** — sonnet may be too
  generous or too harsh on the 1-5 scale. Mitigation: the scorer is
  anchored on a concrete smell checklist rather than a vibes check, and
  score 2-3 is a soft pass (note for comment) rather than a hard revert.
- **Circuit breaker masks real over-sensitivity.** If the gate fails
  attempt 2 often, we'd be eating two full fix-cycles to discover it. The
  escalation prompt at least puts the decision in front of the user rather
  than looping silently.
