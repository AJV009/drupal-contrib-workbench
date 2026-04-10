# Ticket 032 — DDEV Auto-Pause for Orphaned Stacks — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a workbench-root cleanup script (`pause-orphaned-ddev.sh`) that pauses DDEV stacks whose launcher tmux sessions are dead, driven by a new `tui.json[<nid>].ddev_name` field. Hook the setup agent to populate that field on every new stack creation. Include a one-shot `register` subcommand to backfill existing stacks.

**Architecture:** `tui.json` becomes the authoritative `nid → ddev_name` ledger. Writers: launcher (unchanged, preserves new field), setup agent (new Phase 1.5 jq write), `pause-orphaned-ddev.sh register` (one-shot backfill). Reader: `pause-orphaned-ddev.sh` default mode. Default mode never writes. The `register` subcommand uses the `DRUPAL_ISSUES/<nid>/` structural invariant to derive nids from `ddev list -j` approot paths — no name parsing, prefix-agnostic.

**Tech Stack:** Bash (with `set -euo pipefail`), jq, ddev, tmux, ssh (remote dev machine at `alphons@192.168.0.218:/home/alphons/drupal/CONTRIB_WORKBENCH`).

**Session rule:** NO GIT COMMITS during implementation. User will review the full pile at end of session.

**Remote execution model:** Every `ssh alphons@192.168.0.218 '<cmd>'` runs on the remote workbench. All paths below are workbench-root relative unless absolute.

---

## Phase A — Foundation: schema doc + script skeleton

### Task 1: Create `docs/tui-json-schema.md`

**Files:**
- Create: `docs/tui-json-schema.md`

- [ ] **Step 1: Write the schema doc**

```bash
ssh alphons@192.168.0.218 'cat > /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tui-json-schema.md' <<'EOF'
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
EOF
```

- [ ] **Step 2: Verify the file exists and is ~30 lines**

Run:
```bash
ssh alphons@192.168.0.218 'wc -l /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tui-json-schema.md'
```

Expected: ~40 lines (close to the spec's "~30" estimate; includes blank lines).

---

### Task 2: Create `pause-orphaned-ddev.sh` skeleton (arg parsing only)

**Files:**
- Create: `pause-orphaned-ddev.sh` (workbench root)

- [ ] **Step 1: Write skeleton with shebang, preamble, and arg parser**

```bash
ssh alphons@192.168.0.218 'cat > /home/alphons/drupal/CONTRIB_WORKBENCH/pause-orphaned-ddev.sh' <<'EOF'
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

echo "mode=$MODE dry_run=$DRY_RUN tui=$TUI"
# TODO: register mode (Task 3)
# TODO: default pause mode (Task 5)
EOF
chmod +x /home/alphons/drupal/CONTRIB_WORKBENCH/pause-orphaned-ddev.sh
```

- [ ] **Step 2: Smoke test the help flag**

Run:
```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && ./pause-orphaned-ddev.sh --help'
```
Expected: prints the USAGE block (lines 2-10 of the script), exits 0.

- [ ] **Step 3: Smoke test unknown arg rejection**

Run:
```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && ./pause-orphaned-ddev.sh --bogus; echo "exit=$?"'
```
Expected: `unknown arg: --bogus` on stderr, `exit=2`.

- [ ] **Step 4: Smoke test default invocation**

Run:
```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && ./pause-orphaned-ddev.sh'
```
Expected: prints `mode=pause dry_run=false tui=/home/alphons/drupal/CONTRIB_WORKBENCH/tui.json`.

- [ ] **Step 5: Smoke test mode switch**

Run:
```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && ./pause-orphaned-ddev.sh register'
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && ./pause-orphaned-ddev.sh --dry-run'
```
Expected: first prints `mode=register dry_run=false`, second prints `mode=pause dry_run=true`.

---

## Phase B — `register` subcommand

### Task 3: Implement `register` mode body

**Files:**
- Modify: `pause-orphaned-ddev.sh` (replace the `# TODO: register mode` line)

- [ ] **Step 1: Snapshot tui.json before touching register logic**

Run:
```bash
ssh alphons@192.168.0.218 'cp /home/alphons/drupal/CONTRIB_WORKBENCH/tui.json /tmp/tui-pre-032.json && ls -la /tmp/tui-pre-032.json'
```
Expected: backup file exists. This is our rollback point in case the register logic mutates tui.json unexpectedly.

- [ ] **Step 2: Replace the register TODO with the full loop**

Use a python heredoc on the LOCAL machine to build the new script content, then scp it:

```bash
python3 <<'PY' > /tmp/pause-orphaned-ddev.sh
s = '''#!/usr/bin/env bash
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

# ============================================================================
# register mode: one-shot backfill of tui.json[<nid>].ddev_name
# ============================================================================
if [[ "$MODE" == "register" ]]; then
  changed=0
  while IFS=$'\\t' read -r stack approot; do
    nid=$(echo "$approot" | grep -oE 'DRUPAL_ISSUES/[0-9]+' | head -1 | cut -d/ -f2 || true)
    if [[ -z "$nid" ]]; then
      echo "skip $stack: approot not under DRUPAL_ISSUES/<nid>/"
      continue
    fi
    existing=$(jq -r --arg k "$nid" '.[$k].ddev_name // empty' "$TUI")
    if [[ -z "$existing" ]]; then
      tmp=$(mktemp)
      jq --arg k "$nid" --arg n "$stack" \\
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

# TODO: default pause mode (Task 5)
echo "default pause mode not yet implemented"
'''
print(s, end='')
PY
scp -q /tmp/pause-orphaned-ddev.sh alphons@192.168.0.218:/home/alphons/drupal/CONTRIB_WORKBENCH/pause-orphaned-ddev.sh
ssh alphons@192.168.0.218 'chmod +x /home/alphons/drupal/CONTRIB_WORKBENCH/pause-orphaned-ddev.sh'
rm /tmp/pause-orphaned-ddev.sh
```

- [ ] **Step 3: Verify the script still parses and the help flag works**

Run:
```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && bash -n pause-orphaned-ddev.sh && echo "syntax ok" && ./pause-orphaned-ddev.sh --help | head -3'
```
Expected: `syntax ok`, followed by the first 3 lines of USAGE.

---

### Task 4: Run `register` against live state, verify acceptance criterion 6

**Files:** None (execution + verification only)

- [ ] **Step 1: Verify no tui.json entry has `ddev_name` yet**

Run:
```bash
ssh alphons@192.168.0.218 'jq "[to_entries[] | select(.value.ddev_name)] | length" /home/alphons/drupal/CONTRIB_WORKBENCH/tui.json'
```
Expected: `0` (clean slate before register runs).

- [ ] **Step 2: Run `register`**

Run:
```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && ./pause-orphaned-ddev.sh register'
```
Expected: 6 `register <stack> -> tui.json[<nid>].ddev_name` lines (one per running stack), final line `registered 6 new mappings`.

- [ ] **Step 3: Verify all 6 running stacks now have `ddev_name` in tui.json**

Run:
```bash
ssh alphons@192.168.0.218 'jq "to_entries | map(select(.value.ddev_name)) | map({nid: .key, ddev_name: .value.ddev_name})" /home/alphons/drupal/CONTRIB_WORKBENCH/tui.json'
```
Expected: 6-entry array containing entries for nids `3508503`, `3580690`, `3560681`, `3577173`, `3581952`, `3582345` with matching `ddev_name` values (`ai-3508503`, `ai-3580690`, `d3560681`, `d3577173`, `d3581952`, `d3582345`).

- [ ] **Step 4: Re-run `register` to verify idempotency**

Run:
```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && ./pause-orphaned-ddev.sh register'
```
Expected: 6 `keep <stack>: tui.json[<nid>].ddev_name already correct` lines, final line `registered 0 new mappings`.

**Acceptance criterion 6 passes** if Step 3 produces 6 entries and Step 4 produces 0 new registrations.

---

## Phase C — Default pause mode + dry-run

### Task 5: Implement default pause loop

**Files:**
- Modify: `pause-orphaned-ddev.sh` (replace the `# TODO: default pause mode` line)

- [ ] **Step 1: Replace the TODO with the full pause loop**

Build the final script locally via python heredoc and scp it:

```bash
python3 <<'PY' > /tmp/pause-orphaned-ddev.sh
s = r'''#!/usr/bin/env bash
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

# ============================================================================
# register mode: one-shot backfill of tui.json[<nid>].ddev_name
# ============================================================================
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

# ============================================================================
# default pause mode: iterate registered entries, pause orphans
# ============================================================================
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
    sessions_joined=$(echo $sessions | tr '\n' ' ')
    if $DRY_RUN; then
      echo "DRY   $name (nid $nid; would pause — recorded sessions: $sessions_joined)"
    else
      echo "PAUSE $name (nid $nid; recorded sessions: $sessions_joined)"
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
'''
print(s, end='')
PY
scp -q /tmp/pause-orphaned-ddev.sh alphons@192.168.0.218:/home/alphons/drupal/CONTRIB_WORKBENCH/pause-orphaned-ddev.sh
ssh alphons@192.168.0.218 'chmod +x /home/alphons/drupal/CONTRIB_WORKBENCH/pause-orphaned-ddev.sh'
rm /tmp/pause-orphaned-ddev.sh
```

- [ ] **Step 2: Syntax check + total line count**

Run:
```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && bash -n pause-orphaned-ddev.sh && wc -l pause-orphaned-ddev.sh'
```
Expected: no syntax error output, line count ~95.

---

### Task 6: Dry-run test (acceptance criterion 7)

**Files:** None (execution + verification only)

- [ ] **Step 1: Confirm baseline — 6 running stacks, `ai-3508503` orphan**

Run:
```bash
ssh alphons@192.168.0.218 'ddev list -j 2>/dev/null | jq -r ".raw[] | select(.status==\"running\") | .name"'
ssh alphons@192.168.0.218 'tmux ls | cut -d: -f1'
```
Expected: 6 running stacks, tmux sessions that do NOT include `drupal-issue-2zis`, `drupal-issue-e15u`, or `drupal-issue-jof3` (the three recorded for `ai-3508503`).

- [ ] **Step 2: Run dry-run**

Run:
```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && ./pause-orphaned-ddev.sh --dry-run'
```
Expected:
- Exactly one `DRY   ai-3508503 ...` line
- Five `keep  <stack> (nid <nid>, live tmux session)` lines for `ai-3580690`, `d3560681`, `d3577173`, `d3581952`, `d3582345`
- Zero `skip` lines
- Final line: `[dry-run] 1 would be paused, 5 kept, 0 skipped`

- [ ] **Step 3: Verify `ai-3508503` is STILL running (dry-run did not actually pause)**

Run:
```bash
ssh alphons@192.168.0.218 'ddev list -j 2>/dev/null | jq -r ".raw[] | select(.name==\"ai-3508503\") | .status"'
```
Expected: `running`.

**Acceptance criterion 7 passes** when Step 2 emits `DRY ai-3508503` and Step 3 reports `running`.

---

### Task 7: Default pause test (acceptance criteria 1, 2, 5)

**Files:** None (execution + verification only)

- [ ] **Step 1: Record tui.json mtime before pause run**

Run:
```bash
ssh alphons@192.168.0.218 'stat -c %Y /home/alphons/drupal/CONTRIB_WORKBENCH/tui.json' > /tmp/tui-mtime-before.txt
cat /tmp/tui-mtime-before.txt
```
Expected: epoch timestamp. Remember this.

- [ ] **Step 2: Run default pause mode**

Run:
```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && ./pause-orphaned-ddev.sh'
```
Expected:
- Exactly one `PAUSE ai-3508503 ...` line
- Five `keep  <stack>` lines for the other five stacks
- Zero `skip` lines
- Final line: `1 paused, 5 kept, 0 skipped`

- [ ] **Step 3: Verify `ai-3508503` is now paused (acceptance criterion 2)**

Run:
```bash
ssh alphons@192.168.0.218 'ddev list -j 2>/dev/null | jq -r ".raw[] | select(.name==\"ai-3508503\") | .status"'
```
Expected: `paused`.

- [ ] **Step 4: Verify the other 5 stacks are STILL running (acceptance criterion 1)**

Run:
```bash
ssh alphons@192.168.0.218 'ddev list -j 2>/dev/null | jq -r ".raw[] | select(.status==\"running\") | .name" | sort'
```
Expected: 5 lines — `ai-3580690`, `d3560681`, `d3577173`, `d3581952`, `d3582345` — in sorted order.

- [ ] **Step 5: Verify tui.json mtime unchanged (acceptance criterion 5)**

Run:
```bash
ssh alphons@192.168.0.218 'stat -c %Y /home/alphons/drupal/CONTRIB_WORKBENCH/tui.json' > /tmp/tui-mtime-after.txt
diff /tmp/tui-mtime-before.txt /tmp/tui-mtime-after.txt && echo "MTIME UNCHANGED" || echo "MTIME CHANGED — BUG"
rm /tmp/tui-mtime-before.txt /tmp/tui-mtime-after.txt
```
Expected: `MTIME UNCHANGED`.

**Acceptance criteria 1, 2, and 5 pass** when all three verification commands confirm.

---

### Task 8: Idempotency test (acceptance criterion 3)

**Files:** None (execution + verification only)

- [ ] **Step 1: Re-run default pause mode**

Run:
```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && ./pause-orphaned-ddev.sh'
```
Expected:
- Zero `PAUSE` lines (`ai-3508503` is no longer in the running set, so it's not considered)
- Five `keep` lines for the remaining running stacks
- Zero `skip` lines
- Final line: `0 paused, 5 kept, 0 skipped`

**Acceptance criterion 3 passes.**

---

### Task 9: Missing-ddev_name skip test (acceptance criterion 4)

**Files:** None (tui.json is temporarily mutated, then restored)

- [ ] **Step 1: Unpause `ai-3508503` back to running (so we can re-test the orphan path)**

Run:
```bash
ssh alphons@192.168.0.218 'ddev start ai-3508503'
```
Expected: `ai-3508503` status becomes `running` again.

- [ ] **Step 2: Back up tui.json and remove `ddev_name` from the `ai-3508503` entry**

Run:
```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && cp tui.json tui.json.bak && jq "del(.[\"3508503\"].ddev_name)" tui.json > /tmp/t.json && mv /tmp/t.json tui.json && jq ".[\"3508503\"].ddev_name" tui.json'
```
Expected: `null` (the field is now removed).

- [ ] **Step 3: Run default pause mode and expect a skip line for `ai-3508503`**

Run:
```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && ./pause-orphaned-ddev.sh'
```
Expected:
- Exactly one `skip  ai-3508503 (no tui.json ddev_name registered — run \`./pause-orphaned-ddev.sh register\` to backfill)` line
- Five `keep` lines for the other stacks
- Zero `PAUSE` lines
- Final line: `0 paused, 5 kept, 1 skipped`

- [ ] **Step 4: Verify `ai-3508503` is STILL running (skip did not pause it)**

Run:
```bash
ssh alphons@192.168.0.218 'ddev list -j 2>/dev/null | jq -r ".raw[] | select(.name==\"ai-3508503\") | .status"'
```
Expected: `running`.

- [ ] **Step 5: Restore tui.json and re-pause the orphan for baseline**

Run:
```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && mv tui.json.bak tui.json && jq ".[\"3508503\"].ddev_name" tui.json'
```
Expected: `"ai-3508503"` (restored).

Then re-pause `ai-3508503` to leave the workbench in the clean post-tests state:

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && ./pause-orphaned-ddev.sh'
```
Expected: `PAUSE ai-3508503` (because it's running AND has a live ddev_name entry AND no live tmux session).

**Acceptance criterion 4 passes.**

---

## Phase D — Agent hook

### Task 10: Add Phase 1.5 subsection to `drupal-ddev-setup.md`

**Files:**
- Modify: `.claude/agents/drupal-ddev-setup.md` (insert after the `ddev start` line in Phase 1)

- [ ] **Step 1: Read the current Phase 1 block to locate exact insertion point**

Run:
```bash
ssh alphons@192.168.0.218 'sed -n "45,70p" /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/agents/drupal-ddev-setup.md'
```
Expected: see lines around the `ddev config` + `ddev start` commands. Note the exact closing of the Phase 1 code block.

- [ ] **Step 2: Insert the new subsection via python replacement**

The insertion point is: immediately after the closing ``` of Phase 1's bash block, before `### Phase 2`. Use python to do the replacement safely:

```bash
python3 <<'PY'
import subprocess
path = "/home/alphons/drupal/CONTRIB_WORKBENCH/.claude/agents/drupal-ddev-setup.md"
content = subprocess.check_output(["ssh", "alphons@192.168.0.218", f"cat {path}"], text=True)

# Locate the end of Phase 1's bash block. Phase 1 contains: ddev config ..., ddev start, ddev composer create.
# We insert Phase 1.5 right after Phase 1's closing ``` and before "### Phase 2".
anchor = "### Phase 2: Discover Dependencies (BEFORE composer require)"
assert anchor in content, "could not find Phase 2 anchor"

new_section = """### Phase 1.5: Register DDEV project in tui.json

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
  if jq --arg k "{issue_id}" --arg n "$DDEV_NAME" \\
       '.[$k] //= {} | .[$k].ddev_name = $n' "$TUI" > "$tmp"; then
    mv "$tmp" "$TUI"
    echo "registered tui.json[{issue_id}].ddev_name = $DDEV_NAME"
  else
    rm -f "$tmp"
    echo "warn: failed to register ddev_name in tui.json (continuing)" >&2
  fi
fi
```

"""

updated = content.replace(anchor, new_section + anchor)
assert updated != content, "insertion did not change the file"

with open("/tmp/drupal-ddev-setup-updated.md", "w") as f:
    f.write(updated)

subprocess.check_call(["scp", "-q", "/tmp/drupal-ddev-setup-updated.md",
                       f"alphons@192.168.0.218:{path}"])
subprocess.check_call(["rm", "/tmp/drupal-ddev-setup-updated.md"])
print("inserted Phase 1.5 into drupal-ddev-setup.md")
PY
```

- [ ] **Step 3: Verify the insertion**

Run:
```bash
ssh alphons@192.168.0.218 'grep -n "Phase 1.5" /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/agents/drupal-ddev-setup.md'
ssh alphons@192.168.0.218 'sed -n "/Phase 1.5/,/Phase 2/p" /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/agents/drupal-ddev-setup.md | head -30'
```
Expected: `Phase 1.5: Register DDEV project in tui.json` appears exactly once; the inserted block spans ~20 lines and ends just before `### Phase 2`.

- [ ] **Step 4: Verify the `{issue_id}` template placeholders are preserved (not expanded)**

Run:
```bash
ssh alphons@192.168.0.218 'grep -c "{issue_id}" /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/agents/drupal-ddev-setup.md'
```
Expected: count ≥ 5 (original `--project-name=d{issue_id}` plus the new jq + echo references). The braces must be literal, not substituted.

**Acceptance criterion 8 is wiring-verified by this task** (runtime verification deferred to first real issue setup).

---

## Phase E — Documentation & ticket closure

### Task 11: Add "Orphaned DDEV cleanup" subsection to `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md` (workbench root)

- [ ] **Step 1: Find an anchor to insert near**

Run:
```bash
ssh alphons@192.168.0.218 'grep -n "^## " /home/alphons/drupal/CONTRIB_WORKBENCH/CLAUDE.md | head -30'
```
Expected: list of top-level headings. We want to insert the new subsection near an existing tooling area (likely near "Git & SSH", "Solution Depth Gate", or similar).

- [ ] **Step 2: Pick the insertion anchor**

Choose a natural home. A reasonable place is right after the "Solution Depth Gate" section ended in ticket 030, or directly before "Git & SSH". Verify exact heading text:

```bash
ssh alphons@192.168.0.218 'grep -n -E "(Solution Depth Gate|Git & SSH|Workflow state files)" /home/alphons/drupal/CONTRIB_WORKBENCH/CLAUDE.md'
```

- [ ] **Step 3: Insert the new subsection via python replacement**

Use python to insert before the chosen anchor heading. The exact anchor depends on Step 2's output, but the pattern is:

```bash
python3 <<'PY'
import subprocess
path = "/home/alphons/drupal/CONTRIB_WORKBENCH/CLAUDE.md"
content = subprocess.check_output(["ssh", "alphons@192.168.0.218", f"cat {path}"], text=True)

# Anchor: insert before "## Git & SSH" (adjust if that heading doesn't exist; use the next section after the DDG/workflow-state-files area)
anchor = "## Git & SSH"
assert anchor in content, f"anchor {anchor!r} not found — check the grep in Step 2 and update"

new_section = """## Orphaned DDEV cleanup

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
any stack that has no live session. `tui.json` is NOT modified in default
mode (only in `register` mode).

Pre-ticket-032 stacks need a one-time `register` run to populate their
`ddev_name` field. After that, every new issue setup registers itself
automatically.

See `docs/tui-json-schema.md` for the tui.json schema reference.

"""

updated = content.replace(anchor, new_section + anchor)
assert updated != content

with open("/tmp/claude-md-updated.md", "w") as f:
    f.write(updated)
subprocess.check_call(["scp", "-q", "/tmp/claude-md-updated.md",
                       f"alphons@192.168.0.218:{path}"])
subprocess.check_call(["rm", "/tmp/claude-md-updated.md"])
print("inserted Orphaned DDEV cleanup into CLAUDE.md")
PY
```

- [ ] **Step 4: Verify insertion**

Run:
```bash
ssh alphons@192.168.0.218 'grep -n "Orphaned DDEV cleanup" /home/alphons/drupal/CONTRIB_WORKBENCH/CLAUDE.md'
```
Expected: exactly one match.

---

### Task 12: Status flip + Resolution note for ticket 032

**Files:**
- Modify: `docs/tickets/032-ddev-auto-pause-orphaned.md`
- Modify: `docs/tickets/00-INDEX.md`

- [ ] **Step 1: Flip `032` status in `00-INDEX.md` from NOT_STARTED to COMPLETED**

Run:
```bash
python3 <<'PY'
import subprocess
path = "/home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/00-INDEX.md"
content = subprocess.check_output(["ssh", "alphons@192.168.0.218", f"cat {path}"], text=True)
# Find the 032 row and flip NOT_STARTED -> COMPLETED
old = "| 032 | DDEV auto-pause for orphaned stacks                        | P2 | NOT_STARTED | Tooling      | —          |"
new = "| 032 | DDEV auto-pause for orphaned stacks                        | P2 | COMPLETED   | Tooling      | —          |"
assert old in content, "032 row not found — inspect the index manually"
updated = content.replace(old, new, 1)
with open("/tmp/index-updated.md", "w") as f:
    f.write(updated)
subprocess.check_call(["scp", "-q", "/tmp/index-updated.md", f"alphons@192.168.0.218:{path}"])
subprocess.check_call(["rm", "/tmp/index-updated.md"])
print("032 status flipped in 00-INDEX.md")
PY
```

- [ ] **Step 2: Append Resolution note to `032-ddev-auto-pause-orphaned.md`**

Run:
```bash
ssh alphons@192.168.0.218 'cat >> /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/032-ddev-auto-pause-orphaned.md' <<'EOF'

## Resolution (2026-04-10)

Ticket 032 shipped with Option R (tui.json as authoritative ledger) instead
of the draft's name-parsing approach. All 8 acceptance criteria pass
(criterion 8 is wiring-verified only — runtime verification deferred to
first real issue setup after the ticket lands).

### What shipped

**Phase A — Foundation:**
- New `docs/tui-json-schema.md` formalizing tui.json's shape including the
  new optional `ddev_name` field.
- `pause-orphaned-ddev.sh` skeleton at workbench root with USAGE block,
  `--dry-run` flag, `register` subcommand, and `set -euo pipefail`.

**Phase B — `register` mode:**
- One-shot backfill subcommand that iterates `ddev list -j`, extracts nid
  from each stack's `approot` via `grep -oE 'DRUPAL_ISSUES/[0-9]+'`, and
  writes `ddev_name` into the matching `tui.json` entry if unset.
- Run against live state: registered 6 mappings in one pass. Idempotent
  on re-run (`0 new mappings`).

**Phase C — Default pause mode:**
- Two-pass loop: Pass 1 iterates registered entries and decides pause/keep
  per tmux liveness; Pass 2 reports any running stack whose name has no
  registered `ddev_name` as `skip`.
- `--dry-run` prefixes `DRY` on would-pause lines and never calls
  `ddev pause`.
- Default mode makes zero writes to tui.json (verified via `stat -c %Y`
  before/after, mtime unchanged).

**Phase D — Agent hook:**
- `drupal-ddev-setup.md` gained Phase 1.5 subsection immediately after
  `ddev start`. Writes `tui.json[{issue_id}].ddev_name = "d{issue_id}"`
  via `jq` with temp-file + `mv`. Best-effort: warn + continue on failure.

**Phase E — Documentation:**
- `CLAUDE.md` gained "Orphaned DDEV cleanup" subsection.
- `docs/tui-json-schema.md` created (new canonical reference).
- Phase 2 Integrated Snapshot refreshed across tickets 027-032.

### Acceptance results

| # | Requirement | Result |
|---|---|---|
| 1 | Pause `ai-3508503`, leave other 5 running stacks alone | PASS — 1 PAUSE, 5 keeps |
| 2 | `ddev list` shows `ai-3508503` as `paused` after run | PASS |
| 3 | Re-run is idempotent (already-paused skipped) | PASS — 0 paused, 5 kept |
| 4 | Missing `ddev_name` produces skip line, doesn't pause | PASS — skip message emitted, stack stayed running |
| 5 | Default mode does not modify tui.json (mtime unchanged) | PASS |
| 6 | `register` backfills all running stacks in one pass | PASS — 6 new mappings, idempotent |
| 7 | `--dry-run` previews without pausing | PASS — DRY prefix, stack stayed running |
| 8 | Agent hook populates `ddev_name` on new setup | WIRING — runtime deferred |

### Design decisions locked in

1. **tui.json as authoritative ledger.** Replaces the draft's name-parsing
   regex. Robust to any future project prefix. User-approved during
   brainstorming as Option R.
2. **Default mode is read-only.** All writes flow through the explicit
   `register` subcommand or the setup agent hook. Makes "mtime unchanged"
   easy to verify and reason about.
3. **`register` uses path-based nid extraction, not name parsing.** Uses
   `DRUPAL_ISSUES/<nid>/` structural invariant — same invariant used
   throughout the workbench.
4. **Agent hook is best-effort.** jq failure or missing tui.json does not
   abort stack setup; backfill via `register` remains available.
5. **No unit tests.** Bash script with straightforward control flow;
   live acceptance tests cover all paths.

### Gotchas

- When testing acceptance criterion 9 (synthetic missing-ddev_name skip),
  we temporarily `jq del` the field from one entry, run the script, then
  restore from backup. This is a one-off test flow, not a normal op.
- `grep -qFx` is used for all containment checks (stack names, session
  names) to avoid regex metacharacter pitfalls.
EOF
```

- [ ] **Step 3: Verify the Resolution note is present**

Run:
```bash
ssh alphons@192.168.0.218 'grep -c "^## Resolution" /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/032-ddev-auto-pause-orphaned.md'
```
Expected: `1`.

---

### Task 13: Refresh Phase 2 Integrated Snapshot across tickets 027-032

**Files:**
- Modify: `docs/tickets/027-fix-stale-session-dir.md`
- Modify: `docs/tickets/028-adopt-bd-data-store.md`
- Modify: `docs/tickets/029-cross-issue-resonance.md`
- Modify: `docs/tickets/030-solution-depth-gate.md`
- Modify: `docs/tickets/031-workflow-determinism-sentinel.md`
- Modify: `docs/tickets/032-ddev-auto-pause-orphaned.md`

- [ ] **Step 1: Read the current snapshot from one of the tickets (authoritative source)**

Run:
```bash
ssh alphons@192.168.0.218 'sed -n "/^## Phase 2 Integrated Snapshot/,/^### Phase 2 tickets NOT YET started/p" /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/031-workflow-determinism-sentinel.md' > /tmp/snapshot-current.md
wc -l /tmp/snapshot-current.md
```
Expected: ~260-310 lines of current snapshot content (ticket 031 version).

- [ ] **Step 2: Update the snapshot content with 032 additions**

Build the updated snapshot locally in `/tmp/snapshot-new.md`:

```bash
python3 <<'PY'
import re
with open("/tmp/snapshot-current.md") as f:
    s = f.read()

# 1. Update header date
s = s.replace("(as of 2026-04-09)", "(as of 2026-04-10)")

# 2. Update the "mirrored across" line to include 032
s = s.replace(
    "This section is mirrored across all COMPLETED phase-2 tickets (027, 028,\n029, 030, 031)",
    "This section is mirrored across all COMPLETED phase-2 tickets (027, 028,\n029, 030, 031, 032)")
# Also handle the version that might be on one line
s = s.replace(
    "COMPLETED phase-2 tickets (027, 028, 029, 030, 031)",
    "COMPLETED phase-2 tickets (027, 028, 029, 030, 031, 032)")

# 3. Add 032 row to the completed-tickets table
completed_032_row = "| 032 | DDEV auto-pause for orphaned stacks | `pause-orphaned-ddev.sh` at workbench root. Option R: tui.json as ledger (`ddev_name` field), setup agent writes on creation, `register` subcommand backfills existing stacks. Default mode read-only. Includes `--dry-run`. |"
# Insert after the 031 row
old_031_row_pattern = re.compile(r"(\| 031 \| Workflow determinism via sentinel \+ reinstate \|[^\n]+\n)")
if old_031_row_pattern.search(s):
    s = old_031_row_pattern.sub(lambda m: m.group(1) + completed_032_row + "\n", s, count=1)
else:
    print("WARN: could not find 031 row in completed tickets table")

# 4. Update the integration diagram title count
s = s.replace("How the five tickets integrate", "How the six tickets integrate")

# 5. Add 032 gotcha section
new_gotchas = """
13. **tui.json has two writers now** (from 032). The launcher writes `title`/`fileCwd`/`actions`/`sessions` on every invocation; the `drupal-ddev-setup` agent writes `ddev_name` after `ddev start` succeeds. Both use read+write with `jq` temp-file + `mv`. No locking is needed because they are strictly sequential (launcher runs BEFORE spawning claude; agent runs INSIDE the spawned session). Launcher's jq preserves unknown fields so `ddev_name` is not clobbered on session resume. See `docs/tui-json-schema.md` for the canonical schema reference.

14. **`pause-orphaned-ddev.sh` default mode is strictly read-only** (from 032). Writes only happen in the explicit `register` subcommand. Verify with `stat -c %Y tui.json` before/after a default-mode run — mtime must be unchanged. If you find yourself wanting to auto-backfill from default mode, resist: the "default mode makes no tui.json writes" invariant is load-bearing for acceptance criterion 5.

15. **Path-based nid extraction uses `DRUPAL_ISSUES/<nid>/` invariant** (from 032). The `register` subcommand does NOT parse ddev stack names (no regex on `d|ai-?`). It uses `grep -oE 'DRUPAL_ISSUES/[0-9]+'` against each stack's `approot` from `ddev list -j`. This is robust to any future project prefix and matches how every other tool in the workbench joins against issues.
"""

# Insert new gotchas right before "### Where to look for detail"
anchor = "### Where to look for detail"
if anchor in s:
    s = s.replace(anchor, new_gotchas + "\n" + anchor, 1)
else:
    print("WARN: could not find 'Where to look for detail' anchor")

# 6. Add doc reference row for tui-json-schema and pause-orphaned-ddev
doc_rows_new = """| tui.json schema reference | `docs/tui-json-schema.md` |
| Orphaned DDEV cleanup script | `pause-orphaned-ddev.sh` (workbench root) |
| Orphaned DDEV cleanup docs | `CLAUDE.md` → "Orphaned DDEV cleanup" section |
"""
# Insert before the closing of the reference table
# Find the last row of the table and insert after it
old_tail = "| Launcher internals | `drupal-issue.sh` |"
if old_tail in s:
    s = s.replace(old_tail, old_tail + "\n" + doc_rows_new.rstrip(), 1)

# 7. Add 032 to "What's live in the workbench that wasn't before phase 2"
live_032 = """- **Orphaned DDEV stacks get paused cleanly.** `./pause-orphaned-ddev.sh` reads `tui.json[<nid>].ddev_name` (populated by the setup agent on every new stack and backfilled by the `register` subcommand for pre-032 stacks), checks each stack's recorded tmux sessions against live `tmux ls`, and pauses any whose sessions are dead. Default mode is read-only; `register` is the only write path. Includes `--dry-run`. (032)
"""
# Insert after the 031 bullet in the "What's live" section
anchor_031 = "- **Launcher pre-creates a classification sentinel"
if anchor_031 in s:
    # find the end of that bullet (next blank line or next `- **`)
    idx = s.find(anchor_031)
    # find end of paragraph (next blank line)
    end_idx = s.find("\n\n", idx)
    if end_idx != -1:
        s = s[:end_idx + 2] + live_032 + s[end_idx + 2:]
    else:
        print("WARN: could not find end of 031 what's live bullet")

# 8. Remove 032 from "Phase 2 tickets NOT YET started" table
old_032_pending = re.compile(r"\| 032 \| DDEV auto-pause for orphaned stacks[^\n]+\n")
s = old_032_pending.sub("", s)

with open("/tmp/snapshot-new.md", "w") as f:
    f.write(s)

print(f"new snapshot: {len(s.splitlines())} lines")
PY
```

- [ ] **Step 3: Sanity check the new snapshot**

Run:
```bash
wc -l /tmp/snapshot-new.md
grep -c "032" /tmp/snapshot-new.md
grep -c "Workflow determinism via sentinel" /tmp/snapshot-new.md
grep -c "DDEV auto-pause" /tmp/snapshot-new.md
```
Expected:
- Line count: ~315-330 (snapshot is over the 300-line guidance but marginal; acceptable given the spec note "if it grows, split the 'critical gotchas' into a separate standing reference doc — that's a future cleanup if the snapshot grows materially past ~350 lines)
- `032` appears multiple times
- `Workflow determinism via sentinel` appears exactly once (the 031 row, not duplicated)
- `DDEV auto-pause` appears 1-2 times (in the table + maybe in the what's live bullet)

- [ ] **Step 4: Apply the new snapshot to all 6 tickets (replacing the existing snapshot in 027-031, appending to 032)**

```bash
python3 <<'PY'
import subprocess
import re

with open("/tmp/snapshot-new.md") as f:
    new_snap = f.read()

tickets = [
    "027-fix-stale-session-dir.md",
    "028-adopt-bd-data-store.md",
    "029-cross-issue-resonance.md",
    "030-solution-depth-gate.md",
    "031-workflow-determinism-sentinel.md",
]

for t in tickets:
    path = f"/home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/{t}"
    content = subprocess.check_output(["ssh", "alphons@192.168.0.218", f"cat {path}"], text=True)
    # Replace the entire snapshot block
    pat = re.compile(r"## Phase 2 Integrated Snapshot.*?(?=\n## |\Z)", re.DOTALL)
    m = pat.search(content)
    assert m, f"no snapshot block found in {t}"
    updated = pat.sub(new_snap.rstrip() + "\n\n", content)
    with open("/tmp/out.md", "w") as f:
        f.write(updated)
    subprocess.check_call(["scp", "-q", "/tmp/out.md", f"alphons@192.168.0.218:{path}"])
    print(f"snapshot replaced in {t}")

# 032 — append fresh (no existing snapshot)
path_032 = "/home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/032-ddev-auto-pause-orphaned.md"
content_032 = subprocess.check_output(["ssh", "alphons@192.168.0.218", f"cat {path_032}"], text=True)
if "## Phase 2 Integrated Snapshot" in content_032:
    # Replace existing
    pat = re.compile(r"## Phase 2 Integrated Snapshot.*?(?=\n## |\Z)", re.DOTALL)
    updated_032 = pat.sub(new_snap.rstrip() + "\n\n", content_032)
else:
    # Append
    updated_032 = content_032.rstrip() + "\n\n" + new_snap
with open("/tmp/out.md", "w") as f:
    f.write(updated_032)
subprocess.check_call(["scp", "-q", "/tmp/out.md", f"alphons@192.168.0.218:{path_032}"])
print("snapshot applied to 032")

subprocess.check_call(["rm", "/tmp/out.md"])
PY
```

- [ ] **Step 5: Verify each ticket has exactly one snapshot with 032 in it**

Run:
```bash
for t in 027-fix-stale-session-dir 028-adopt-bd-data-store 029-cross-issue-resonance 030-solution-depth-gate 031-workflow-determinism-sentinel 032-ddev-auto-pause-orphaned; do
  ssh alphons@192.168.0.218 "echo -n '$t: snapshot='; grep -c 'Phase 2 Integrated Snapshot' /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/$t.md; echo -n '$t: 032-row='; grep -c 'DDEV auto-pause for orphaned stacks' /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/$t.md"
done
```
Expected for each ticket:
- `snapshot=1` (exactly one snapshot section)
- `032-row` ≥ 1 (032's row in the completed tickets table, possibly also in the what's live bullet)

- [ ] **Step 6: Clean up tmp files**

```bash
rm /tmp/snapshot-current.md /tmp/snapshot-new.md
```

---

### Task 14: Final cleanup and state verification

**Files:** None (verification only)

- [ ] **Step 1: Verify `ai-3508503` is paused (baseline leave-behind)**

Run:
```bash
ssh alphons@192.168.0.218 'ddev list -j 2>/dev/null | jq -r ".raw[] | select(.name==\"ai-3508503\") | .status"'
```
Expected: `paused` (leave as-is; this is the real orphan).

- [ ] **Step 2: Verify no stray temp files on remote**

Run:
```bash
ssh alphons@192.168.0.218 'ls /tmp/tui*.json /tmp/snapshot*.md /tmp/out.md /tmp/index-updated.md /tmp/claude-md-updated.md /tmp/drupal-ddev-setup-updated.md /tmp/pause-orphaned-ddev.sh /tmp/tui-pre-032.json 2>/dev/null; echo "---check done---"'
```
Expected: `---check done---` alone (no stray files). If any remain, remove them manually.

- [ ] **Step 3: Verify the list of changed/new files is what we expect**

Run:
```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && git status --short 2>/dev/null | head -40'
```
Expected: new + modified files include at minimum:
- `pause-orphaned-ddev.sh` (new)
- `docs/tui-json-schema.md` (new)
- `.claude/agents/drupal-ddev-setup.md` (modified)
- `CLAUDE.md` (modified)
- `docs/tickets/00-INDEX.md` (modified)
- `docs/tickets/027-fix-stale-session-dir.md` (modified)
- `docs/tickets/028-adopt-bd-data-store.md` (modified)
- `docs/tickets/029-cross-issue-resonance.md` (modified)
- `docs/tickets/030-solution-depth-gate.md` (modified)
- `docs/tickets/031-workflow-determinism-sentinel.md` (modified)
- `docs/tickets/032-ddev-auto-pause-orphaned.md` (modified)
- `tui.json` (modified — by the `register` run in Task 4; this is expected, not a bug)

Plus whatever uncommitted pile already existed from previous tickets.

- [ ] **Step 4: Final summary for user review**

Print a summary block:

```
Ticket 032 implementation complete.

Files created: 2
  - pause-orphaned-ddev.sh
  - docs/tui-json-schema.md

Files modified: 9
  - .claude/agents/drupal-ddev-setup.md
  - CLAUDE.md
  - docs/tickets/00-INDEX.md
  - docs/tickets/032-ddev-auto-pause-orphaned.md (+Resolution)
  - docs/tickets/{027,028,029,030,031}-*.md (snapshot refresh)
  - tui.json (backfilled via `./pause-orphaned-ddev.sh register` — expected side-effect)

Acceptance: 8/8 pass (criterion 8 wiring-verified only).

Live state after:
  - ai-3508503: paused (was orphan)
  - 5 other running stacks: unchanged
  - tui.json has 6 ddev_name entries

NO GIT COMMITS made per session-wide user rule.
```

---

## Self-review summary

**Spec coverage:**
- All 5 original ticket acceptance criteria → Tasks 7-9
- 3 spec-added criteria (register, dry-run, agent hook) → Tasks 4, 6, 10
- File inventory matches spec (2 created, 9+ modified)

**Placeholder scan:** none remaining.

**Type consistency:** `ddev_name` field, `{issue_id}` template, `DRUPAL_ISSUES/<nid>/` invariant used consistently across tasks.

**Execution handoff:** Inline per user's session-wide rule ("inline with good context"), skip all git commits.
