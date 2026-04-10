#!/usr/bin/env bash
# PreToolUse hook: blocks "git push" unless push-gate checklist exists and passes.
# Writes bd memory on block events (best-effort).
set -euo pipefail

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // ""')
[[ "$TOOL" != "Bash" ]] && exit 0

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
[[ ! "$CMD" =~ git\ push ]] && exit 0

# We're in a git push. Find the checklist.
PROJECT_DIR=$(echo "$INPUT" | jq -r '.cwd // "."')
CHECKLIST=$(find "$PROJECT_DIR" -path "*/DRUPAL_ISSUES/*/workflow/03-push-gate-checklist.json" \
  -mmin -60 2>/dev/null | head -1)

if [[ -z "$CHECKLIST" ]]; then
  NID=$(echo "$PROJECT_DIR" | grep -oE 'DRUPAL_ISSUES/[0-9]+' | head -1 | cut -d/ -f2 || true)
  if [[ -n "$NID" ]]; then
    bd remember "Blocked premature push for $NID: no checklist" \
      --key "phase.push_gate.blocked.$NID" 2>/dev/null || true
  fi
  echo "BLOCKED: No push-gate checklist found (workflow/03-push-gate-checklist.json)." >&2
  echo "Run the full Pre-Push Quality Gate before pushing." >&2
  exit 2
fi

# Check verdicts — any FAILED, NEEDS_WORK, false, or non-zero exit code blocks
FAILED=$(jq -r 'to_entries[]
  | select(.key | test("verdict|passed|exit_code"))
  | select(
      (.value == "FAILED") or
      (.value == "NEEDS_WORK") or
      (.value == false) or
      ((.key | test("exit_code")) and (.value != 0))
    )
  | "\(.key)=\(.value)"' "$CHECKLIST" 2>/dev/null)

if [[ -n "$FAILED" ]]; then
  NID=$(jq -r '.issue_id // "unknown"' "$CHECKLIST")
  bd remember "Blocked push for $NID: failed checks: $FAILED" \
    --key "phase.push_gate.blocked.$NID" 2>/dev/null || true
  echo "BLOCKED: Push-gate checklist has failing checks:" >&2
  echo "$FAILED" >&2
  echo "Fix these before pushing." >&2
  exit 2
fi

exit 0
