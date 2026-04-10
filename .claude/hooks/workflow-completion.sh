#!/usr/bin/env bash
# Stop hook: blocks stop if review happened but push gate wasn't reached.
# Writes bd session progress on every relevant stop (best-effort).
set -euo pipefail

INPUT=$(cat)
PROJECT_DIR=$(echo "$INPUT" | jq -r '.cwd // "."')

# Find most recently modified review summary (= we're in a fix flow)
REVIEW=$(find "$PROJECT_DIR" -path "*/DRUPAL_ISSUES/*/workflow/01-review-summary.json" \
  -mmin -120 2>/dev/null | sort | tail -1)

# Not in a fix flow → let it stop, no bd write
[[ -z "$REVIEW" ]] && exit 0

WORKFLOW_DIR=$(dirname "$REVIEW")
NID=$(echo "$WORKFLOW_DIR" | grep -oE 'DRUPAL_ISSUES/[0-9]+' | head -1 | cut -d/ -f2)
CHECKLIST="$WORKFLOW_DIR/03-push-gate-checklist.json"

if [[ -f "$CHECKLIST" ]]; then
  # Push gate was reached — write progress, let it stop
  VERDICTS=$(jq -r '[
    .spec_reviewer_verdict // "n/a",
    .reviewer_verdict // "n/a",
    .verifier_verdict // "n/a"
  ] | join(", ")' "$CHECKLIST" 2>/dev/null || echo "parse-error")
  bd remember "Push gate reached for $NID: $VERDICTS" \
    --key "phase.push_gate.$NID" 2>/dev/null || true
  exit 0
else
  # Review happened but push gate not reached — block stop, write bd
  bd remember "Session stopped mid-fix for $NID: review done, push gate not reached" \
    --key "phase.session_incomplete.$NID" 2>/dev/null || true
  echo "BLOCKED: Review completed for issue $NID but push-gate checklist is missing." >&2
  echo "Complete the Pre-Push Quality Gate (CI parity, depth gate, spec/reviewer/verifier agents) before stopping." >&2
  exit 2
fi
