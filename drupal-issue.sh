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
  echo "Usage: drupal-issue.sh <issue_id_or_url> [options]" >&2
  echo "" >&2
  echo "Options:" >&2
  echo "  --gate, -g                 Enable pre-work gate (pause after analysis, before fix)" >&2
  echo "  -i, --instructions \"...\"   Additional instructions for the AI session" >&2
  echo "" >&2
  echo "Examples:" >&2
  echo "  ./drupal-issue.sh 3579079" >&2
  echo "  ./drupal-issue.sh 3579079 --gate" >&2
  echo "  ./drupal-issue.sh 3579079 -i \"focus on the entity access bug only\"" >&2
  echo "  ./drupal-issue.sh 3579079 --gate -i \"use approach from comment #7\"" >&2
  echo "  ./drupal-issue.sh https://www.drupal.org/project/ai/issues/3579079" >&2
  echo "  ./drupal-issue.sh https://www.drupal.org/i/3579079 -i \"ignore JS warnings\"" >&2
  exit 1
fi

INPUT="$1"; shift
GATE=false
INSTRUCTIONS=""

# --- Parse optional flags ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --gate|-g)
      GATE=true; shift ;;
    -i|--instructions)
      if [[ $# -lt 2 ]]; then
        echo "Error: $1 requires a string argument." >&2
        exit 1
      fi
      INSTRUCTIONS="$2"; shift 2 ;;
    *)
      echo "Error: Unknown argument '$1'" >&2
      echo "Use --gate/-g or -i/--instructions \"...\"" >&2
      exit 1 ;;
  esac
done

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

build_prompt_prefix() {
  # Build the preamble that goes ABOVE the skill invocation
  local prefix=""
  if [[ -n "$INSTRUCTIONS" ]]; then
    prefix="ADDITIONAL INSTRUCTIONS (apply throughout this entire session, across all skill invocations and agent dispatches): $INSTRUCTIONS

"
  fi
  echo -n "$prefix"
}

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

  local prefix
  prefix=$(build_prompt_prefix)

  local skill_cmd="/drupal-issue https://www.drupal.org/i/$ISSUE_ID"
  if [[ "$GATE" == true ]]; then
    skill_cmd="$skill_cmd --pre-work-gate"
  fi

  local prompt="${prefix}${skill_cmd}"

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
  [[ "$GATE" == true ]] && echo "  Pre-work gate: ENABLED"
  [[ -n "$INSTRUCTIONS" ]] && echo "  Instructions: $INSTRUCTIONS"
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

  local prefix
  prefix=$(build_prompt_prefix)

  local prompt="${prefix}Refresh issue #$ISSUE_ID: use the drupal-issue-fetcher agent to pull latest comments and MR status into DRUPAL_ISSUES/$ISSUE_ID/artifacts/, summarize what changed since our last session."

  clear
  echo "Resuming session for issue #$ISSUE_ID (session: $SESSION_ID)"
  [[ -n "$INSTRUCTIONS" ]] && echo "  Instructions: $INSTRUCTIONS"
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
