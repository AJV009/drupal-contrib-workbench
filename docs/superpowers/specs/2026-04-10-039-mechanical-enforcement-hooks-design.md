# Ticket 039 — Mechanical Enforcement Hooks + bd Session Progress

**Status:** SPEC (not yet implemented)
**Priority:** P1
**Type:** Enhancement
**Depends on:** 033 (research — verdict: ADOPT hooks only), 030 (workflow state file pattern), 031 (bd write pattern)
**Born from:** 033 research deliverable's "Suggested follow-up ticket"

## Goal

Add two Claude Code hooks that mechanically enforce the pre-push quality
gate and workflow completion, replacing prose-only IRON LAW enforcement
that has been shown to leak (session 9b75cb81 evidence). Include bd
writes from hooks so that cross-session memory captures workflow progress
and enforcement events.

## Why

The verification gate (ticket 022, phase 1) is prose-only. The IRON LAW
"NEVER AUTO-PUSH" works most of the time, but nothing mechanically
prevents the model from:

1. Running `git push` without having completed the pre-push quality gate
2. Stopping mid-workflow and claiming "done" without having run the
   spec/reviewer/verifier agents

Ticket 033 research confirmed that Claude Code hooks with exit code 2
**mechanically block** the action and feed stderr back to the model.
This is the only mechanism in the Claude Code ecosystem that enforces
behavior externally rather than trusting the model to obey prose.

## Architecture

### New workflow state file: `workflow/03-push-gate-checklist.json`

Written by `/drupal-contribute-fix` at a new "Step 5.5" between the
agent dispatches (Steps 3-5) and the push gate summary (Step 6). This
file is the hooks' read target — the mechanical proof that the pre-push
quality gate completed.

```json
{
  "ci_parity_exit_code": 0,
  "phpunit_passed": true,
  "depth_gate_decision": "SKIP",
  "spec_reviewer_verdict": "SPEC_COMPLIANT",
  "reviewer_verdict": "APPROVED",
  "verifier_verdict": "VERIFIED",
  "timestamp": "2026-04-10T15:30:00Z",
  "issue_id": "3581952"
}
```

### Hook 1: PreToolUse — git push gate (`.claude/hooks/push-gate.sh`)

**Event:** PreToolUse (fires before every tool call)
**Short-circuit:** exits 0 immediately if tool is not Bash or command
doesn't contain `git push`. Cost: one `jq` parse + one string match per
tool call.

**Gate logic (when `git push` detected):**
1. Search for `DRUPAL_ISSUES/*/workflow/03-push-gate-checklist.json`
   modified in the last 60 minutes
2. If not found → exit 2 ("BLOCKED: no push-gate checklist")
3. If found, check all verdict fields for FAILED/NEEDS_WORK
4. If any verdict failed → exit 2 ("BLOCKED: failing verdicts")
5. Otherwise → exit 0 (push allowed)

**bd write on block:** `bd remember "Blocked premature push for <nid>: <reason>" --key "phase.push_gate.blocked.<nid>"` (best-effort)

### Hook 2: Stop — workflow completion gate (`.claude/hooks/workflow-completion.sh`)

**Event:** Stop (fires when Claude is about to stop responding)
**Short-circuit:** exits 0 if no `01-review-summary.json` modified in
the last 120 minutes exists (= not in a fix workflow).

**Gate logic (when in a fix workflow):**
1. Find most recently modified `01-review-summary.json` (= review happened)
2. Extract issue nid from path
3. Check sibling `03-push-gate-checklist.json` exists
4. If missing → exit 2 ("BLOCKED: review done but push gate not reached")
5. If present → exit 0 + bd write progress summary

**bd writes:**
- On successful stop (checklist exists): `bd remember "Push gate reached for <nid>: <verdicts>" --key "phase.push_gate.<nid>"` (best-effort)
- On blocked stop (checklist missing): `bd remember "Session ended mid-fix for <nid>: review done, push gate not reached" --key "phase.session_incomplete.<nid>"` (best-effort)

### settings.json integration

Add PreToolUse and Stop entries alongside existing SessionStart and
PreCompact hooks. Structure:

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [{ "command": "bd prime", "type": "command" }], "matcher": "" }
    ],
    "PreCompact": [
      { "hooks": [{ "command": "bd prime", "type": "command" }], "matcher": "" }
    ],
    "PreToolUse": [
      { "hooks": [{ "command": "bash .claude/hooks/push-gate.sh", "type": "command" }], "matcher": "" }
    ],
    "Stop": [
      { "hooks": [{ "command": "bash .claude/hooks/workflow-completion.sh", "type": "command" }], "matcher": "" }
    ]
  }
}
```

## Files

### Created (3)

| Path | Lines | Purpose |
|---|---|---|
| `.claude/hooks/push-gate.sh` | ~50 | PreToolUse hook: gate git push on checklist |
| `.claude/hooks/workflow-completion.sh` | ~45 | Stop hook: gate stop mid-fix + bd progress |
| `docs/tickets/039-mechanical-enforcement-hooks.md` | ~30 | Ticket file |

### Modified (5)

| Path | Change |
|---|---|
| `.claude/settings.json` | Add PreToolUse + Stop hook entries |
| `.claude/skills/drupal-contribute-fix/SKILL.md` | New "Step 5.5: Write push-gate checklist" between agent dispatch and push gate |
| `docs/workflow-state-files.md` | Add `03-push-gate-checklist.json` row to registry |
| `docs/bd-schema.md` | 3 new phase notation prefixes |
| `CLAUDE.md` | New "Mechanical enforcement hooks" subsection |

## Hook script: push-gate.sh (full)

```bash
#!/usr/bin/env bash
# PreToolUse hook: blocks "git push" unless push-gate checklist exists and passes.
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

# Check verdicts — any FAILED or NEEDS_WORK blocks
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
```

## Hook script: workflow-completion.sh (full)

```bash
#!/usr/bin/env bash
# Stop hook: blocks stop if review happened but push gate wasn't reached.
# Writes bd session progress on every relevant stop.
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
```

## SKILL.md addition: Step 5.5

Insert between the existing "Step 5: Verifier Agent" and "Step 6: Draft
Issue Comment":

```markdown
**Step 5.5: Write push-gate checklist (MANDATORY)**

After ALL three agents (spec reviewer, reviewer, verifier) have reported,
write the push-gate checklist to enable the mechanical push gate hook:

```bash
ISSUE_ID={issue_id}
WORKFLOW_DIR=DRUPAL_ISSUES/$ISSUE_ID/workflow
mkdir -p "$WORKFLOW_DIR"

jq -n \
  --arg ci "$CI_EXIT_CODE" \
  --argjson phpunit "$PHPUNIT_PASSED" \
  --arg depth "$DEPTH_DECISION" \
  --arg spec "$SPEC_VERDICT" \
  --arg review "$REVIEWER_VERDICT" \
  --arg verify "$VERIFIER_VERDICT" \
  --arg ts "$(date -Iseconds)" \
  --arg id "$ISSUE_ID" \
  '{
    ci_parity_exit_code: ($ci | tonumber),
    phpunit_passed: $phpunit,
    depth_gate_decision: $depth,
    spec_reviewer_verdict: $spec,
    reviewer_verdict: $review,
    verifier_verdict: $verify,
    timestamp: $ts,
    issue_id: $id
  }' > "$WORKFLOW_DIR/03-push-gate-checklist.json"
```

This file is read by `.claude/hooks/push-gate.sh` (PreToolUse) and
`.claude/hooks/workflow-completion.sh` (Stop). Without it, `git push`
will be mechanically blocked and Claude cannot stop the session.

**Do NOT skip this step.** Unlike prose rules, the hooks enforce this
mechanically — there is no way to push or claim "done" without this file.
```

## bd schema additions

New rows in `docs/bd-schema.md`:

| Prefix | Written by | Meaning |
|---|---|---|
| `bd:phase.push_gate.<nid>` | Stop hook | Push gate reached, includes spec/reviewer/verifier verdicts |
| `bd:phase.session_incomplete.<nid>` | Stop hook | Session ended before push gate was reached |
| `bd:phase.push_gate.blocked.<nid>` | PreToolUse hook | A premature `git push` was blocked by the hook |

All three are `bd remember` writes (not `bd update`) with `--key` for
deduplication. Best-effort: failure does not block the hook's primary
function (exit 0 or exit 2).

## CLAUDE.md subsection

```markdown
## Mechanical enforcement hooks

Two Claude Code hooks enforce the pre-push quality gate and workflow
completion mechanically (exit code 2 blocks the action and feeds stderr
back to the model):

1. **PreToolUse → `.claude/hooks/push-gate.sh`**: blocks `git push`
   unless `workflow/03-push-gate-checklist.json` exists and all verdicts
   pass. This is the hard gate that replaces the prose IRON LAW
   "NEVER AUTO-PUSH."

2. **Stop → `.claude/hooks/workflow-completion.sh`**: blocks Claude from
   stopping if a review happened (`01-review-summary.json` exists) but
   the push gate wasn't reached (`03-push-gate-checklist.json` missing).
   Forces the model to complete the full pre-push quality gate before
   claiming "done."

Both hooks also write bd memories for cross-session progress tracking.
These are best-effort; bd failure never blocks the hook's primary gate
function.

To bypass hooks in an emergency (e.g., hook is misconfigured):
`claude --disable-hooks` (requires Claude Code 2.1.50+).
```

## Acceptance criteria

| # | Criterion | Test |
|---|---|---|
| 1 | `git push` blocked when no checklist exists | Synthetic: create a module dir, attempt push, verify stderr + exit 2 |
| 2 | `git push` blocked when checklist has FAILED verdict | Write checklist with `reviewer_verdict: "NEEDS_WORK"`, attempt push |
| 3 | `git push` passes when checklist is clean and < 60 min old | Write clean checklist, attempt push → exit 0 |
| 4 | Stop blocked mid-fix-workflow | Create `01-review-summary.json` without checklist → Claude cannot stop |
| 5 | Stop passes when not in fix workflow | No review summary → stop passes |
| 6 | Stop passes when workflow complete | Both files exist → stop passes |
| 7 | bd writes on push block event | After blocked push, `bd memories push_gate` shows event |
| 8 | bd writes on session stop | After stop, `bd memories push_gate` shows progress |
| 9 | Existing hooks still work | SessionStart/PreCompact bd prime unaffected |
| 10 | Step 5.5 checklist write is in SKILL.md | Code review of the inserted section |

Criteria 1-6 can be tested with synthetic workflow dirs.
Criteria 7-8 depend on bd being available on the remote.
Criterion 10 is wiring-verified.

## Testing strategy

**Synthetic tests on remote** (no real issue needed):
1. Create a fake `DRUPAL_ISSUES/99999/workflow/` dir
2. Test push-gate.sh directly: pipe synthetic JSON to stdin, check exit code
3. Test workflow-completion.sh directly: same pattern
4. Test settings.json validates (Claude Code loads without errors)

**No unit tests.** Shell scripts with straightforward control flow; direct
invocation tests cover all paths.

## Non-goals

- Agent Teams (rejected per 033 research — resume incompatibility)
- SubagentStop hooks (marginal value for our workflow)
- Modifying the push gate prose or IRON LAW (hooks complement, not replace)
- Automatic push (the user still confirms; the hook just prevents the
  model from reaching `git push` without verification)

## Risks

1. **Hook fires on EVERY Bash tool call.** The short-circuit (`[[ "$TOOL" != "Bash" ]] && exit 0; [[ ! "$CMD" =~ git\ push ]] && exit 0`) is two string comparisons — negligible latency. But if jq parsing of stdin fails, the hook could error. Mitigated: `set -euo pipefail` + testing.

2. **Stop hook blocks normal Q&A sessions.** Mitigated: the 120-minute `find -mmin` window ensures only recent fix workflows trigger the gate. A review from yesterday won't block today's question.

3. **Stale checklist from a prior issue.** The 60-minute `find -mmin` window on push-gate.sh prevents a checklist from issue A from greenlighting a push for issue B. If the user works two issues in rapid succession (< 60 min), the hook finds the most recent one — correct behavior since the user is pushing the most recent fix.

4. **bd not in PATH.** Hooks use `bd remember ... 2>/dev/null || true` — if bd is not available, the write silently fails and the hook's primary gate function (exit 0/2) is unaffected.

5. **`--disable-hooks` escape hatch.** Documented in CLAUDE.md subsection. If a hook is misconfigured and blocks all actions, the user can bypass with `claude --disable-hooks`.
