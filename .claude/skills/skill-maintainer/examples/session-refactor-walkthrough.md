# Session Refactor Walkthrough

A condensed walkthrough of the Phases 1-4 cleanup done on this
workspace's Drupal workflow skills. Open this when you're about to do
a multi-phase cleanup pass and want a template for how to structure it.

## Starting state

- 4 workflow skills at a combined 2206 lines (loaded in every session)
- `drupal-contribute-fix` was 738 lines (47% over the 500-line spec target)
- Multiple rules duplicated across files
- 14 `MANDATORY`/`CRITICAL`/`NON-NEGOTIABLE` markers in one file
- Reference lists without trigger phrases
- No explicit `## Gotchas` sections
- Historical narration embedded in rules ("This gate was added after
  #NNNNNN where X happened and Y wasted time...")

## Approach: phase the work by risk

Instead of one big refactor, split into four phases by risk level.
Validate after each phase. Get user approval before the next.

### Phase 1 — pure cleanup, zero risk

Dedupe across files without changing any rules. Roughly:

1. **Dedupe agent-browser screenshot patterns.** Removed ~55 lines of
   inline agent-browser bash from `drupal-issue-review` and
   `drupal-issue-comment`; replaced with one-line references to the
   `agent-browser` skill. Both files already said "see agent-browser
   for full reference" and then duplicated the content anyway.
2. **Move `drupal-issue-comment` TUI Browser Integration to references.**
   ~55 lines of JSON examples moved out of default load.
3. **Collapse "Humility over showmanship" + "What NOT to do"** into one
   section in `drupal-issue-comment`.
4. **Remove duplicate `package` mode command block** (web/ vs docroot/
   versions that differed by one path string).
5. **Delete `drupal-issue-review` manual ddev config fallback.** The
   agent is a hard dependency; the fallback was defensive bloat.
6. **Extract mode command blocks** from `drupal-contribute-fix` SKILL.md
   to existing `modes/*.md` files that already had the same content.
7. **Move historical justifications** to parenthetical form.
8. **Consolidate `Hands-Free Operation`** to CLAUDE.md, reference in
   each skill.
9. **Consolidate `Progress Tracking`** to CLAUDE.md.
10. **Collapse `Called From` + `Handoffs` tables** to single "Related
    Skills" where they described the same edges.

**Result**: ~295 lines cut. No rules lost. No risk.

### Phase 2 — restructure, medium risk

Consolidate scattered sections and add navigation aids:

1. **Merge duplicate workflow summaries in contribute-fix.** Three
   different overviews of the same 7-step flow. Kept one, deleted the
   others.
2. **Remove drupalorg-cli section from contribute-fix.** Duplicated
   CLAUDE.md content.
3. **Replace ddev/agent-browser command blocks in review skill** with
   agent references.
4. **Consolidate test sections under `## Testing` parent.** Four peer
   sections (Testing & Verification References, Test Planning, TEST
   COVERAGE GATE, Test Validation) became one parent with three
   numbered steps (Plan, TDD, Validate).
5. **Add "Rules at a glance" TL;DR** at the top of contribute-fix —
   a 10-item scannable priority list before the full body.

**Result**: another ~150 lines cut. Navigation significantly improved.

### Phase 3 — judgment calls, higher risk

Now compress things that required design decisions:

1. **Trim dead-weight sections**: `Handoff After Triage` (collapsed to
   one sentence), `NEVER DELETE Contribution Artifacts` (merged into
   one paragraph), `SSH Remote Verification` (moved to Gotchas),
   `Interdiff Generation` (compressed), `After Successful Push` user
   menu (deleted the hardcoded 5-option prompt, the menu is trivially
   constructable), `Agent Prompt Templates` + `Example Output` (merged
   into References list), `Mandatory Gatekeeper Behavior` (kept exit
   code table, dropped the two bold sentences that restated Rules at a glance).
2. **Compress `drupal-issue` categories A-I** from 67 lines of prose
   per category to a compact table. Kept E and G as prose because
   they have escalation logic that doesn't fit in table cells.
3. **Extract `drupal-issue` Examples section** to
   `examples/classification-walkthroughs.md`.
4. **Tighten `Reading related issues`** from 14 lines of generic
   patterns to 5 lines.
5. **Demote shouting markers in contribute-fix** from 14 to 7. Kept
   the 4 IRON LAWs at top and the 1 IRON LAW at Push Gate. Demoted
   redundant `(MANDATORY)` section tags to plain text. Rules unchanged,
   caps-lock volume down.

**Result**: another ~115 lines cut. Line counts now comfortably under
the 500-line spec target for all workflow skills.

### Phase 4 — spec compliance polish

Final pass to align with the agentskills.io best practices:

1. **Tighten `Verify claims against source code`** section from 42 to
   27 lines. Same rules, less narration.
2. **Compact `drupal-issue` Before You Begin Q7-Q10.** Q10 was 50 lines;
   compressed to ~20 while preserving all rules including the
   three-part pre-follow-up search.
3. **Move review-skill static checklist** to
   `references/static-review-checklist.md`. ~45 lines out of default
   load.
4. **Add `## Gotchas` sections to all 4 workflow skills.** This is the
   "highest-value content" per the spec's best-practices page. Deep
   per-skill audit to identify what scattered mentions should
   consolidate. Net: +84 lines of Gotchas content, with ~30 lines of
   duplicate mentions removed from other sections.
5. **Rewrite References lists with "open when X" triggers** per the
   spec's progressive disclosure guidance.
6. **Run validator** (`scripts/validate.py`). All skills pass.

**Result**: Gotchas added. Final line counts:

| File | Start | After P4 | Δ |
|---|---|---|---|
| `drupal-contribute-fix` | 738 | 490 | −248 |
| `drupal-issue` | 535 | 417 | −118 |
| `drupal-issue-review` | 463 | 350 | −113 |
| `drupal-issue-comment` | 337 | 310 | −27 |
| **Total** | **2206** | **1677** | **−529 (−24%)** |

All 4 workflow skills under 500 lines. Every rule preserved. Gotchas
sections added. Validator passes.

## Things that worked

- **Phase planning with estimated line deltas.** Presenting a concrete
  plan with "-55 lines from X, -45 lines from Y" lets the user evaluate
  the trade-off per item. Open-ended cleanup passes produce worse results.
- **Surgical edits, not rewrites.** Using `Edit` with exact `old_string`
  from recent `Read` keeps every change auditable. Whole-file rewrites
  hide regressions.
- **Validate after each phase.** Line-count targets and spec compliance
  are cheap to check. Running the validator after each phase catches
  accidental description length violations or YAML breakage before they
  compound.
- **Preserve uncommitted intentional additions.** Early in the session,
  a separate run added 300 lines of intentional new content (Q10, Step 0
  CI parity, Semantic Intent section). The cleanup had to absorb those
  WITHOUT reverting them. Check `git status` and `git diff` at the start
  of every session.
- **Consolidation > deletion.** The 24% line reduction came almost
  entirely from consolidating duplication (same rule in 3 files → one
  canonical location + references). Very few rules were actually deleted.

## Things that didn't work / lessons learned

- **Initial reluctance to touch IRON LAWs.** It felt risky to demote
  `(MANDATORY)` section tags, but the rules are already enforced by the
  top-of-file IRON LAWs + Rules at a glance. The visual emphasis was
  redundant. After the demotion, the remaining 4 IRON LAWs feel genuinely
  critical again.
- **Trying to tighten too many things at once.** Phase 1 originally
  batched 10 items, and tracking which edits were in-progress got messy.
  Splitting into "P1a complete → validate → P1b" would have been cleaner.
- **Line-count anxiety.** Phase 4 added Gotchas sections which pushed
  `drupal-contribute-fix` from 462 back up to 505. Briefly exceeding the
  spec limit was stressful but unnecessary — the Gotchas content was
  high-value per the spec's own best practices. The right response was
  to tighten the References section (P4.6) to reclaim 15 lines, not to
  cut the Gotchas.

## Template for future cleanup passes

When a skill drifts back to >500 lines or shows the bloat warning signs
(see `bloat-patterns.md`):

1. Audit with `scripts/validate.py`. Identify which files are over.
2. Read each target skill end to end. Check `git status` for
   uncommitted intentional changes.
3. Identify bloat by type using `bloat-patterns.md` taxonomy.
4. Group into phases (dedup → restructure → compress → spec polish).
5. Present the full plan to the user with line deltas per item.
6. Execute phase by phase with surgical edits.
7. Validate after each phase.
8. Report combined deltas at the end.
9. Do NOT commit. Let the user drive the commit decision.

Total time for the Phase 1-4 session on this workspace: roughly one
focused session. The biggest wins were Phase 1 (dedup) and Phase 2
(structural consolidation).
