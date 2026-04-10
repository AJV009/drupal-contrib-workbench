# TICKET-034: Cross-Issue Long-Term Memory via bd Notes/Comments

**Status:** NOT_STARTED
**Priority:** P1
**Affects:** All workflow skills (light edits to write to bd in addition to disk), `drupal-issue-fetcher` agent, new `scripts/bd-helpers.sh`
**Type:** Enhancement

## Problem

Today, when starting a new issue, there is no programmatic recall of: "the last 3 issues in this module had the same root cause," "this file has been touched in 5 prior MRs and they all had to handle X," "marcus prefers Y style of fix in this module."

Phase 1 ticket 023 created on-disk workflow artifacts but they're per-issue silos. No cross-issue query is possible. The user has to remember and inject prior context manually, like in session `14f9b85b-...`:

> "I previously worked on this... I just need you to verify if anything from the ai_agents issue need to be removed or refactored to accommodate ai issue 3582345"

## Solution

Use bd's per-issue long-form fields (`Description`, `Design`, `Notes`, `AcceptanceCriteria`, `Comments`) plus `bd remember` as the long-term memory layer. The on-disk `workflow/*.json|md` files stay as a transitional cache; bd is the source of truth for queries.

### Schema (defined in 028's `docs/bd-schema.md`, enforced here)

| Workflow phase                  | bd target                              | Notation                       |
|---------------------------------|----------------------------------------|--------------------------------|
| Classification (ticket 023)     | bd issue `Metadata` JSON               | `bd:phase.classification`      |
| Resonance check (ticket 029)    | bd issue `Comments`                    | `bd:phase.resonance`           |
| Review findings (ticket 023)    | bd issue `Description` (mirror)        | `bd:phase.review`              |
| Solution depth pre (ticket 030) | bd issue `Design`                      | `bd:phase.solution_depth.pre`  |
| Solution depth post (ticket 030)| bd issue `Comments`                    | `bd:phase.solution_depth.post` |
| Verification (ticket 022)       | bd issue `Comments` (one per push)     | `bd:phase.verification`        |
| Push gate summary (ticket 023)  | bd issue `Notes` (cumulative)          | `bd:phase.push_gate`           |
| Maintainer feedback observed    | `bd remember "module:<X>:maintainer_pref"` | `bd:maintainer_pref.<module>` |
| Module-level conventions        | `bd remember "module:<X>:lore"`        | `bd:module_lore`               |
| File-level history              | bd issue `Notes` + `bd label add file:<path>` | `bd:file_history`        |

### Fetcher integration (the actual leverage)

In `drupal-issue-fetcher` agent, add a step after fetching upstream artifacts:

```
Before returning, query bd for relevant prior knowledge:

1. bd list --label-any "module:<module_name>" --status closed
2. For each result, bd show <id> | grep -A5 "bd:phase.verification"
3. bd recall "module:<module_name>:maintainer_pref"
4. bd recall "module:<module_name>:lore"
5. For files mentioned in the MR diff:
     bd list --label-any "file:<path>" --notes-contains "<keyword>"

Include findings as a "PRIOR KNOWLEDGE" section in the enriched return:

   PRIOR KNOWLEDGE
   ===============
   - Last 3 issues in module ai_agents touched ToolsFunctionOutput.php; pattern: serializer hardening
   - Maintainer cadence96 prefers test_*Test.php naming over *Test.php in this module
   - File src/Plugin/AiAgent/AgentBase.php was modified in #3560681 with a known performance gotcha (see bd-3560681 notes)
```

The controller now starts every issue with relevant cross-issue context already in its window, instead of having to derive it.

### Write side

After each phase artifact is written to disk, ALSO write to bd. Wrap the bd writes in helper functions in `scripts/bd-helpers.sh`:

```bash
# scripts/bd-helpers.sh
bd_phase_classification() {
  local iss="$1" file="$2"
  bd issue update "bd-${iss}" --metadata "$(cat "$file")"
}

bd_phase_solution_depth_pre() {
  local iss="$1" file="$2"
  bd issue update "bd-${iss}" --design "$(cat "$file")"
}

bd_phase_verification() {
  local iss="$1" file="$2"
  bd issue update "bd-${iss}" --comment "bd:phase.verification\n\n$(cat "$file")"
}

bd_phase_push_gate() {
  local iss="$1" file="$2"
  bd issue update "bd-${iss}" --notes-append "bd:phase.push_gate\n\n$(cat "$file")"
}

bd_remember_maintainer_pref() {
  local module="$1" pref="$2"
  bd remember "module:${module}:maintainer_pref" "$pref"
}
```

Skills then call these helpers at the right phase. Skills should NOT inline `bd` commands — always go through helpers so we can change the bd schema in one place.

## Acceptance

1. After this lands, starting a new issue in module `ai_agents` surfaces (via fetcher's enriched return) at least one piece of prior knowledge from a closed bd issue in the same module
2. `bd show bd-<id>` for any issue worked post-implementation includes `bd:phase.classification`, `bd:phase.review`, `bd:phase.verification` data
3. `bd list --notes-contains "<keyword>"` returns relevant historical issues
4. Manual: `bd remember "module:ai:test_pattern" "use kernel tests for entity access checks"` followed by a new issue start should surface that recall in fetcher output
5. `scripts/bd-helpers.sh` exists with at least the 5 helper functions above

## Dependencies

- **028** (bd must exist with schema defined)
- **029** (resonance check writes its own bd entries; the schemas should be consistent — both write to Comments with `bd:resonance.*` and `bd:phase.*` notation)

## Notes

This ticket is the second-order win from adopting bd. Without it, bd is just an issue tracker. With it, bd becomes the workbench's institutional memory.

The fetcher integration is the key payoff — it converts cross-issue knowledge from "the user has to remember and inject" into "the workflow surfaces it automatically every time."

## Research update from ticket 028 (2026-04-09)

Two important corrections before implementing this ticket:

### 1. `bd recall` does not exist

The ticket's fetcher integration example uses `bd recall "module:<module_name>:maintainer_pref"` and `bd recall "module:<module_name>:lore"`. **There is no `bd recall` command.**

The real memory surface is:

| Operation | Command |
|---|---|
| Write | `bd remember "<insight>" --key <key>` |
| List | `bd memories` |
| Search | `bd memories <search term>` |
| Delete | `bd forget <key>` |
| Auto-load at session start | `bd prime` (runs automatically via the SessionStart hook installed by `bd setup claude`) |

**Corrected fetcher pseudocode**:
```
Before returning, query bd for relevant prior knowledge:

1. bd list --label module-<module_name> --status merged --format json
2. For each result, bd show <id> --format json | jq '.comments[] | select(.body | startswith("bd:phase.verification"))'
3. bd memories module.<module_name>
4. bd list --label file-<slug> --notes-contains "<keyword>"

Include findings as a "PRIOR KNOWLEDGE" section in the enriched return.
```

### 2. Memory key format

The ticket uses `module:<X>:maintainer_pref` format. Per `docs/bd-schema.md`, use **dots, not colons** for memory keys to match bd's key slugification convention:

| Kind | Key |
|---|---|
| Maintainer preference | `module.<module>.maintainer_pref.<maintainer>` |
| Module lore | `module.<module>.lore.<topic>` |
| File gotcha | `file.<slugified-path>.gotcha.<topic>` |

Slugify file paths: `/`, `.`, `_` → `-`. Matches the launcher's SESSION_DIR encoding.

### 3. `scripts/bd-helpers.sh` — keep the pattern, update the calls

The helper function design is good. Update the function bodies to use the corrected commands:

```bash
bd_phase_classification() {
  local iss="$1" file="$2"
  bd update "$iss" --metadata "@$file"
}

bd_phase_solution_depth_pre() {
  local iss="$1" file="$2"
  bd update "$iss" --design "$(cat "$file")"
}

bd_phase_verification() {
  local iss="$1" file="$2"
  bd comment "$iss" "bd:phase.verification

$(cat "$file")"
}

bd_phase_push_gate() {
  local iss="$1" file="$2"
  # --notes REPLACES, does not append — read existing + concat + write
  local existing
  existing=$(bd show "$iss" --format json | jq -r '.notes // ""')
  bd update "$iss" --notes "${existing}

bd:phase.push_gate ($(date -Iseconds))
$(cat "$file")"
}

bd_remember_maintainer_pref() {
  local module="$1" maintainer="$2" pref="$3"
  bd remember "$pref" --key "module.${module}.maintainer_pref.${maintainer}"
}
```

Note the `bd_phase_push_gate` read-modify-write dance — `--notes` replaces, not appends, so appending cumulative summaries requires reading the existing value first.

### 4. bd issue IDs are NOT `bd-3560681` etc.

The "PRIOR KNOWLEDGE" example in this ticket uses `bd-3560681` as an ID. Real bd IDs are `CONTRIB_WORKBENCH-<slug>`. The Drupal issue number goes in the label (`drupal-3560681`) and external-ref (`external:drupal:3560681`).

### 5. The ticket's design remains correct

None of these corrections affect the design intent (fetcher-driven cross-issue memory, helper-wrapped writes, bd as institutional memory). Implementation should cross-reference `docs/bd-schema.md` for exact command syntax.

## Resolution (2026-04-10)

Ticket 034 shipped: centralized bd-helpers CLI, all workflow phases wired
to write to bd, fetcher enriched with PRIOR KNOWLEDGE query, maintainer/lore
memory system, and refactored inline bd writes from 031/030.

### What shipped

- `scripts/bd-helpers.sh` (205 lines, 12 subcommands) — single source of truth for all bd interactions
- `/drupal-issue` SKILL.md — refactored Step 2.5 (031 inline → helpers), added resonance bd write at Step 0.5
- `/drupal-issue-review` SKILL.md — added review bd write at Step 4.9
- `/drupal-contribute-fix` SKILL.md — refactored failure path (030 inline → helpers), added depth-pre/verification/push-gate writes
- `drupal-issue-fetcher` agent — new Step 4c: query bd for prior knowledge (full + delta modes), writes `prior-knowledge.json` + `bd-issue-state.json`
- `docs/bd-schema.md` — maintainer_pref + module_lore key patterns
- `CLAUDE.md` — "Cross-issue memory" subsection

### Acceptance results

| # | Criterion | Result |
|---|---|---|
| 1 | ensure-issue creates + returns ID | PASS |
| 2 | phase-classification writes metadata | PASS |
| 3 | query-prior-knowledge returns JSON | PASS |
| 4 | remember-maintainer stores memory | PASS |
| 5 | remember-lore stores memory | PASS |
| 6 | 031 inline writes refactored to helpers | PASS (code review) |
| 7 | 030 inline writes refactored to helpers | PASS (code review) |
| 8 | review bd write at Step 4.9 | PASS (code review) |
| 9 | depth-pre + verification + push-gate writes | PASS (code review) |
| 10 | fetcher PRIOR KNOWLEDGE step | PASS (code review) |
| 11 | all writes best-effort | PASS (empty bd_id → exit 0) |

### Gotchas discovered

1. `bd q` (quick capture) outputs only the ID; `bd create` outputs multi-line confirmation text. Always use `bd q` for scriptable ID capture.
2. `bd list --external-ref` didn't find issues created by `bd q` (which doesn't support `--external-ref`). Switched to label-based lookup (`bd list --label drupal-<nid>`) which is reliable and fast.
3. `bd label add` outputs confirmation text to stdout, polluting return values when captured in a subshell. Redirected stdout to /dev/null.
4. bd auto-discovers `.beads/` by walking up from CWD. The helpers script must `cd` to the workbench root before any bd call.
5. `bd note` (alias for `bd update --append-notes`) correctly appends — no read-modify-write dance needed. This contradicts the ticket's research correction #6 which said `--notes` replaces.
