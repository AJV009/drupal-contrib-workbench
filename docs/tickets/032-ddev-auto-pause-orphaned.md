# TICKET-032: DDEV Auto-Pause for Orphaned Stacks

**Status:** NOT_STARTED
**Priority:** P2
**Affects:** New file `pause-orphaned-ddev.sh` at workbench root
**Type:** Tooling

## Problem

Running DDEV stacks accumulate when their corresponding tmux sessions die. Audit at planning time:

- 6 running DDEV stacks: `ai-3508503`, `ai-3580690`, `d3560681`, `d3577173`, `d3581952`, `d3582345`
- 6 live tmux sessions including 1 main `drupal-contrib-bench-7nda`
- **`ai-3508503` is a confirmed orphan**: tui.json records its sessions as `drupal-issue-2zis`, `drupal-issue-e15u`, `drupal-issue-jof3` — none of which exist in `tmux ls`

Each orphaned stack consumes RAM, sockets, and a slot in the docker bridge. The user has 32 GB RAM and tons of headroom, so this isn't urgent — but the noise is real, and the user explicitly asked for cleanup tooling.

## Solution

A small bash script at the workbench root: `pause-orphaned-ddev.sh`. No daemon, no cron prescribed. Run manually when you notice sprawl, or wire to your own scheduling.

Per user direction: "**Just pause if the shell doesn't exist. Not a cap or anything because some rare times I work on a LOT of issues together.**"

```bash
#!/usr/bin/env bash
# pause-orphaned-ddev.sh
# Pauses any running DDEV stack whose associated tmux session is no longer alive.
# Mapping flow: ddev stack -> issue id -> tui.json sessions[] -> tmux ls
# READ-ONLY for tui.json (does not modify; tui-browser is the consumer).

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TUI="$SCRIPT_DIR/tui.json"
LIVE_TMUX=$(tmux ls 2>/dev/null | cut -d: -f1 | sort -u || true)

[ -f "$TUI" ] || { echo "no tui.json found at $TUI"; exit 0; }

ddev list -j 2>/dev/null | jq -r '.raw[] | select(.status=="running") | .name' | while read -r stack; do
  # Strip prefix to get bare numeric issue id (matches d3577173, ai-3580690, ai3508503)
  iss=$(echo "$stack" | sed -E 's/^(d|ai-?)//')

  # Read tui.json sessions[] for this issue id
  iss_sessions=$(jq -r --arg k "$iss" '.[$k].sessions[]? // empty' "$TUI" 2>/dev/null)

  # If no sessions ever recorded -> skip (manual ddev start, leave alone)
  if [ -z "$iss_sessions" ]; then
    echo "skip $stack: no tui.json mapping (manual start?)"
    continue
  fi

  # Check if any of those sessions is currently alive
  alive=false
  for s in $iss_sessions; do
    if echo "$LIVE_TMUX" | grep -qx "$s"; then
      alive=true
      break
    fi
  done

  if [ "$alive" = false ]; then
    echo "PAUSE $stack (no live tmux session for issue $iss; recorded sessions: $iss_sessions)"
    ddev pause "$stack"
  else
    echo "keep $stack (alive tmux for issue $iss)"
  fi
done
```

## tui.json contract (do not break)

This script READS tui.json only. It does not write. The contract per `/home/alphons/project/tui-browser/server/tui-overrides.js` line 80 is:

```js
// @returns {{ title?: string, fileCwd?: string, actions?: Array } | null}
```

tui-browser only consumes `title`, `fileCwd`, `actions[]`. The `sessions[]` field is the launcher's own use, free for us to also read. As long as we never write to tui.json, tui-browser is unaffected.

## Acceptance

1. Running the script today (with the documented state) should pause `ai-3508503` and leave the other 5 running stacks alone
2. After running, `ddev list` shows `ai-3508503` as `paused`
3. Re-running is idempotent (already-paused stacks aren't touched)
4. Stacks with no tui.json entry are skipped with an explanatory log line (not paused)
5. Script does not modify `tui.json` (verify mtime unchanged)

## Dependencies

None. Standalone tooling.

## Notes

Future improvements (separate tickets if useful):
- A `--dry-run` flag (would only print, not pause)
- A `--age-min N` filter to only pause stacks orphaned for >N minutes (avoids racing with brand-new tmux sessions that haven't yet written to tui.json)
- A companion `resume-by-issue.sh <issue-id>` that flips the orphan back to running when you restart work on it

These can be added later if the basic version proves useful.

## Resolution (2026-04-10)

Ticket 032 shipped with Option R (tui.json as authoritative ledger) instead
of the draft's name-parsing approach. All 8 acceptance criteria pass
(criterion 8 is wiring-verified only — runtime verification deferred to
first real issue setup after the ticket lands).

### What shipped

**Phase A — Foundation:**
- New `docs/tui-json-schema.md` formalizing tui.json's shape including the
  new optional `ddev_name` field.
- `pause-orphaned-ddev.sh` at workbench root: 130 lines, three modes
  (default stop, `register`, `--dry-run`).

**Phase B — `register` mode:**
- One-shot backfill subcommand: iterates `ddev list -j` (ALL stacks —
  running + paused), extracts nid from each stack's `approot` via
  `grep -oE 'DRUPAL_ISSUES/[0-9]+'`, writes `ddev_name` into the
  matching `tui.json` entry if unset.
- Backfilled 25 mappings (6 running + 19 paused) in one pass. Idempotent
  on re-run (0 new mappings).

**Phase C — Default mode:**
- Two-pass loop: Pass 1 iterates tui.json entries with `ddev_name`,
  checks `sessions[]` against live `tmux ls`, stops orphans via
  `ddev stop`. Pass 2 reports running stacks with no `ddev_name` as
  skips with a backfill hint.
- **Empty sessions[] → skip** (not stop). Per original ticket intent:
  stacks created outside the launcher flow can't be liveness-verified,
  so they're left alone with a warning.
- `--dry-run` prefixes `DRY` on would-stop lines, never calls `ddev stop`.
- Default mode makes zero writes to tui.json (verified by mtime check).

**Phase D — Agent hook:**
- `drupal-ddev-setup.md` gained Phase 1.5 subsection after `ddev start`.
  Writes `tui.json[{issue_id}].ddev_name = "d{issue_id}"` via `jq` with
  temp-file + `mv`. Best-effort: warn + continue on failure.

**Phase E — Documentation:**
- `CLAUDE.md` gained "Orphaned DDEV cleanup" subsection.
- `docs/tui-json-schema.md` created (canonical reference for tui.json).
- Phase 2 Integrated Snapshot refreshed across tickets 027-032.

### Acceptance results

| # | Requirement | Result |
|---|---|---|
| 1 | Stop `ai-3508503`, leave other running stacks alone | PASS — 1 PAUSE, 4 keep, 1 skip (d3582345 empty sessions) |
| 2 | `ddev list` shows `ai-3508503` as stopped after run | PASS — status: `stopped` (DDEV 1.25+ uses `stopped` not legacy `paused`) |
| 3 | Re-run is idempotent (already-stopped not considered) | PASS — 0 paused, 4 kept, 1 skipped |
| 4 | Missing `ddev_name` produces skip line, doesn't stop | PASS — d3560681 without ddev_name: skip message, stack stayed running |
| 5 | Default mode does not modify tui.json (mtime unchanged) | PASS |
| 6 | `register` backfills all stacks in one pass | PASS — 25 new mappings (all stacks, not just running) |
| 7 | `--dry-run` previews without stopping | PASS — DRY prefix, ai-3508503 stayed running |
| 8 | Agent hook populates `ddev_name` on new setup | WIRING — runtime deferred to first real issue setup |

### Gotchas discovered during implementation

1. **`ddev pause` does not exist in DDEV 1.25.1.** The correct command is
   `ddev stop`. The ticket draft assumed `ddev pause`; existing stacks
   with status `paused` in `ddev list` were paused by an older DDEV
   version. `ddev stop` produces status `stopped` (not `paused`).
   Script now uses `ddev stop` and the error-handling pattern
   (`if ! ddev stop ... then warn + continue`) is verified working.

2. **`register` backfills ALL stacks (running + paused), not just running.**
   `ddev list -j` returns every known stack. This is intentional — paused
   stacks may be resumed later and subsequently orphaned, so pre-populating
   their `ddev_name` now saves a future `register` run.

3. **Empty `sessions[]` in tui.json is a distinct case from "no sessions
   alive."** The `register` subcommand creates tui.json entries with only
   `ddev_name` (no `title`/`fileCwd`/`sessions`) for stacks whose nid
   has no pre-existing tui.json entry. Default mode must skip these rather
   than treat empty sessions as "all dead" — the stack was never managed
   by the launcher, so liveness can't be verified. This matched the
   original ticket's explicit intent: "If no sessions ever recorded ->
   skip (manual ddev start, leave alone)."

4. **`d3582345` had no tui.json entry before `register` ran.** It appears
   to have been created outside the launcher flow. After `register`, it
   has only `ddev_name` and nothing else. Default mode correctly skips it.

### Design decisions locked in

1. **tui.json as authoritative ledger** replaces the draft's name-parsing
   regex. Robust to any future project prefix.
2. **Default mode is read-only.** All writes flow through `register` or
   the setup agent hook.
3. **`register` uses path-based nid extraction, not name parsing.**
4. **Agent hook is best-effort.** jq failure doesn't abort stack setup.
5. **`ddev stop` over `ddev pause`** on DDEV 1.25+. Script name and output
   labels say "pause" for human readability; the underlying command is
   `ddev stop`.
6. **Empty sessions → skip, not stop.** Defensive default for stacks
   created outside the launcher flow.

## Phase 2 Integrated Snapshot

See [phase-2-integrated-snapshot.md](phase-2-integrated-snapshot.md) for the
shared cross-ticket snapshot (maintained as a single file to avoid duplication).

