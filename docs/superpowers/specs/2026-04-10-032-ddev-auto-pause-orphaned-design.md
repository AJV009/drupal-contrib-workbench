# Ticket 032 — DDEV Auto-Pause for Orphaned Stacks

**Status:** SPEC (not yet implemented)
**Priority:** P2
**Type:** Tooling
**Depends on:** none (standalone; reuses 027's `pwd -P` convention)

## Goal

Add a manually-invoked workbench-root script that pauses DDEV stacks whose
launcher-created tmux sessions are no longer alive, using explicit metadata
in `tui.json` (new `ddev_name` field) as the join key. Hook the
`drupal-ddev-setup` agent to populate that metadata on every new stack
creation, so the routine is self-maintaining going forward. Include a
one-shot `register` subcommand to backfill existing pre-032 stacks.

## Why not the draft ticket's approach

The original ticket draft used `sed -E 's/^(d|ai-?)//'` to extract a nid
from a DDEV stack name. That works for today's 6 running stacks but
hardcodes two known prefix conventions (`d` and `ai-?`). Any new project
that happens to produce a differently-named stack would be silently
skipped. The user asked for a more durable approach, framed as: "we can
use a pattern whenever launching new instances and then use that to deal
with idle ones, since we are not making this backward compatibility, we
can build a new routine here."

This spec adopts that direction: `tui.json` becomes the authoritative
ledger of `nid → ddev_name`, written by the setup agent at creation time
and read (but not written) by the pause script in its normal hot path.

## Architecture

### The new ledger field

`tui.json[<nid>].ddev_name` — string, optional. Contains the exact
DDEV project name (same value passed to `ddev config --project-name=`).
Written by the setup agent on each new stack. Read by the pause script.
Preserved across launcher `write_tui_json` calls (verified by reading
the jq expression in `drupal-issue.sh:104-128` — it only touches
`title`/`fileCwd`/`actions`/`sessions` and leaves other fields alone).

`tui-browser` is unaffected: its documented contract consumes
`title`/`fileCwd`/`actions[]`, and the new field is additive.

### Data flow at creation time

```
drupal-ddev-setup agent
  ├── ddev config --project-type=drupal ... --project-name=d<nid>
  ├── ddev start
  └── (NEW) jq write: tui.json[<nid>].ddev_name = "d<nid>"
```

### Data flow at pause time

```
./pause-orphaned-ddev.sh
  ├── ddev list -j               → set of {name, status, approot}
  ├── tmux ls                    → set of live session names
  ├── tui.json                   → map of nid → {sessions[], ddev_name}
  └── for each nid with ddev_name set:
        if ddev_name is "running" AND no session in sessions[] is live tmux:
            ddev pause <ddev_name>
```

### One-shot register subcommand

```
./pause-orphaned-ddev.sh register
  └── for each running ddev stack:
        nid = grep -oE 'DRUPAL_ISSUES/[0-9]+' <approot> | cut -d/ -f2
        if nid valid AND tui.json[nid].ddev_name is unset:
            jq write tui.json[nid].ddev_name = <stack>
```

This uses the structural invariant `DRUPAL_ISSUES/<nid>/` that every
issue root obeys (launcher writes into it, agent cd's into it, skills
read from it). It's the same invariant used throughout the workbench —
stable enough to drive a one-shot migration.

## Files

### Created

| Path | Lines | Purpose |
|---|---|---|
| `pause-orphaned-ddev.sh` | ~80 | Main script (workbench root). Three modes: default pause, `register`, `--dry-run`. |
| `docs/tui-json-schema.md` | ~30 | Formalizes tui.json shape including the new `ddev_name` field. Future readers / editors have a single source of truth. |

### Modified

| Path | Change |
|---|---|
| `.claude/agents/drupal-ddev-setup.md` | New "Phase 1.5: Register DDEV project in tui.json" subsection right after `ddev start`. ~15 lines. Best-effort jq write. |
| `CLAUDE.md` | New "Orphaned DDEV cleanup" subsection. ~15 lines. Documents when/why/how to run `./pause-orphaned-ddev.sh`. |
| `docs/tickets/032-ddev-auto-pause-orphaned.md` | Status flip NOT_STARTED → COMPLETED + Resolution note. |
| `docs/tickets/00-INDEX.md` | Status flip for 032. |
| `docs/tickets/027.md`, `028.md`, `029.md`, `030.md`, `031.md`, `032.md` | Phase 2 Integrated Snapshot refresh (032 added to tables, new tui.json schema gotcha if discovered during impl). |

## Script: `pause-orphaned-ddev.sh`

### Shebang, flags, preamble

```bash
#!/usr/bin/env bash
# pause-orphaned-ddev.sh — pause DDEV stacks whose launcher tmux sessions are dead.
#
# USAGE:
#   ./pause-orphaned-ddev.sh              pause orphans (default)
#   ./pause-orphaned-ddev.sh --dry-run    preview what would be paused, no-op
#   ./pause-orphaned-ddev.sh register     one-time backfill of tui.json.ddev_name
#
# READS tui.json. WRITES tui.json only in `register` mode.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"  # -P per ticket 027
TUI="$SCRIPT_DIR/tui.json"
MODE="pause"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    register)   MODE="register"; shift ;;
    --dry-run)  DRY_RUN=true; shift ;;
    -h|--help)  sed -n '2,10p' "$0"; exit 0 ;;
    *)          echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$TUI" ]] || { echo "no tui.json at $TUI" >&2; exit 0; }
```

### `register` subcommand body

```bash
if [[ "$MODE" == "register" ]]; then
  changed=0
  while IFS=$'\t' read -r stack approot; do
    nid=$(echo "$approot" | grep -oE 'DRUPAL_ISSUES/[0-9]+' | head -1 | cut -d/ -f2 || true)
    if [[ -z "$nid" ]]; then
      echo "skip $stack: approot not under DRUPAL_ISSUES/<nid>/"
      continue
    fi
    existing=$(jq -r --arg k "$nid" '.[$k].ddev_name // empty' "$TUI")
    if [[ -z "$existing" ]]; then
      tmp=$(mktemp)
      jq --arg k "$nid" --arg n "$stack" \
         '.[$k] //= {} | .[$k].ddev_name = $n' "$TUI" > "$tmp" && mv "$tmp" "$TUI"
      echo "register $stack -> tui.json[$nid].ddev_name"
      changed=$((changed + 1))
    elif [[ "$existing" != "$stack" ]]; then
      echo "WARN $stack: tui.json[$nid].ddev_name already set to '$existing' (not overwriting)"
    else
      echo "keep $stack: tui.json[$nid].ddev_name already correct"
    fi
  done < <(ddev list -j 2>/dev/null | jq -r '.raw[] | [.name, .approot] | @tsv')
  echo "registered $changed new mappings"
  exit 0
fi
```

### Default pause loop

```bash
LIVE_TMUX=$(tmux ls 2>/dev/null | cut -d: -f1 | sort -u || true)

# running ddev stacks (names only, one per line)
RUNNING=$(ddev list -j 2>/dev/null | jq -r '.raw[] | select(.status=="running") | .name' | sort -u)

# map nid -> ddev_name for tui.json entries that have ddev_name set
mapfile -t ENTRIES < <(jq -r 'to_entries[] | select(.value.ddev_name) | "\(.key)\t\(.value.ddev_name)"' "$TUI")

pause_count=0
keep_count=0
skip_count=0

# Pass 1: for each registered (nid, name) pair, decide pause / keep
for line in "${ENTRIES[@]}"; do
  nid="${line%%$'\t'*}"
  name="${line##*$'\t'}"

  # only process currently-running stacks
  if ! grep -qFx "$name" <<< "$RUNNING"; then
    continue
  fi

  sessions=$(jq -r --arg k "$nid" '.[$k].sessions[]? // empty' "$TUI")
  alive=false
  for s in $sessions; do
    if grep -qFx "$s" <<< "$LIVE_TMUX"; then
      alive=true
      break
    fi
  done

  if $alive; then
    echo "keep  $name (nid $nid, live tmux session)"
    keep_count=$((keep_count + 1))
  else
    if $DRY_RUN; then
      echo "DRY   $name (nid $nid; would pause — recorded sessions: $(echo $sessions | tr '\n' ' '))"
    else
      echo "PAUSE $name (nid $nid; recorded sessions: $(echo $sessions | tr '\n' ' '))"
      if ! ddev pause "$name"; then
        echo "  warn: ddev pause $name failed (continuing)" >&2
      fi
    fi
    pause_count=$((pause_count + 1))
  fi
done

# Pass 2: report running stacks that have no tui.json ddev_name registered
REGISTERED_NAMES=$(printf '%s\n' "${ENTRIES[@]}" | awk -F'\t' '{print $2}' | sort -u)
while read -r stack; do
  [[ -z "$stack" ]] && continue
  if ! grep -qFx "$stack" <<< "$REGISTERED_NAMES"; then
    echo "skip  $stack (no tui.json ddev_name registered — run \`./pause-orphaned-ddev.sh register\` to backfill)"
    skip_count=$((skip_count + 1))
  fi
done <<< "$RUNNING"

if $DRY_RUN; then
  echo "[dry-run] $pause_count would be paused, $keep_count kept, $skip_count skipped"
else
  echo "$pause_count paused, $keep_count kept, $skip_count skipped"
fi
```

### Invariants / properties

- **Default mode does not write tui.json.** Only `register` writes. mtime
  unchanged on default-mode runs. Verified by acceptance criterion 5.
- **`set -e` doesn't kill the loop on individual `ddev pause` failure.** The
  `if ! ddev pause ...; then` pattern catches the error and reports a
  warning without aborting the rest of the iteration.
- **Idempotent.** Already-paused stacks don't appear in the RUNNING set,
  so they're not considered. Re-running produces zero new PAUSE lines.
- **Dry-run is pure.** Prints `DRY` prefix lines, never calls `ddev pause`.
- **Pre-032 stacks** (tui.json entries without `ddev_name`) are **not
  silently skipped** — they produce a clear `skip <stack> (no tui.json
  ddev_name registered — run register to backfill)` message.
- **Uses `grep -Fx`** (fixed-string, whole-line) for all containment
  checks, so stack names / session names containing regex metacharacters
  are handled literally.

## Agent hook: `drupal-ddev-setup.md`

Add a new "Phase 1.5" subsection immediately after the existing Phase 1
`ddev start` line. Placement matters: after `ddev start` because we want
to write only on successful stack creation, and before Phase 2 (which
may take minutes and would delay the tui.json update unnecessarily).

```markdown
### Phase 1.5: Register DDEV project in tui.json

After `ddev start` succeeds, record the DDEV project name in `tui.json` so
that `pause-orphaned-ddev.sh` can later identify this stack when the tmux
session eventually dies. This is a **best-effort** write — if `tui.json`
is missing or `jq` fails, continue; the pause script's `register` mode
can backfill later.

```bash
DDEV_NAME="d{issue_id}"   # same value passed to --project-name above
TUI="$WORKBENCH/tui.json"
if [ -f "$TUI" ]; then
  tmp=$(mktemp)
  if jq --arg k "{issue_id}" --arg n "$DDEV_NAME" \
       '.[$k] //= {} | .[$k].ddev_name = $n' "$TUI" > "$tmp"; then
    mv "$tmp" "$TUI"
    echo "registered tui.json[{issue_id}].ddev_name = $DDEV_NAME"
  else
    rm -f "$tmp"
    echo "warn: failed to register ddev_name in tui.json (continuing)" >&2
  fi
fi
```
```

Templated `{issue_id}` placeholder matches the agent's existing convention.
`$WORKBENCH` is already defined earlier in the agent prose (line ~45).

## Schema doc: `docs/tui-json-schema.md`

New file, ~30 lines. Formalizes the `tui.json` shape:

```markdown
# tui.json schema

`tui.json` lives at the workbench root and is a JSON object keyed by
Drupal issue nid (string). Each entry holds metadata about one issue
that has been worked on at least once.

## Writers

| Writer | Fields touched | Trigger |
|---|---|---|
| `drupal-issue.sh` → `write_tui_json()` | `title`, `fileCwd`, `actions` (default seed), `sessions` (unique append) | Every launcher invocation (new session or resume) |
| `drupal-ddev-setup` agent (ticket 032) | `ddev_name` | After `ddev start` succeeds on first stack creation |
| `pause-orphaned-ddev.sh register` (ticket 032) | `ddev_name` (backfill only when unset) | Manual one-shot migration |

## Readers

| Reader | Fields read | Contract |
|---|---|---|
| `tui-browser` (external project) | `title`, `fileCwd`, `actions` | Public contract; never break these. |
| `pause-orphaned-ddev.sh` (default mode) | `sessions`, `ddev_name` | Added in ticket 032. |

## Field reference

| Field | Type | Set by | Purpose |
|---|---|---|---|
| `title` | string | launcher | Shown in tui-browser |
| `fileCwd` | string (path) | launcher | Working directory root for this issue |
| `actions` | array of objects | launcher | Clickable shortcuts shown in tui-browser |
| `sessions` | array of strings | launcher | tmux session names ever used for this issue (unique-append, never shrunk) |
| `ddev_name` | string (optional) | ddev-setup agent | DDEV project name for this issue's stack, used by `pause-orphaned-ddev.sh` |

## Invariants

1. Keys are bare numeric Drupal nids as strings.
2. `sessions` is append-only; the launcher never removes entries. A stale
   session name staying in `sessions` is safe because `pause-orphaned-ddev.sh`
   joins against live `tmux ls` output, not historical state.
3. The file is always valid JSON. Writers use `jq` with temp-file + `mv`
   to avoid partial writes.
4. No field except `title`/`fileCwd`/`actions` is part of the tui-browser
   public contract. Other fields are free for internal workbench use.
```

## `CLAUDE.md` subsection

New "Orphaned DDEV cleanup" subsection in the tooling area:

```markdown
## Orphaned DDEV cleanup

DDEV stacks accumulate when tmux sessions die (tmux server restart,
machine reboot, manual kill). To pause any stack whose launcher-created
tmux session is no longer alive, run:

```bash
./pause-orphaned-ddev.sh              # pause orphans
./pause-orphaned-ddev.sh --dry-run    # preview only, no pause
./pause-orphaned-ddev.sh register     # one-time backfill after a workbench upgrade
```

How it works: the DDEV setup agent writes `tui.json[<nid>].ddev_name`
when it creates a stack. The pause script reads that mapping, checks
each stack's recorded tmux sessions against live `tmux ls`, and pauses
any stack that has no live session. tui.json is NOT modified in default
mode (only in `register` mode).

Pre-ticket-032 stacks need a one-time `register` run to populate their
`ddev_name` field. After that, every new issue setup registers itself
automatically.
```

## Acceptance criteria

| # | Requirement | Verification |
|---|---|---|
| 1 | Script paused `ai-3508503` on today's live state, leaving the other 5 running stacks alone | Run `register` then default mode. Output contains `PAUSE ai-3508503` + five `keep <stack>` lines. |
| 2 | After pause run, `ddev list` reports `ai-3508503` as `paused` | `ddev list -j \| jq -r '.raw[] \| select(.name=="ai-3508503").status'` → `paused` |
| 3 | Re-running default mode is idempotent | Second run: zero `PAUSE`, five `keep`, zero `skip`. |
| 4 | Stacks with no tui.json `ddev_name` are skipped with an explanatory log line (not paused) | Temporarily remove `ddev_name` from one entry, re-run. Verify `skip  <stack> (no tui.json ddev_name registered...)` message and stack is still running. |
| 5 | Default mode does not modify `tui.json` (verify mtime unchanged) | `stat -c %Y tui.json` before and after a default-mode run — equal. |
| 6 | `register` subcommand backfills all running stacks in one run | Start from clean tui.json (no `ddev_name` fields). Run `register`. Verify `jq '[to_entries[] \| select(.value.ddev_name)] \| length' tui.json` returns 6. |
| 7 | `--dry-run` prints would-pause lines without calling `ddev pause` | Re-orphan a stack, run `--dry-run`, verify `DRY <stack>` output and `ddev list` still shows stack as running. |
| 8 | Agent hook populates `ddev_name` on new issue setup (wiring verification only) | Code review of `.claude/agents/drupal-ddev-setup.md` Phase 1.5 section. Runtime verification deferred to first real-world issue setup after ticket lands. |

Criterion 8 is wiring-verified only, same deferred-runtime pattern as
ticket 030 criterion 5 and ticket 031's preflight reinstate loop. Real
end-to-end test happens on first live issue setup.

## Testing strategy

Live testing on remote (`alphons@192.168.0.218:/home/alphons/drupal/CONTRIB_WORKBENCH`):

1. Implement the script and agent edit
2. Run `./pause-orphaned-ddev.sh register` against today's 6-running-stack state
3. Verify `jq 'to_entries | map(select(.value.ddev_name)) | length' tui.json` returns 6
4. Run `./pause-orphaned-ddev.sh --dry-run` → prints `DRY ai-3508503` but does NOT pause
5. Run `./pause-orphaned-ddev.sh` (default) → actually pauses `ai-3508503`
6. Verify `ddev list` shows `ai-3508503` as `paused`, other 5 as `running`
7. Re-run default mode → idempotent (zero pauses)
8. `stat -c %Y tui.json` snapshot before/after → mtime unchanged during default-mode runs
9. Synthetic "no ddev_name" test: back up tui.json, unset one entry's `ddev_name`, re-run default mode, verify skip message
10. Unpause `ai-3508503` manually after tests to restore baseline

**No unit tests.** This is a ~80-line bash script with straightforward
control flow. Live acceptance tests cover all code paths.

## Non-goals (explicitly out of scope)

- `--age-min N` filter — deferred per original ticket
- `resume-by-issue.sh` companion script — deferred per original ticket
- cron / systemd / hook-based automatic scheduling — ticket says "no daemon, no cron prescribed"
- bd writes on pause events — pure ops noise, not worth persisting
- Auto-register from default mode — keeping the write path isolated to the explicit `register` subcommand keeps the "no tui.json writes in default mode" guarantee easy to verify
- Garbage collection of stale `sessions[]` entries — launcher's append-only behavior is fine; joining against live `tmux ls` handles staleness naturally
- Removing the legacy `ai-*` naming — treated uniformly via `register` backfill; no special case needed

## Dependencies

**On previous tickets:**

- **027** — `pwd -P` convention adopted for `SCRIPT_DIR` derivation
- **028** — No direct dep, but snapshot refresh pattern is inherited
- **None of 029/030/031** — functionally independent

**Reverse dependencies:**

- None. This is leaf tooling.

## Risks

1. **Race condition between launcher `write_tui_json` (on resume) and agent hook (on fresh setup)** — strictly sequential in practice: launcher runs FIRST (before the claude session spawns), then the agent runs INSIDE the spawned session. The launcher's write preserves unknown fields, so even in an imagined concurrent scenario, `ddev_name` is not clobbered.
2. **jq write failure during agent hook** — handled: hook is best-effort, prints warn, continues. Backfill via `register` remains available.
3. **`ddev pause` fails on one stack** — handled: caught with `if ! ddev pause`, warns, loop continues.
4. **tui.json corrupted (invalid JSON)** — all writes use temp-file + `mv`, so a crash mid-write leaves the old file intact. If tui.json is pre-corrupted, `jq` will fail and the script exits with a clear error.
5. **New project prefix invalidates `register` extraction** — mitigated: `register` uses path-based nid extraction (`DRUPAL_ISSUES/<nid>/`), not name parsing. Works for any future prefix.

## Estimated scope

- New script: ~80 lines bash
- Agent hook: ~15 lines new prose + bash
- Schema doc: ~30 lines markdown
- CLAUDE.md subsection: ~15 lines
- Ticket + index + snapshot refresh: small edits
- **Total net lines added:** ~200

## Future work (out of scope)

- Promote `ddev_name` into a broader "tui.json as issue metadata ledger" direction (discussed during brainstorming as Option R in its fullest form). Could hold more per-issue operational metadata over time — bd issue id, module/project metadata, launch history. Candidate for a follow-up after ticket 034's cross-issue memory work matures.
- Companion `resume-by-issue.sh <nid>` that un-pauses a stack and optionally reopens its tmux session. Mentioned in original ticket notes as "future improvement."
- A `--since <timestamp>` filter for "only pause stacks orphaned more than N minutes" — mentioned in original ticket notes.
