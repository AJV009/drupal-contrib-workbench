# Drupal Issue Session Resume - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A shell wrapper script that gives Claude Code session continuity across drupal.org issue work, so returning to an issue resumes the prior conversation instead of starting from scratch.

**Architecture:** Single bash script (`drupal-issue.sh`) at workspace root manages a JSON mapping (`DRUPAL_ISSUES/session-map.json`) of issue IDs to Claude Code session UUIDs. New issues get a pre-generated UUID via `--session-id`; returning issues resume via `--resume`. Uses `exec` for clean process replacement.

**Tech Stack:** Bash, jq, uuidgen, Claude Code CLI

---

## File Structure

| File | Responsibility |
|------|---------------|
| `drupal-issue.sh` (create) | Wrapper script: argument parsing, session lookup, Claude Code launch |
| `DRUPAL_ISSUES/session-map.json` (create on first run) | Persistent mapping of issue ID to session UUID + metadata |

---

### Task 1: Create the script with argument parsing and URL extraction

**Files:**
- Create: `drupal-issue.sh`

- [ ] **Step 1: Write the script with argument validation and issue ID extraction**

```bash
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
# Handles:
#   3579079
#   https://www.drupal.org/i/3579079
#   https://drupal.org/i/3579079
#   https://www.drupal.org/project/ai/issues/3579079
#   https://drupal.org/project/ai/issues/3579079
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

echo "Issue #$ISSUE_ID"
```

- [ ] **Step 2: Test argument parsing manually**

Run each of these and verify the output says `Issue #3579079`:
```bash
chmod +x drupal-issue.sh
./drupal-issue.sh 3579079
./drupal-issue.sh https://www.drupal.org/i/3579079
./drupal-issue.sh https://drupal.org/i/3579079
./drupal-issue.sh https://www.drupal.org/project/ai/issues/3579079
./drupal-issue.sh https://drupal.org/project/ai/issues/3579079
```

Test error cases:
```bash
./drupal-issue.sh            # Should print usage
./drupal-issue.sh "not-a-url" # Should print extraction error
```

- [ ] **Step 3: Commit**

```bash
git add drupal-issue.sh
git commit -m "feat: add drupal-issue.sh with argument parsing and URL extraction"
```

---

### Task 2: Add session map read/write and new-session flow

**Files:**
- Modify: `drupal-issue.sh`

- [ ] **Step 1: Add session map initialization and lookup**

Append after the issue ID extraction block in `drupal-issue.sh`:

```bash
# --- Ensure session map exists ---
if [[ ! -f "$MAP_FILE" ]]; then
  mkdir -p "$(dirname "$MAP_FILE")"
  echo '{}' > "$MAP_FILE"
fi

# --- Look up existing session ---
SESSION_ID=$(jq -r --arg id "$ISSUE_ID" '.[$id].session_id // empty' "$MAP_FILE")
```

- [ ] **Step 2: Add the new-session launch function**

Append after the lookup block:

```bash
launch_new_session() {
  local uuid
  uuid=$(uuidgen)

  # Build the prompt
  local prompt="/drupal-issue https://www.drupal.org/i/$ISSUE_ID"
  if [[ -n "$OBJECTIVE" ]]; then
    prompt="$prompt $OBJECTIVE"
  fi

  # Write mapping before launch (we know the UUID)
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

  echo "Starting new session for issue #$ISSUE_ID (session: $uuid)"
  exec claude --session-id "$uuid" --name "issue-$ISSUE_ID" "$prompt"
}
```

- [ ] **Step 3: Add the routing logic at the bottom of the script**

```bash
# --- Route: resume or new ---
if [[ -z "$SESSION_ID" ]]; then
  launch_new_session
fi

# (Resume logic added in next task)
# For now, fall through to new session if we reach here
launch_new_session
```

- [ ] **Step 4: Test new-session flow**

```bash
# Use a test issue ID that won't conflict
./drupal-issue.sh 9999999
# Should print: "Starting new session for issue #9999999 (session: <uuid>)"
# and launch Claude Code interactively with the /drupal-issue prompt.
# Type /exit in Claude to quit.

# Verify session-map.json was written:
cat DRUPAL_ISSUES/session-map.json
# Should show entry for "9999999" with a session_id, last_accessed, and url.
```

- [ ] **Step 5: Commit**

```bash
git add drupal-issue.sh
git commit -m "feat: add session map management and new-session launch flow"
```

---

### Task 3: Add resume flow with session validation and stale cleanup

**Files:**
- Modify: `drupal-issue.sh`

- [ ] **Step 1: Add the resume function**

Insert before the `# --- Route: resume or new ---` section, replacing the routing logic:

```bash
resume_session() {
  # Update last_accessed timestamp
  local timestamp
  timestamp=$(date -Iseconds)
  local updated
  updated=$(jq --arg id "$ISSUE_ID" --arg ts "$timestamp" \
               '.[$id].last_accessed = $ts' "$MAP_FILE")
  echo "$updated" > "$MAP_FILE"

  # Build the resume prompt
  local prompt="Refresh issue #$ISSUE_ID: use the drupal-issue-fetcher agent to pull latest comments and MR status into DRUPAL_ISSUES/$ISSUE_ID/artifacts/, summarize what changed since our last session."
  if [[ -n "$OBJECTIVE" ]]; then
    prompt="$prompt Then: $OBJECTIVE"
  fi

  echo "Resuming session for issue #$ISSUE_ID (session: $SESSION_ID)"
  exec claude --resume "$SESSION_ID" --name "issue-$ISSUE_ID" "$prompt"
}

remove_stale_session() {
  echo "Previous session $SESSION_ID no longer exists on disk. Starting fresh."
  local updated
  updated=$(jq --arg id "$ISSUE_ID" 'del(.[$id])' "$MAP_FILE")
  echo "$updated" > "$MAP_FILE"
  SESSION_ID=""
}
```

- [ ] **Step 2: Replace the routing logic at the bottom**

Remove the temporary routing logic from Task 2 and replace with:

```bash
# --- Route: resume or new ---
if [[ -n "$SESSION_ID" ]]; then
  # Validate session file exists on disk
  if [[ -f "$SESSION_DIR/$SESSION_ID.jsonl" ]]; then
    resume_session
  else
    remove_stale_session
    launch_new_session
  fi
else
  launch_new_session
fi
```

- [ ] **Step 3: Test resume flow**

```bash
# First, check that session-map.json has the entry from Task 2 testing
cat DRUPAL_ISSUES/session-map.json

# Resume the session we created earlier (assuming 9999999 was used)
./drupal-issue.sh 9999999
# Should print: "Resuming session for issue #9999999 (session: <uuid>)"
# and launch Claude Code with --resume, showing the refresh prompt.
# Claude should have context from the previous session.
# Type /exit to quit.
```

- [ ] **Step 4: Test stale session cleanup**

```bash
# Manually corrupt the session-map to point to a non-existent session
jq '.["8888888"] = {"session_id": "00000000-0000-0000-0000-000000000000", "last_accessed": "2026-03-26T00:00:00+05:30", "url": "https://www.drupal.org/i/8888888"}' DRUPAL_ISSUES/session-map.json > /tmp/sm.json && mv /tmp/sm.json DRUPAL_ISSUES/session-map.json

./drupal-issue.sh 8888888
# Should print: "Previous session 00000000-... no longer exists on disk. Starting fresh."
# Then launch a new session.
# Type /exit to quit.

# Verify the stale entry was replaced with a fresh one:
cat DRUPAL_ISSUES/session-map.json
```

- [ ] **Step 5: Commit**

```bash
git add drupal-issue.sh
git commit -m "feat: add session resume with validation and stale session cleanup"
```

---

### Task 4: Clean up test data and final verification

**Files:**
- Modify: `DRUPAL_ISSUES/session-map.json` (clean test entries)

- [ ] **Step 1: Remove test entries from session-map.json**

```bash
jq 'del(.["9999999"]) | del(.["8888888"])' DRUPAL_ISSUES/session-map.json > /tmp/sm.json && mv /tmp/sm.json DRUPAL_ISSUES/session-map.json
cat DRUPAL_ISSUES/session-map.json
# Should be {} or only contain real issue entries
```

- [ ] **Step 2: End-to-end test with a real issue**

```bash
# New session for a real issue
./drupal-issue.sh 3579079
# Should create a new session, launch Claude with /drupal-issue prompt.
# Let the artifacts fetch, then /exit.

# Resume it
./drupal-issue.sh 3579079
# Should resume with full prior context, run the refresh prompt.
# /exit.

# Resume with an objective
./drupal-issue.sh 3579079 "check if there are new review comments to address"
# Should resume and include the objective in the prompt.
# /exit.
```

- [ ] **Step 3: Verify session-map.json state**

```bash
cat DRUPAL_ISSUES/session-map.json | jq .
# Should show the 3579079 entry with a valid session_id and recent last_accessed
```

- [ ] **Step 4: Commit**

```bash
git add DRUPAL_ISSUES/session-map.json
git commit -m "chore: clean up test entries from session map"
```

---

### Task 5: Add session-map.json to .gitignore

**Files:**
- Modify: `.gitignore` (or create if not present)

- [ ] **Step 1: Ensure session-map.json is not tracked in git**

The session map contains local session UUIDs that are machine-specific. Add to `.gitignore`:

```
DRUPAL_ISSUES/session-map.json
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore session-map.json (machine-specific session data)"
```
