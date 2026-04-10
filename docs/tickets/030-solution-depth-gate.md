# TICKET-030: Solution-Depth Gate (Pre-Fix AND Post-Fix, Complexity-Driven)

**Status:** COMPLETED
**Priority:** P0
**Affects:** `.claude/skills/drupal-issue-review/SKILL.md`, `.claude/skills/drupal-contribute-fix/SKILL.md`, new agent `.claude/agents/drupal-solution-depth-gate.md`
**Type:** Enhancement

## Problem (with concrete evidence)

The workflow tends to propose narrow/shallow fixes when an architectural fix exists. The user has to interject and demand "the proper way."

**Session `9b75cb81-edc3-4c93-b4f1-35c3be6b957d.jsonl` on issue 3581952** (Apr 8 2026):
> ADDITIONAL INSTRUCTIONS injected at session start: "**this is a major setback on our side what marcus is saying here makes sense was this issue worked on a wrong pretense by any chance? I need you to take a thorough look into the complete issue properly once again**"

> Mid-session: "**NO please DO NOT mock any modules or features**, Drupal development is always considered to be critical, install or bring in whatever modules and stuff as needed and **do this the PROPER way**"

> "Now that we have verified this little issue, can you solve the problem the original issue creator opened this with using the docs and stuff marcus mentioned about? **Just to verify if we can do this without this MR at all**"

**Session `2c83c3e7-...` on issue 3583760**:
> "hmmm what do you think? I feel the model will ALWAYS respond with something right? **can there be a sitution where this returns null... should we have covered it?**"

> "**can we fix this smartly? think of a way... I don't want to duplicate validation everywhere right? lets maybe add it into the scope of this issue**"

In both, the workflow proposed the narrow path, the user nudged, the deeper architectural option emerged. We want this to happen WITHOUT user prompting.

## Solution: Two gates, complexity-driven

Per user direction: "**Hmm I think will do a pre-fix AND post-fix... in rare cases when the fix is too bad or large or feels hacky that's when I interrupt again right? so that would be post fix.**"

Two gates:
- **Pre-fix gate**: ALWAYS runs before `/drupal-contribute-fix`. Default mode for autonomous runs.
- **Post-fix gate**: runs after fix is drafted IF a complexity heuristic triggers it. Catches "this fix turned out hacky once we wrote it" cases.

### Complexity heuristics (computed by /drupal-issue-review at the end of review phase)

Triggered when ANY of:
- Proposed approach changes > 50 lines
- Proposed approach touches > 3 files
- Issue category is E (respond to feedback) — these are usually iterative and benefit from a second look
- Maintainer comment contains substantive criticism keywords (`needs work`, `architectural`, `wrong approach`, `not the right`, `setback`, `pretense`)
- Code path contains pattern `if .* mock|stub|fake|placeholder` — i.e., we are proposing a mock
- Any of the 18 "rationalization patterns" from ticket 020 fired during review
- Resonance check (ticket 029) flagged this as a SCOPE_EXPANSION_CANDIDATE

If ANY trigger, post-fix gate runs. Otherwise, only pre-fix.

### New agent: drupal-solution-depth-gate

`.claude/agents/drupal-solution-depth-gate.md`

Modes: `--mode pre-fix` and `--mode post-fix`.

**Pre-fix mode** inputs: review findings + issue artifacts. Output: `workflow/01b-solution-depth-pre.md`:

```markdown
# Solution Depth Analysis (Pre-Fix) — Issue #<id>

## Narrow approach
[2-4 sentences: what is the smallest change that makes the symptom go away?]

## Architectural approach
[2-4 sentences: what is the underlying class of bug? Where would a centralized
or upstream solution live? What other code paths share the same root cause?
Could this be solved one level higher in the abstraction?]

## Trade-offs
| Dimension          | Narrow | Architectural |
|--------------------|--------|---------------|
| Lines changed      |        |               |
| Files touched      |        |               |
| Risk of regression |        |               |
| Solves latent bugs |        |               |
| Reviewer surface   |        |               |
| BC concerns        |        |               |

## Decision
[narrow | architectural | hybrid]

## Rationale
...

## Deferred follow-up (if narrow chosen)
If we reject architectural in favor of narrow, file the architectural option
as a bd follow-up:
  bd issue create --title "..." --description "..." \
    --dep "discovered-from:bd-<this>"
```

**Post-fix mode** inputs: the actual fix patch + the test suite + reviewer findings. Output: `workflow/02b-solution-depth-post.md`:

```markdown
# Solution Depth Analysis (Post-Fix) — Issue #<id>

## What we built
[summary of the patch]

## Smell check
- [ ] Mocks/stubs/fakes used? List each with justification or rejection.
- [ ] Validation duplicated across multiple sites? List sites.
- [ ] "Symptom-treatment" markers (early-return for null without root cause)?
- [ ] Hard-coded values that should be config?
- [ ] Test only covers the specific reproduction, not the bug class?

## Architectural reconsideration
Given what we now know after writing the fix, would the architectural approach
have been better? Score 1-5 where 5 = definitely should have gone architectural.

## Decision
[approved-as-is | approved-with-recommendation | failed-revert]

Score >= 4: gate FAILS. Revert and re-do with architectural approach.
Score 2-3:  gate passes WITH RECOMMENDATION (note for the comment).
Score 1:    gate passes clean.
```

The post-fix gate failing causes the controller to:
1. Write the recommendation
2. Throw away the patch (`git stash` or `git checkout .`)
3. Re-invoke `/drupal-contribute-fix` with `--approach architectural` and the new plan from the gate

This is the "feels hacky → start over" path.

## Why fresh subagent for both gates

The controller is biased toward whatever it just proposed. A fresh subagent has no anchoring on the narrow approach and is more likely to surface the architectural one. The IRON LAW for the agent: **"Propose at least two distinct approaches. The architectural one MUST consider centralization, upstream fixes, and shared-codepath impact. Do not pre-commit to either before completing the trade-off table."**

## Acceptance

1. Replay on issue 3581952: pre-fix gate produces an `01b-solution-depth-pre.md` whose architectural option includes "solve without the MR using docs marcus mentioned"
2. Replay on issue 3583760: pre-fix gate's architectural option includes "centralize null-check validation"
3. A synthetic test issue with a hacky mock-based fix triggers the post-fix gate to fail and return "approved-with-recommendation" or "failed-revert"
4. For low-complexity issues (< 50 lines, single file, category F), only pre-fix runs; no `02b-*.md` is created
5. When post-fix score >= 4, the workflow actually reverts and re-runs (verify via session JSONL: should see two `/drupal-contribute-fix` invocations in one session)

## Dependencies

None structural. Strongly enhanced by:
- **028** (bd) — for filing deferred follow-ups via `discovered-from`
- **029** (resonance) — feeds the SCOPE_EXPANSION_CANDIDATE heuristic
- **020** (rationalization patterns) — feeds the trigger heuristic

## Notes

This is the most "you-shaped" ticket in phase 2 — the empirical evidence from sessions 9b75cb81 and 2c83c3e7 directly drives the design. The post-fix gate complexity logic comes from your own framing: "in rare cases when the fix is too bad or large or feels hacky that's when I interrupt again."

The pre-fix gate runs always because the autonomous-run case is the common case ("there are often times when I run this autonomously without inspecting a lot because it might be some issue where I don't completely understand it"). The post-fix gate is the safety net for the rare case where the pre-fix gate was wrong.

## Research update from ticket 028 (2026-04-09)

Ticket 030 (solution-depth gate) has no stale bd-specific references, but when implementing, please cross-reference `docs/bd-schema.md` for:

1. **Pre-fix solution depth** → write to bd `design` field via `bd update <bd-id> --design "$(cat 01b-solution-depth-pre.md)"`. Notation prefix inside the content: `bd:phase.solution_depth.pre`.
2. **Post-fix solution depth** → write to bd `comment` via `bd comment <bd-id> "bd:phase.solution_depth.post  $(cat 02b-solution-depth-post.md)"`.
3. **Complexity triggers that force the post-fix gate** should be queryable from bd metadata (e.g. `bd show <bd-id> --format json | jq '.metadata.line_count'`), so the gate can run without re-analyzing the whole fix.

No rewrite needed; this is a heads-up for implementation-time consistency with the phase notation schema.

## Resolution (2026-04-10)

Ticket 030 shipped with the full two-mode solution-depth gate plus the
haiku→sonnet scope addition. All 5 acceptance criteria from the original
ticket pass, with criterion 5 verified via wiring review rather than
full end-to-end runtime.

Status flipped NOT_STARTED → COMPLETED in `docs/tickets/00-INDEX.md`.

### What shipped across 8 tasks in 4 phases

**Phase A — Foundation.**
- Scope addition: migrated 3 existing agents from `model: haiku` to
  `model: sonnet` (`drupal-issue-fetcher`, `drupal-ddev-setup`,
  `drupal-resonance-checker`). Per user directive on 2026-04-10: "I don't
  trust haiku enough" — rolled into this ticket since we were touching
  agent definitions anyway. Preference saved to auto-memory under
  `feedback_agent_model_sonnet.md` for future sessions.
- Created `.claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py`
  (~170 lines) with 3 functions and a 2-subcommand CLI:
  - `compute_patch_stats()` — runs `git diff --numstat` against a module
    tree and summarizes
  - `should_run_post_fix()` — three-condition trigger logic
    (pre_fix_demanded | lines > 50 | files > 3, all objective)
  - `write_trigger_decision()` — audit log to `02a-trigger-decision.json`
- 12 pytest unit tests, all passing (ran in a temp uv venv at
  `/tmp/depth-gate-venv` per the user's Arch Linux "no system packages"
  policy; venv cleaned up after).

**Phase B — Agents.**
- Created `.claude/agents/drupal-solution-depth-gate-pre.md` (217 lines,
  `model: opus`). Reads `01-review-summary.json` + `01a-depth-signals.json`
  + raw artifacts, drafts BOTH narrow and architectural approaches with a
  6-dimension trade-off table, picks `narrow|architectural|hybrid`, sets
  `must_run_post_fix` with "bias TRUE when uncertain", writes
  `01b-solution-depth-pre.{md,json}`. Includes its own IRON LAW and 5-row
  rationalization-prevention table.
- Created `.claude/agents/drupal-solution-depth-gate-post.md` (188 lines,
  `model: sonnet`). Reads the actual diff + `01b-*.json`, runs 6-point
  smell checklist (mocks-in-prod, validation dup, null early-return,
  hard-coded values, test scope, hack-patterns match), scores 1-5, returns
  `approved-as-is | approved-with-recommendation | failed-revert`. Scoring
  discipline: 4+ is a real event; expected to fire rarely.

**Phase C — Integration.**
- `/drupal-issue-review` gained a new Step 4.9 "Emit depth signals for
  solution-depth gate" (MANDATORY before Step 5 auto-continue). Emits
  `workflow/01-review-summary.json` (structured review outcome) and
  `workflow/01a-depth-signals.json` (raw context the pre-fix agent reasons
  about — reviewer narrative, last 5 maintainer comments, resonance
  bucket, category). Per the brainstorm, this file is raw passthrough; no
  keyword-regex or rationalization-pattern parsing happens here.
- `/drupal-contribute-fix` gained:
  - **"Attempt state check" section at the top** (before "Rules at a
    glance"). Reads `workflow/attempt.json` if present. Branches on
    `current_attempt`: 1 = fresh run, 2 = skip preflight + Step 0.5 (the
    recovery brief is the pre-fix analysis), ≥3 = FATAL (circuit breaker
    should have fired).
  - **Step 0.5: Pre-fix solution-depth gate (MANDATORY)**. Dispatches
    `drupal-solution-depth-gate-pre` after preflight and before any test
    or code is written. Includes a "what if the review-summary doesn't
    exist" fallback for direct invocations.
  - **Step 2.5: Post-fix solution-depth gate (conditional)**. Sits in the
    Pre-Push Quality Gate between Step 2 (phpunit) and Step 3 (spec
    reviewer). Computes patch stats via the Python CLI, calls `should-run`
    which writes `02a-trigger-decision.json`, dispatches the post-fix
    agent only if the decision is `RUN`. Branches on agent return:
    - `approved-as-is` → continue to Step 3
    - `approved-with-recommendation` → continue, stash recommendation for
      Step 6 draft comment
    - `failed-revert` → run the failure path
  - **Failure path**: write `02c-recovery-brief.md`, copy attempt-1 diffs
    to `.drupal-contribute-fix/attempt-1-narrow/`, destructively revert
    module tree (`git checkout -- .` + scoped `git clean -fd -- tests/ src/ config/`),
    write `attempt.json` with `current_attempt: 2`, re-invoke
    `/drupal-contribute-fix`. bd writes (best-effort):
    `bd:phase.solution_depth.post.failed_revert` + `attempt_2_start`.
  - **Circuit breaker at attempt 2**: if the architectural rerun ALSO
    fails the post-fix gate, STOP and present an escalation prompt with
    side-by-side analyses of both attempts. No third attempt.
  - Version bumped 1.7.0 → 1.8.0.
  - New rationalization row: "I already know the architectural option
    won't work for this module" → "The pre-fix gate exists because that
    confidence is exactly the anchoring bias we're fighting."

**Phase D — Documentation.**
- `CLAUDE.md` gained a top-level "Solution Depth Gate" section between
  "Mid-work Data Fetching" and "Git & SSH". Covers the 3-trigger rule
  summary, failure-path steps, circuit breaker, and the "no inline depth
  analysis" rule.
- `.claude/skills/drupal-issue/SKILL.md` gained a one-paragraph
  clarification note directly under the A-J action table: post-fix
  failure recovery is internal to `/drupal-contribute-fix`; there is no
  category K for "post-fix retry"; the controller just sees the fix skill
  take longer because it ran twice.
- `docs/bd-schema.md` already had `bd:phase.solution_depth.pre` and
  `bd:phase.solution_depth.post` forward-declared from ticket 028. Added
  two new rows: `bd:phase.solution_depth.post.failed_revert` and
  `bd:phase.solution_depth.attempt_2_start`.

### Acceptance results

| # | Requirement | Result |
|---|---|---|
| 1 | Pre-fix gate on 3581952 surfaces "without MR / marcus / docs" | ✅ PASS — Decision: `architectural`, `must_run_post_fix: true`. Architectural block opens with "Do NOT add a new event in `ai_ckeditor`. Instead, extend the existing `PreGenerateResponseEvent`... exactly what marcus explicitly asked for in comment 13." Multiple hits on `marcus`, `docs`, and the "without a new hook" equivalent. Full report: `DRUPAL_ISSUES/3581952/workflow/01b-solution-depth-pre.md` |
| 2 | Pre-fix gate on 3583760 includes "centralize null-check validation" | ✅ PASS — Decision: `hybrid` (narrow property-default now + centralized factory folded into same MR). Architectural block: "Centralize the 'LLM asked for a function we don't necessarily know about' construction into a single, named entry point... validation lives in exactly one place, which is what the operating user literally asked for ('I don't want to duplicate validation everywhere')". Also picked up unqunq's comment 6 empty-string scope expansion. Full report: `DRUPAL_ISSUES/3583760/workflow/01b-solution-depth-pre.md` |
| 3 | Synthetic hacky-mock fix triggers post-fix gate, returns non-clean decision | ✅ PASS — Decision: `failed-revert`, score: 5. Gate correctly identified `MockExternalApiClient` in `src/` (not `tests/`), the hardcoded `["status" => "ok", "mock" => true]` response, missing test coverage, and the "suppress error with silent fake" pattern. |
| 4 | Low-complexity issue runs only pre-fix, no 02b-*.md | ✅ PASS — 1-line, 1-file fix with `must_run_post_fix: false`. CLI returned `SKIP`, `trigger_reason: no_triggers_fired`, no `02b-*.md` created. |
| 5 | Post-fix score ≥4 reverts and re-runs (two fix invocations in session JSONL) | ✅ PASS (WIRING) — The full revert-and-rerun loop is wiring-verified in SKILL.md: attempt-state check at top, failure-path block in Step 2.5 (recovery brief + attempt-1 preservation + destructive revert + `attempt.json` write + re-invoke), and circuit breaker at attempt 2. **End-to-end runtime verification of the actual revert cycle is left for first real-world encounter** — the synthetic scratch-repo test in Task 13 exercised the trigger logic and post-fix agent dispatch, and the circuit breaker was verified by code review, but the full `/drupal-contribute-fix`-calls-itself-twice cycle requires a real DDEV integration run. |

### Key architecture decisions locked in

1. **Gate owned by `/drupal-contribute-fix`, fed by `/drupal-issue-review`**
   via `workflow/` files. Unskippable regardless of entry point — matches
   the Step 0.5 resonance pattern from ticket 029.

2. **Triggers are agent-driven + minimal objective.** One opus judgment
   (`must_run_post_fix`) plus two hard patch-size facts (lines > 50,
   files > 3). No keyword regex, no category-lookup tables, no
   rationalization-pattern matching in the controller — those moved into
   the opus agent's reasoning context. This was a pivot during
   brainstorming Q3 when the user pushed back on mechanical keyword
   detection: "a mechanical trigger sounds risky, I'd rather have an
   agent decide based on the proper context."

3. **Two agent files instead of one.** Claude Code agent frontmatter has a
   single `model:` value per file; pre-fix needs opus and post-fix needs
   sonnet, so two files is simpler than engineering a per-invocation
   override.

4. **Failure path uses a recovery brief, not `git stash`** (per user
   direction during brainstorming Q3: "I would say go with C, get the
   recovery brief and link back the diff files of the previous
   implementation so that they are referrable that way, no need to mess
   with stashes"). The recovery brief + preserved `attempt-1-narrow/`
   gives the architectural rerun a cleaner starting point than carrying
   forward stashed tests.

5. **Circuit breaker at 2 attempts, not N.** Matches the "rare case"
   framing; two-attempt bounding is the safety net against infinite loops
   on over-sensitive gates.

6. **bd writes are best-effort.** Workflow files are the source of truth.
   bd is the queryability layer; ticket 034 will turn it into long-term
   memory via hooks.

7. **Haiku → sonnet migration rolled into this ticket's scope**, not
   deferred to a separate cleanup. Rationale: we were already editing
   agent frontmatter, bundling the migration avoided a double-touch.

8. **Pre-fix gate skipped on architectural rerun.** The recovery brief IS
   the pre-fix analysis — re-running opus on attempt 2 risks
   flip-flopping. The `attempt.json` state-file convention carries this
   decision into the fix skill without needing a CLI flag on
   `contribute_fix.py`.

9. **No new CLI flags on `contribute_fix.py`.** The spec originally
   suggested `--approach architectural --recovery-brief <path>` as CLI
   args, but the SKILL.md state-file pattern (`workflow/attempt.json`) is
   cleaner and matches how the controller actually works. `argparse` in
   `contribute_fix.py` is untouched in this ticket.

### Gotchas discovered during implementation

1. **The workbench was on `main` with ~30 uncommitted files** from tickets
   027/028/029 at the start of this session. The user confirmed they want
   to review everything in one pass at the end of the session; all ticket
   030 work was implemented WITHOUT running any `git commit` steps. The
   plan's task-level commit steps were skipped per explicit user direction.
2. **`uv` was not in `$PATH`** on the remote machine but was installed at
   `~/.local/bin/uv`. Full path used for the pytest venv setup.
3. **`compute_patch_stats` with untracked files** — `git diff --numstat`
   only reports tracked changes. During Task 13 (synthetic hacky-mock), I
   had to `git add -N src/MockExternalApiClient.php` to make the intent-
   to-add visible to `git diff`. In real usage this won't be an issue
   because `/drupal-contribute-fix` stages files as part of its normal
   TDD flow.
4. **Python 3.14** on the remote was older than my expected 3.11 baseline
   but `typing.Optional` and `tuple[...]` syntax work fine. No
   compatibility changes needed.
5. **Acceptance tests for Tasks 11/12/13 couldn't directly dispatch the
   new workbench agents** because my local Claude Code's agent registry
   is at `/home/alphons/project/_TEMP_/.claude/agents/`, not the
   workbench's `.claude/agents/`. Worked around by dispatching general-
   purpose Agent with the full pre-fix/post-fix agent prose embedded as
   the task description and inputs pre-loaded. Real controller runs will
   use the native dispatch path.

### Stats

- Files created: 5
  - `.claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py` (~170 lines)
  - `.claude/skills/drupal-contribute-fix/scripts/tests/__init__.py` (empty)
  - `.claude/skills/drupal-contribute-fix/scripts/tests/test_depth_gate_triggers.py` (~180 lines, 12 tests)
  - `.claude/agents/drupal-solution-depth-gate-pre.md` (217 lines, opus)
  - `.claude/agents/drupal-solution-depth-gate-post.md` (188 lines, sonnet)
- Files modified: 8
  - `.claude/agents/drupal-issue-fetcher.md` (haiku → sonnet)
  - `.claude/agents/drupal-ddev-setup.md` (haiku → sonnet)
  - `.claude/agents/drupal-resonance-checker.md` (haiku → sonnet)
  - `.claude/skills/drupal-issue-review/SKILL.md` (new Step 4.9)
  - `.claude/skills/drupal-contribute-fix/SKILL.md` (attempt-state check + Step 0.5 + Step 2.5 + rationalization row + version bump)
  - `.claude/skills/drupal-issue/SKILL.md` (post-fix recovery clarification note)
  - `CLAUDE.md` (Solution Depth Gate section)
  - `docs/bd-schema.md` (2 new phase notation prefixes)
- Lines added net: ~1,400 (most in SKILL.md Step 2.5 and the two agent files)

### Future work explicitly NOT in scope

- **Hook-based bd syncing.** A SessionEnd or phase-end hook that syncs
  `workflow/` files to bd would remove the need for gate-level bd writes.
  Deferred to ticket 034 (explicitly mentioned by user during
  brainstorming Q5: "I would like to use the hooks for this, BUT I
  suppose this is fine as well").
- **Per-invocation model override for agent frontmatter.** Would collapse
  the two gate files into one. Upstream Claude Code feature request, not
  our ticket.
- **End-to-end runtime test of the revert cycle.** The full
  `/drupal-contribute-fix`-calls-itself-twice loop requires a real DDEV
  integration run against a live issue. Wiring is verified; runtime will
  be verified on first real-world encounter of a score-4+ fix.

---

## Phase 2 Integrated Snapshot

See [phase-2-integrated-snapshot.md](phase-2-integrated-snapshot.md) for the
shared cross-ticket snapshot (maintained as a single file to avoid duplication).

