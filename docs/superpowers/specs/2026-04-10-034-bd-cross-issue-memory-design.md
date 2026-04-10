# Ticket 034 — Cross-Issue Long-Term Memory via bd

**Status:** SPEC (not yet implemented)
**Priority:** P1
**Type:** Enhancement
**Depends on:** 028 (bd installed), 029 (resonance), 030 (depth gate), 031 (classification bd write), 039 (hooks bd writes)

## Goal

Turn bd from a queryable issue tracker into the workbench's institutional
memory by: (1) wiring all remaining workflow phases to write to bd via
centralized helpers, (2) enriching the fetcher agent with a PRIOR
KNOWLEDGE query that surfaces cross-issue intelligence from bd at the
start of every new issue, and (3) adding a maintainer-preference and
module-lore memory system.

## Architecture

### Infrastructure: `scripts/bd-helpers.sh` (subcommand CLI)

Standalone bash script at the workbench root. Called as
`scripts/bd-helpers.sh <subcommand> <args>`. Each subcommand wraps one
bd write or query pattern. All writes are best-effort (failure logged to
stderr, never blocks the caller). The script is the single source of
truth for bd schema interactions — skills MUST NOT inline `bd` commands.

```
scripts/bd-helpers.sh <subcommand> [args...]
```

Subcommands:

| Subcommand | bd operation | Caller |
|---|---|---|
| `ensure-issue <nid> <title>` | `bd create` if not exists; prints bd ID to stdout | `/drupal-issue` Step 2.5 |
| `phase-classification <bd-id> <file>` | `bd update <bd-id> --metadata "$(cat <file>)"` | `/drupal-issue` Step 2.5 |
| `phase-resonance <bd-id> <file>` | `bd comment <bd-id> --file <file>` (prefixed `bd:phase.resonance`) | `/drupal-issue` Step 0.5 |
| `phase-review <bd-id> <file>` | `bd update <bd-id> --description "$(cat <file>)"` | `/drupal-issue-review` Step 4.9 |
| `phase-depth-pre <bd-id> <file>` | `bd update <bd-id> --design "$(cat <file>)"` | `/drupal-contribute-fix` Step 0.5 |
| `phase-depth-post-fail <bd-id> <post-file> <brief-file>` | `bd comment` x2 | `/drupal-contribute-fix` failure path |
| `phase-verification <bd-id> <file>` | `bd comment <bd-id> --file <file>` (prefixed `bd:phase.verification`) | `/drupal-contribute-fix` post-verifier |
| `phase-push-gate <bd-id> <file>` | `bd note <bd-id> --file <file>` (appends, not replaces) | `/drupal-contribute-fix` Step 5.5 |
| `remember-maintainer <module> <maintainer> <pref>` | `bd remember "<pref>" --key module.<mod>.maintainer_pref.<who>` | Manual or review skill |
| `remember-lore <module> <topic> <insight>` | `bd remember "<insight>" --key module.<mod>.lore.<topic>` | Manual or review skill |
| `query-prior-knowledge <module>` | `bd list` + `bd memories` → JSON to stdout | Fetcher agent |

**Error handling:** Every write subcommand wraps its bd call in:
```bash
if ! bd <cmd> ... 2>/tmp/bd-err-$$.txt; then
  echo "bd-helpers: <subcommand> failed (best-effort, continuing)" >&2
  cat /tmp/bd-err-$$.txt >&2
  rm -f /tmp/bd-err-$$.txt
fi
```
This matches the established best-effort pattern from tickets 031/039.

### `ensure-issue` subcommand (replaces 031 inline)

```bash
ensure_issue() {
  local nid="$1" title="$2"
  local bd_id
  bd_id=$(bd list --external-ref "external:drupal:$nid" --json 2>/dev/null \
    | jq -r '.[0].id // empty')
  if [[ -z "$bd_id" ]]; then
    bd_id=$(bd create "$title" \
      --external-ref "external:drupal:$nid" \
      -l "drupal-$nid" 2>/dev/null) || true
  fi
  echo "$bd_id"
}
```
Returns the bd issue ID to stdout. Caller captures it for subsequent
phase writes. If bd is unreachable, returns empty string; all downstream
phase commands no-op on empty bd_id.

### `query-prior-knowledge` subcommand (the read side)

```bash
query_prior_knowledge() {
  local module="$1"
  local result="{}"

  # 1. Prior issues in this module
  local issues
  issues=$(bd list --label "module-$module" --all --json 2>/dev/null || echo "[]")
  result=$(echo "$result" | jq --argjson i "$issues" '.prior_issues = $i')

  # 2. Maintainer preferences
  local prefs
  prefs=$(bd memories "module.$module.maintainer_pref" 2>/dev/null || echo "")
  result=$(echo "$result" | jq --arg p "$prefs" '.maintainer_prefs = ($p | split("\n") | map(select(. != "")))')

  # 3. Module lore
  local lore
  lore=$(bd memories "module.$module.lore" 2>/dev/null || echo "")
  result=$(echo "$result" | jq --arg l "$lore" '.module_lore = ($l | split("\n") | map(select(. != "")))')

  echo "$result"
}
```

Output format (JSON to stdout):
```json
{
  "prior_issues": [
    {"id": "CONTRIB_WORKBENCH-abc", "title": "...", "status": "merged", "labels": ["drupal-3581952", "module-ai"]}
  ],
  "maintainer_prefs": [
    "module.ai.maintainer_pref.marcus: prefers extending existing events over new hooks"
  ],
  "module_lore": [
    "module.ai.lore.testing: use kernel tests for entity access checks, not unit tests"
  ]
}
```

### Write side: skill edits

**`/drupal-issue` SKILL.md — Step 2.5 (refactor 031 inline writes):**

Replace the existing `bd create`/`bd update` block with:
```bash
BD_ID=$(scripts/bd-helpers.sh ensure-issue "$ISSUE_ID" "Drupal issue $ISSUE_ID: {title}")
if [[ -n "$BD_ID" ]]; then
  scripts/bd-helpers.sh phase-classification "$BD_ID" "$WORKFLOW_DIR/00-classification.json"
fi
```

**`/drupal-issue` SKILL.md — Step 0.5 (new bd write after resonance):**

After resonance checker returns and writes `workflow/00-resonance.json`:
```bash
if [[ -n "$BD_ID" ]] && [[ -f "$WORKFLOW_DIR/00-resonance.json" ]]; then
  scripts/bd-helpers.sh phase-resonance "$BD_ID" "$WORKFLOW_DIR/00-resonance.json"
fi
```

**`/drupal-issue-review` SKILL.md — Step 4.9 (new bd write after depth signals):**

After writing `01-review-summary.json`:
```bash
BD_ID=$(bd list --external-ref "external:drupal:$ISSUE_ID" --json 2>/dev/null | jq -r '.[0].id // empty')
if [[ -n "$BD_ID" ]] && [[ -f "$WORKFLOW_DIR/01-review-summary.json" ]]; then
  scripts/bd-helpers.sh phase-review "$BD_ID" "$WORKFLOW_DIR/01-review-summary.json"
fi
```

**`/drupal-contribute-fix` SKILL.md — Step 0.5 (new bd write after pre-fix gate):**

After pre-fix gate writes `01b-solution-depth-pre.json`:
```bash
BD_ID=$(bd list --external-ref "external:drupal:$ISSUE_ID" --json 2>/dev/null | jq -r '.[0].id // empty')
if [[ -n "$BD_ID" ]] && [[ -f "$WORKFLOW_DIR/01b-solution-depth-pre.json" ]]; then
  scripts/bd-helpers.sh phase-depth-pre "$BD_ID" "$WORKFLOW_DIR/01b-solution-depth-pre.json"
fi
```

**`/drupal-contribute-fix` SKILL.md — failure path (refactor 030 inline writes):**

Replace the existing `bd comment` x2 with:
```bash
if [[ -n "$BD_ID" ]]; then
  scripts/bd-helpers.sh phase-depth-post-fail "$BD_ID" \
    "$WORKFLOW_DIR/02b-solution-depth-post.json" \
    "$WORKFLOW_DIR/02c-recovery-brief.md"
fi
```

**`/drupal-contribute-fix` SKILL.md — after verifier (new bd write):**

After Step 5 (Verifier Agent) returns:
```bash
if [[ -n "$BD_ID" ]] && [[ -f "$WORKFLOW_DIR/02-verification-results.json" ]]; then
  scripts/bd-helpers.sh phase-verification "$BD_ID" "$WORKFLOW_DIR/02-verification-results.json"
fi
```

Note: `02-verification-results.json` doesn't exist yet as a formal workflow
file — the verifier agent returns its verdict as prose. For this ticket,
the verification bd write will use the verifier's structured return if
available, or skip if not. This is a graceful degradation, not a blocker.

**`/drupal-contribute-fix` SKILL.md — Step 5.5 (new bd write after checklist):**

After writing `03-push-gate-checklist.json`:
```bash
if [[ -n "$BD_ID" ]] && [[ -f "$WORKFLOW_DIR/03-push-gate-checklist.json" ]]; then
  scripts/bd-helpers.sh phase-push-gate "$BD_ID" "$WORKFLOW_DIR/03-push-gate-checklist.json"
fi
```

### Read side: fetcher enrichment

**`.claude/agents/drupal-issue-fetcher.md`** — new step in the `full` mode,
after all upstream artifacts are fetched and before the agent returns:

```markdown
### Step N: Query bd for prior knowledge (best-effort)

After all artifacts are written to the output directory, query bd for
cross-issue intelligence about this module:

```bash
PRIOR=$(scripts/bd-helpers.sh query-prior-knowledge "<module_name>")
if [[ -n "$PRIOR" ]] && [[ "$PRIOR" != "{}" ]]; then
  echo "$PRIOR" > "$OUT_DIR/prior-knowledge.json"
fi
```

If bd has no data for this module, the file is not created. Skills that
read the artifacts directory should check for its existence but not
require it.

Also query for this specific issue's prior bd state:

```bash
BD_ID=$(bd list --external-ref "external:drupal:<issue_id>" --json 2>/dev/null | jq -r '.[0].id // empty')
if [[ -n "$BD_ID" ]]; then
  bd show "$BD_ID" --json > "$OUT_DIR/bd-issue-state.json" 2>/dev/null || true
fi
```

This gives the controller the full bd state for the issue (all prior
phase writes, comments, notes) in one file.
```

The `delta` mode should also run this query (it's a read, not a fetch).

### Module label convention

For `query-prior-knowledge` to find prior issues, issues must be labeled
with `module-<name>`. This label should be added by `ensure-issue` at
creation time:

```bash
bd create "$title" \
  --external-ref "external:drupal:$nid" \
  -l "drupal-$nid,module-$module" 2>/dev/null
```

The module name comes from the classification data (already available at
Step 2.5). This requires a small addition to `ensure-issue`: accept an
optional `--module <name>` flag.

### bd schema additions (`docs/bd-schema.md`)

New memory key patterns:

| Kind | Key pattern | Example |
|---|---|---|
| Maintainer pref | `module.<mod>.maintainer_pref.<who>` | `module.ai.maintainer_pref.marcus` |
| Module lore | `module.<mod>.lore.<topic>` | `module.ai.lore.testing` |

### CLAUDE.md addition

New "Cross-issue memory (bd)" subsection:

```markdown
## Cross-issue memory (bd)

bd serves as the workbench's institutional memory. Every workflow phase
writes its artifacts to bd via `scripts/bd-helpers.sh` (never inline bd
commands). The fetcher queries bd for PRIOR KNOWLEDGE at the start of
each issue.

To manually add maintainer preferences or module lore:
  scripts/bd-helpers.sh remember-maintainer ai marcus "prefers extending existing events"
  scripts/bd-helpers.sh remember-lore ai testing "use kernel tests for entity access checks"

These are surfaced automatically when working on any issue in the same module.
```

## Files

### Created (1)

| Path | Lines | Purpose |
|---|---|---|
| `scripts/bd-helpers.sh` | ~180 | Centralized bd write/query CLI |

### Modified (8)

| Path | Change |
|---|---|
| `.claude/skills/drupal-issue/SKILL.md` | Refactor Step 2.5 bd writes to use helpers + add Step 0.5 resonance write |
| `.claude/skills/drupal-issue-review/SKILL.md` | Add phase-review bd write at Step 4.9 |
| `.claude/skills/drupal-contribute-fix/SKILL.md` | Add phase-depth-pre, phase-verification, phase-push-gate writes; refactor failure-path writes |
| `.claude/agents/drupal-issue-fetcher.md` | Add PRIOR KNOWLEDGE query step |
| `docs/bd-schema.md` | Add maintainer_pref + module_lore key patterns |
| `CLAUDE.md` | Add "Cross-issue memory" subsection |
| `docs/tickets/034-bd-cross-issue-memory.md` | Status flip + Resolution |
| `docs/tickets/00-INDEX.md` | Status flip for 034 |

## Acceptance criteria

| # | Criterion | Test |
|---|---|---|
| 1 | `scripts/bd-helpers.sh ensure-issue 99999 "Test"` creates a bd issue and returns its ID | Run on remote, verify non-empty stdout |
| 2 | `scripts/bd-helpers.sh phase-classification <id> <file>` writes metadata to the bd issue | `bd show <id> --json \| jq .metadata` shows content |
| 3 | `scripts/bd-helpers.sh query-prior-knowledge ai` returns JSON with prior_issues + prefs + lore | Run on remote, verify JSON structure |
| 4 | `scripts/bd-helpers.sh remember-maintainer ai marcus "prefers events"` stores a memory | `bd memories module.ai` shows it |
| 5 | `scripts/bd-helpers.sh remember-lore ai testing "kernel tests"` stores a memory | `bd memories module.ai` shows it |
| 6 | 031's inline bd writes in `/drupal-issue` Step 2.5 are replaced with helper calls | Code review |
| 7 | 030's inline bd writes in failure path are replaced with helper calls | Code review |
| 8 | `/drupal-issue-review` Step 4.9 has a phase-review bd write | Code review |
| 9 | `/drupal-contribute-fix` has phase-depth-pre, phase-verification, phase-push-gate writes | Code review |
| 10 | Fetcher agent `full` mode includes PRIOR KNOWLEDGE query step | Code review |
| 11 | All bd writes are best-effort (failure doesn't block skill) | Code review of error handling |

## Testing strategy

**Live testing on remote:**
- Create a synthetic bd issue via `ensure-issue`
- Run each `phase-*` subcommand against it with fixture files
- Verify `bd show <id>` reflects the writes
- Run `query-prior-knowledge` and verify JSON output
- Test `remember-*` subcommands and verify `bd memories` output
- Verify all subcommands handle bd-unavailable gracefully (rename bd binary temporarily)

**Wiring verification:**
- Skill edits are code-reviewed (not runtime-tested — same deferred pattern as 030/031/039)

## Non-goals

- **File-level history** (`bd label add file-<slug>`) — requires touching git-diff parsing, lower value than module-level memory. Deferred.
- **Automatic maintainer-pref extraction** — the review skill could auto-detect maintainer patterns, but that's AI inference, not mechanical. Deferred to a future skill enhancement.
- **bd schema migration for existing issues** — existing bd issues from 031 won't have module labels. They'll be invisible to `query-prior-knowledge` until the user re-runs the issue or manually adds labels. This is acceptable for organic adoption.

## Risks

1. **`bd memories` output format is freeform text, not JSON.** The `query-prior-knowledge` parsing assumes newline-separated entries. If bd changes its output format, the jq parsing breaks. Mitigated: the helper is the single place to fix.

2. **`bd note` appends but has no prefix.** The push-gate write uses `bd note` to append the checklist. If multiple pushes happen, multiple entries accumulate. This is intentional — cumulative push gate history is the desired behavior.

3. **Module name comes from classification data.** If classification is wrong or missing, the module label is wrong. Mitigated: the fetcher also queries by issue nid, not just module name.

4. **`bd list --external-ref` is the bd-id lookup path.** Every phase write needs the bd ID. The pattern is: `bd list --external-ref "external:drupal:<nid>" --json | jq -r '.[0].id // empty'`. This runs on every write. If bd is slow, it adds latency. Mitigated: best-effort — timeout or failure just skips the write.
