#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAP_FILE="$SCRIPT_DIR/DRUPAL_ISSUES/session-map.json"
SESSION_DIR="$HOME/.claude/projects/-home-alphons-project-freelygive-drupal-CONTRIB-WORKBENCH"

# --- Dependency check ---
for cmd in jq uuidgen claude; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "Error: '$cmd' is required but not found in PATH." >&2
    exit 1
  fi
done

# --- Argument validation ---
if [[ $# -lt 1 ]]; then
  echo "Usage: drupal-issue.sh <issue_id_or_url> [objective]" >&2
  echo "" >&2
  echo "Examples:" >&2
  echo "  ./drupal-issue.sh 3579079" >&2
  echo "  ./drupal-issue.sh 3579079 \"address review comments\"" >&2
  echo "  ./drupal-issue.sh https://www.drupal.org/project/ai/issues/3579079" >&2
  echo "  ./drupal-issue.sh https://www.drupal.org/i/3579079 \"rebase and fix\"" >&2
  exit 1
fi

INPUT="$1"
OBJECTIVE="${2:-}"

# --- Extract numeric issue ID ---
if [[ "$INPUT" =~ ^[0-9]+$ ]]; then
  ISSUE_ID="$INPUT"
elif [[ "$INPUT" =~ drupal\.org/i/([0-9]+) ]]; then
  ISSUE_ID="${BASH_REMATCH[1]}"
elif [[ "$INPUT" =~ drupal\.org/project/[^/]+/issues/([0-9]+) ]]; then
  ISSUE_ID="${BASH_REMATCH[1]}"
else
  echo "Error: Could not extract issue ID from '$INPUT'" >&2
  echo "Expected a numeric ID or a drupal.org issue URL." >&2
  exit 1
fi

# --- Ensure session map exists ---
if [[ ! -f "$MAP_FILE" ]]; then
  mkdir -p "$(dirname "$MAP_FILE")"
  echo '{}' > "$MAP_FILE"
fi

# --- Look up existing session ---
SESSION_ID=$(jq -r --arg id "$ISSUE_ID" '.[$id].session_id // empty' "$MAP_FILE")

# --- Functions ---

write_tui_json() {
  local tmux_name issue_id issue_dir tui_file
  tmux_name=$(tmux display-message -p "#{session_name}" 2>/dev/null || echo "")
  [[ -z "$tmux_name" ]] && return 0

  issue_id="$1"
  issue_dir="$SCRIPT_DIR/DRUPAL_ISSUES/$issue_id"
  tui_file="$SCRIPT_DIR/tui.json"

  # Read existing or start fresh
  local tui_data
  [[ -f "$tui_file" ]] && tui_data=$(cat "$tui_file") || tui_data="{}"

  # Upsert entry: set title, fileCwd, default action, append session name
  tui_data=$(echo "$tui_data" | jq \
    --arg key "$issue_id" \
    --arg title "D.O ISSUE: $issue_id" \
    --arg cwd "$issue_dir" \
    --arg url "https://www.drupal.org/i/$issue_id" \
    --arg sess "$tmux_name" \
    '
    .[$key] //= {} |
    .[$key].title = $title |
    .[$key].fileCwd = $cwd |
    .[$key].actions //= [{"id":"issue-page","label":"Issue","icon":"drupal","type":"url","url":$url}] |
    .[$key].sessions = ((.[$key].sessions // []) + [$sess] | unique)
    ')
  echo "$tui_data" > "$tui_file"
}

launch_new_session() {
  local uuid
  uuid=$(uuidgen)

  local prompt="/drupal-issue https://www.drupal.org/i/$ISSUE_ID"
  if [[ -n "$OBJECTIVE" ]]; then
    prompt="$prompt $OBJECTIVE"
  fi

  # Write mapping before launch
  local timestamp
  timestamp=$(date -Iseconds)
  local updated
  updated=$(jq --arg id "$ISSUE_ID" \
               --arg sid "$uuid" \
               --arg ts "$timestamp" \
               --arg url "https://www.drupal.org/i/$ISSUE_ID" \
               '.[$id] = {"session_id": $sid, "last_accessed": $ts, "url": $url}' \
               "$MAP_FILE")
  echo "$updated" > "$MAP_FILE"

  clear
  echo "Starting new session for issue #$ISSUE_ID (session: $uuid)"
  write_tui_json "$ISSUE_ID"
  exec claude --allow-dangerously-skip-permissions --permission-mode bypassPermissions --session-id "$uuid" --name "issue-$ISSUE_ID" "$prompt"
}

resume_session() {
  # Update last_accessed
  local timestamp
  timestamp=$(date -Iseconds)
  local updated
  updated=$(jq --arg id "$ISSUE_ID" --arg ts "$timestamp" \
               '.[$id].last_accessed = $ts' "$MAP_FILE")
  echo "$updated" > "$MAP_FILE"

  local prompt="Refresh issue #$ISSUE_ID: use the drupal-issue-fetcher agent to pull latest comments and MR status into DRUPAL_ISSUES/$ISSUE_ID/artifacts/, summarize what changed since our last session."
  if [[ -n "$OBJECTIVE" ]]; then
    prompt="$prompt Then: $OBJECTIVE"
  fi

  clear
  echo "Resuming session for issue #$ISSUE_ID (session: $SESSION_ID)"
  write_tui_json "$ISSUE_ID"
  exec claude --allow-dangerously-skip-permissions --permission-mode bypassPermissions --resume "$SESSION_ID" --name "issue-$ISSUE_ID" "$prompt"
}

remove_stale_session() {
  echo "Previous session $SESSION_ID no longer exists on disk. Starting fresh."
  local updated
  updated=$(jq --arg id "$ISSUE_ID" 'del(.[$id])' "$MAP_FILE")
  echo "$updated" > "$MAP_FILE"
  SESSION_ID=""
}

# --- Route: resume or new ---
if [[ -n "$SESSION_ID" ]]; then
  if [[ -f "$SESSION_DIR/$SESSION_ID.jsonl" ]]; then
    resume_session
  else
    remove_stale_session
    launch_new_session
  fi
else
  launch_new_session
fi
