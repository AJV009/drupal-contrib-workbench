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

# ============================================================================
# register mode: one-shot backfill of tui.json[<nid>].ddev_name
# Iterates ALL stacks (running + paused), not just running, so paused stacks
# get their mapping populated too (useful if they're later resumed and orphaned).
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

# running ddev stacks only (we never pause already-paused stacks)
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
  if [[ -z "$sessions" ]]; then
    # No sessions ever recorded — stack was created outside launcher flow.
    # Can't verify liveness, so skip rather than pause (per original ticket intent).
    echo "skip  $name (nid $nid, no sessions recorded in tui.json — manual/external stack, leave alone)"
    skip_count=$((skip_count + 1))
    continue
  fi
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
      if ! ddev stop "$name"; then
        echo "  warn: ddev stop $name failed (continuing)" >&2
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
