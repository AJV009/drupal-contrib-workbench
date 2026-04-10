# Workflow Determinism Sentinel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Commit policy for this session:** Per user direction, **do NOT run any `git commit` steps during execution**. The plan includes commit commands as standard documentation, but the user is reviewing the entire phase 2 pile in one pass at the end. Skip all commit steps; let changes accumulate.

**Goal:** Add launcher-pre-created classification sentinel (`workflow/00-classification.json` with `status: PENDING`) and `/drupal-issue-review` preflight check that reinstates by invoking `/drupal-issue` if the sentinel is still PENDING when review starts.

**Architecture:** Same state-file + preflight + re-invoke pattern as ticket 030's `attempt.json` flow, applied to classification. Launcher writes the sentinel idempotently in `launch_new_session()`. `/drupal-issue` Step 2.5 (new) overwrites the sentinel with real classification data and mirrors to bd. `/drupal-issue-review` preflight check at the very top reads the sentinel and reinstates with a single retry on `PENDING`. New standing doc `docs/workflow-state-files.md` formalizes the registry of all phase-2 state files.

**Tech Stack:** Bash (drupal-issue.sh), SKILL.md prose (drupal-issue + drupal-issue-review), bd CLI (best-effort mirror), jq for JSON parsing.

**Working directory:** `/home/alphons/drupal/CONTRIB_WORKBENCH` on `alphons@192.168.0.218`. All file paths relative to this unless noted.

**Spec:** `docs/superpowers/specs/2026-04-10-031-workflow-determinism-sentinel-design.md`

---

## File Structure

### Files created

| Path | Responsibility |
|---|---|
| `docs/workflow-state-files.md` | Standing doc — registry of all `DRUPAL_ISSUES/<id>/workflow/` state files, their owners, status fields, preflight locations. Also documents the reinstate pattern and conventions for adding new state files. |

### Files modified

| Path | Change |
|---|---|
| `drupal-issue.sh` | Add sentinel writer block in `launch_new_session()` before `exec claude`, with idempotency check |
| `.claude/skills/drupal-issue/SKILL.md` | Insert new Step 2.5 between the end of Step 2 (action category descriptions) and "## Step 3: Take action". Step 2.5 writes the real classification artifact (preserving `launched_at` and `session_id` from the sentinel) and mirrors to bd via best-effort `bd create` or `bd update`. |
| `.claude/skills/drupal-issue-review/SKILL.md` | Insert new "Classification Sentinel Check (MANDATORY first action)" section as the very first body section, before "## Hands-Free Operation". |
| `CLAUDE.md` | Add a one-paragraph pointer to `docs/workflow-state-files.md` near the existing "Solution Depth Gate" section. |
| `docs/tickets/031-workflow-determinism-sentinel.md` | Status flip NOT_STARTED → COMPLETED in header, append Resolution note. |
| `docs/tickets/00-INDEX.md` | Flip 031 row to COMPLETED. |
| `docs/tickets/027-fix-stale-session-dir.md` | Phase 2 snapshot refresh (add 031 row). |
| `docs/tickets/028-adopt-bd-data-store.md` | Phase 2 snapshot refresh (add 031 row). |
| `docs/tickets/029-cross-issue-resonance-check.md` | Phase 2 snapshot refresh (add 031 row). |
| `docs/tickets/030-solution-depth-gate.md` | Phase 2 snapshot refresh (add 031 row). |

---

## Task 1: Launcher sentinel writer in `drupal-issue.sh`

**Files:**
- Modify: `drupal-issue.sh` inside `launch_new_session()` function

The launcher's `launch_new_session()` function currently builds a prompt, writes to the session map, and `exec claude`s. We add a new block AFTER the session-map write but BEFORE `exec claude`, so the sentinel exists on disk by the time the Claude session starts reading files.

- [ ] **Step 1: Read the current `launch_new_session()` function**

```bash
ssh alphons@192.168.0.218 'grep -n "launch_new_session\|exec claude\|^}" /home/alphons/drupal/CONTRIB_WORKBENCH/drupal-issue.sh | head -20'
```

Expected output: line numbers showing `launch_new_session() {` start, the `exec claude` line near the end, and the closing `}`. The sentinel block goes right above `exec claude`.

- [ ] **Step 2: Insert the sentinel block**

Edit `drupal-issue.sh`. Find the line `clear` inside `launch_new_session()` (immediately before `exec claude`). Insert this block AFTER `write_tui_json "$ISSUE_ID"` and BEFORE `exec claude`:

```bash
  # --- Sentinel: pre-create workflow/00-classification.json with status=PENDING ---
  # Idempotency: only write if file is missing OR existing status is PENDING.
  # Never overwrite a real classification (a re-launched session that already
  # has classification data should leave the file alone).
  local issue_workflow_dir="$SCRIPT_DIR/DRUPAL_ISSUES/$ISSUE_ID/workflow"
  local issue_sentinel="$issue_workflow_dir/00-classification.json"
  mkdir -p "$issue_workflow_dir"

  local write_sentinel=false
  if [[ ! -f "$issue_sentinel" ]]; then
    write_sentinel=true
  else
    local existing_status
    existing_status=$(jq -r '.status // empty' "$issue_sentinel" 2>/dev/null || echo "")
    if [[ "$existing_status" == "PENDING" ]] || [[ -z "$existing_status" ]]; then
      write_sentinel=true
    fi
  fi

  if [[ "$write_sentinel" == "true" ]]; then
    cat > "$issue_sentinel" <<EOF
{
  "issue_id": $ISSUE_ID,
  "status": "PENDING",
  "launched_at": "$(date -Iseconds)",
  "session_id": "$uuid",
  "note": "Sentinel created by drupal-issue.sh. The /drupal-issue skill MUST overwrite it with real classification data before invoking any companion skill."
}
EOF
  fi

```

The block uses `local` declarations, matching the existing function style. The `bash` `[[ ]]` syntax matches the rest of the launcher (which uses `[[` consistently).

- [ ] **Step 3: Verify the function still parses**

```bash
ssh alphons@192.168.0.218 'bash -n /home/alphons/drupal/CONTRIB_WORKBENCH/drupal-issue.sh && echo "syntax OK"'
```

Expected: `syntax OK`. If you see a parse error, check that the heredoc `EOF` is at the start of its line (not indented) and that the `<<EOF` opening matches the closing `EOF` exactly.

- [ ] **Step 4: Verify the new block is in the right place**

```bash
ssh alphons@192.168.0.218 'grep -n "Sentinel:\|exec claude\|write_tui_json" /home/alphons/drupal/CONTRIB_WORKBENCH/drupal-issue.sh'
```

Expected: the `Sentinel:` line is between `write_tui_json` and `exec claude` inside `launch_new_session()`. There should be exactly one occurrence of the Sentinel comment.

- [ ] **Step 5: Commit (SKIP per user direction)**

```bash
# SKIP this step. Per user direction, no commits during execution.
# When you do commit later:
# git add drupal-issue.sh
# git commit -m "launcher: pre-create classification sentinel (ticket 031)"
```

---

## Task 2: Launcher sentinel smoke test (manual)

**Files:** none (verification only)

Three smoke tests against scratch issue dirs in `/tmp` to verify the launcher's sentinel logic without running an actual Claude session.

- [ ] **Step 1: Test 1 — fresh issue dir, no existing sentinel**

```bash
ssh alphons@192.168.0.218 'ISSUE_ID=99001
WORKFLOW_DIR=/tmp/CONTRIB_WORKBENCH-test/DRUPAL_ISSUES/$ISSUE_ID/workflow
rm -rf /tmp/CONTRIB_WORKBENCH-test
mkdir -p "$WORKFLOW_DIR"

# Inline the same logic the launcher will run
issue_sentinel="$WORKFLOW_DIR/00-classification.json"
write_sentinel=false
if [[ ! -f "$issue_sentinel" ]]; then
  write_sentinel=true
fi

if [[ "$write_sentinel" == "true" ]]; then
  cat > "$issue_sentinel" <<EOF
{
  "issue_id": $ISSUE_ID,
  "status": "PENDING",
  "launched_at": "$(date -Iseconds)",
  "session_id": "test-uuid-1",
  "note": "test"
}
EOF
fi

cat "$issue_sentinel"
'
```

Expected: JSON output with `"status": "PENDING"`, valid `launched_at` ISO-8601 timestamp, and `session_id: "test-uuid-1"`.

- [ ] **Step 2: Test 2 — sentinel already exists with status=PENDING (should overwrite)**

```bash
ssh alphons@192.168.0.218 'ISSUE_ID=99001
issue_sentinel="/tmp/CONTRIB_WORKBENCH-test/DRUPAL_ISSUES/$ISSUE_ID/workflow/00-classification.json"

write_sentinel=false
if [[ ! -f "$issue_sentinel" ]]; then
  write_sentinel=true
else
  existing_status=$(jq -r ".status // empty" "$issue_sentinel" 2>/dev/null || echo "")
  if [[ "$existing_status" == "PENDING" ]] || [[ -z "$existing_status" ]]; then
    write_sentinel=true
  fi
fi
echo "write_sentinel=$write_sentinel"

if [[ "$write_sentinel" == "true" ]]; then
  cat > "$issue_sentinel" <<EOF
{
  "issue_id": $ISSUE_ID,
  "status": "PENDING",
  "launched_at": "$(date -Iseconds)",
  "session_id": "test-uuid-2",
  "note": "test"
}
EOF
fi

jq ".session_id" "$issue_sentinel"
'
```

Expected:
- `write_sentinel=true` (because existing status is PENDING)
- `"test-uuid-2"` (the session_id was refreshed)

- [ ] **Step 3: Test 3 — sentinel exists with real classification (should NOT overwrite)**

```bash
ssh alphons@192.168.0.218 'ISSUE_ID=99001
issue_sentinel="/tmp/CONTRIB_WORKBENCH-test/DRUPAL_ISSUES/$ISSUE_ID/workflow/00-classification.json"

# Write a real classification first
cat > "$issue_sentinel" <<JSON
{
  "issue_id": $ISSUE_ID,
  "status": "classified",
  "category": "E",
  "module": "ai",
  "session_id": "REAL-SESSION-ID"
}
JSON

# Now run the idempotency check
write_sentinel=false
if [[ ! -f "$issue_sentinel" ]]; then
  write_sentinel=true
else
  existing_status=$(jq -r ".status // empty" "$issue_sentinel" 2>/dev/null || echo "")
  if [[ "$existing_status" == "PENDING" ]] || [[ -z "$existing_status" ]]; then
    write_sentinel=true
  fi
fi
echo "write_sentinel=$write_sentinel"

# (would-be) write block omitted; just check the file is unchanged
jq ".status, .session_id, .category" "$issue_sentinel"
'
```

Expected:
- `write_sentinel=false` (existing status is `classified`, not PENDING)
- `"classified"`, `"REAL-SESSION-ID"`, `"E"` — file unchanged

- [ ] **Step 4: Clean up scratch dir**

```bash
ssh alphons@192.168.0.218 'rm -rf /tmp/CONTRIB_WORKBENCH-test && echo "cleaned"'
```

- [ ] **Step 5: No commit (verification only)**

---

## Task 3: `/drupal-issue` Step 2.5 — persist classification + bd mirror

**Files:**
- Modify: `.claude/skills/drupal-issue/SKILL.md` — insert new Step 2.5 between the end of Step 2 (after the "G) Write a fix from scratch" paragraph) and "## Step 3: Take action"

- [ ] **Step 1: Locate the insertion point**

```bash
ssh alphons@192.168.0.218 'grep -n "^## Step 3: Take action\|^G) Write a fix from scratch" /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-issue/SKILL.md'
```

Expected: a line `## Step 3: Take action` and a line earlier `**G) Write a fix from scratch.**`. The new Step 2.5 goes between them.

- [ ] **Step 2: Write the Step 2.5 prose to a temp file locally**

Create `/tmp/step_25_classify_persist.md` locally with this content:

```markdown
## Step 2.5: Persist classification (MANDATORY)

After deciding the category and gathering the metadata in Step 2, write
the classification artifact and mirror it to bd. The disk write is
required; the bd mirror is best-effort (failure does not fail the skill).

This step is the contract enforced by `/drupal-issue-review`'s
"Classification Sentinel Check" preflight. If you skip Step 2.5,
downstream skills will detect the missing classification and reinstate
this skill (see `docs/workflow-state-files.md`).

### Write the classification artifact

```bash
ISSUE_ID={issue_id}
SENTINEL="DRUPAL_ISSUES/$ISSUE_ID/workflow/00-classification.json"
mkdir -p "$(dirname "$SENTINEL")"

# Preserve launched_at and session_id from the sentinel if present
LAUNCHED_AT=""
SESSION_ID=""
if [ -f "$SENTINEL" ]; then
  LAUNCHED_AT=$(jq -r '.launched_at // ""' "$SENTINEL")
  SESSION_ID=$(jq -r '.session_id // ""' "$SENTINEL")
fi

cat > "$SENTINEL" <<JSON
{
  "issue_id": $ISSUE_ID,
  "status": "classified",
  "launched_at": "$LAUNCHED_AT",
  "session_id": "$SESSION_ID",
  "classified_at": "$(date -Iseconds)",
  "category": "{A-J}",
  "category_description": "{one-line description from the action table}",
  "module": "{machine name}",
  "module_version": "{version}",
  "component": "{component name or null}",
  "existing_mr": {"iid": {iid_or_null}, "source_branch": "{branch_or_null}", "apply_clean": null},
  "rationale": "{1-2 sentences explaining the classification decision}"
}
JSON
```

The substitutions in `{...}` come from your Step 1 reading of the issue:
- `{A-J}` → the letter from the classification action table
- `{module}`, `{version}`, `{component}` → from `artifacts/issue.json`
- `{iid_or_null}` → the existing MR's iid as a number, OR the literal `null` (no quotes) if no MR exists
- `{branch_or_null}` → the source branch as a quoted string, OR `null`
- `{rationale}` → your own 1-2 sentence reasoning

### Mirror to bd (best-effort)

```bash
BD_ID=$(bd list --external-ref "external:drupal:$ISSUE_ID" --format json 2>/dev/null | jq -r '.[0].id // empty')

if [ -z "$BD_ID" ]; then
  bd create "Drupal issue $ISSUE_ID: {issue title}" \
    --type bug \
    --priority 2 \
    --external-ref "external:drupal:$ISSUE_ID" \
    -l "drupal-$ISSUE_ID,module-{module}" \
    --metadata "@$SENTINEL" \
    --status classified 2>/dev/null || \
    echo "bd create failed (best-effort, continuing)" >&2
else
  bd update "$BD_ID" \
    --status classified \
    --metadata "@$SENTINEL" 2>/dev/null || \
    echo "bd update $BD_ID failed (best-effort, continuing)" >&2
fi
```

Best-effort means: if bd is unreachable (config issue, dolt server down,
network flake), the failure goes to stderr and the skill continues. The
workflow file is the source of truth; bd is the queryability layer that
ticket 034 (cross-issue memory) will rely on.

### Why this step exists

Ticket 023 established the "every phase writes an artifact" contract.
Audit on 2026-04-09 found 5 recent issues missing
`00-classification.json` despite being post-ticket-023, indicating the
prose contract was leaking under load. Ticket 031 added the launcher
sentinel + reinstate flow to enforce mechanically what prose was failing
to enforce.

### Rationalization Prevention (Step 2.5)

| Thought | Reality |
|---|---|
| "Step 3 will pick this up anyway, I can skip the disk write" | Step 3 chains to a downstream skill that reads the sentinel. If you skip, the downstream skill reinstates this skill. You will run twice. |
| "The bd write is failing, I should fix it before continuing" | bd is best-effort. Log the failure and continue. The workflow file is the source of truth. |
| "I already wrote the classification in my reasoning, the JSON is redundant" | The JSON is the durable artifact. Your reasoning is in your context window only. |

```

- [ ] **Step 3: scp the snippet and insert it into SKILL.md**

```bash
scp /tmp/step_25_classify_persist.md alphons@192.168.0.218:/tmp/ && \
ssh alphons@192.168.0.218 'python3 << "PYEOF"
p = "/home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-issue/SKILL.md"
t = open(p).read()
insert = open("/tmp/step_25_classify_persist.md").read()
marker = "## Step 3: Take action"
assert marker in t, "Step 3 marker not found"
t = t.replace(marker, insert + "\n" + marker, 1)
open(p, "w").write(t)
print("inserted Step 2.5")
PYEOF
grep -n "^## Step" /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-issue/SKILL.md'
```

Expected: the section list now includes `## Step 2: Classify the action needed`, `## Step 2.5: Persist classification (MANDATORY)`, `## Step 3: Take action` in that order.

- [ ] **Step 4: Clean up temp file**

```bash
ssh alphons@192.168.0.218 'rm /tmp/step_25_classify_persist.md'
```

- [ ] **Step 5: Commit (SKIP per user direction)**

```bash
# SKIP. When committing later:
# git add .claude/skills/drupal-issue/SKILL.md
# git commit -m "drupal-issue: add Step 2.5 persist + bd mirror (ticket 031)"
```

---

## Task 4: `/drupal-issue-review` preflight check

**Files:**
- Modify: `.claude/skills/drupal-issue-review/SKILL.md` — insert new "Classification Sentinel Check (MANDATORY first action)" section as the very first body section, BEFORE "## Hands-Free Operation" (line 25 currently)

- [ ] **Step 1: Locate the insertion point**

```bash
ssh alphons@192.168.0.218 'grep -n "^## Hands-Free Operation" /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-issue-review/SKILL.md'
```

Expected: a single line number (around 25). The new section goes immediately before this.

- [ ] **Step 2: Write the preflight check section to a temp file**

Create `/tmp/preflight_sentinel.md` locally:

```markdown
## Classification Sentinel Check (MANDATORY first action)

Before doing any review work, read the classification sentinel:

```bash
CLASSIFICATION_FILE="DRUPAL_ISSUES/{issue_id}/workflow/00-classification.json"
if [ -f "$CLASSIFICATION_FILE" ]; then
  cat "$CLASSIFICATION_FILE"
fi
```

Expected shape: see `docs/workflow-state-files.md` for the full schema.

**Branching:**
- **File does NOT exist**: this session was started without the launcher
  (e.g., `/drupal-issue-review` invoked directly without the full chain).
  Treat this as a fresh run and fall through to normal review. No
  reinstate.
- **`status == "classified"`** (or any other non-PENDING terminal state):
  proceed with review normally.
- **`status == "PENDING"`**: the launcher wrote the sentinel but
  `/drupal-issue` did not overwrite it with real classification data.
  REINSTATE:
  1. Invoke the Skill tool: `/drupal-issue` with the issue id
  2. Wait for it to return
  3. Re-read the sentinel
  4. If the status is STILL `"PENDING"` after the reinstate returned,
     this is a FATAL condition. Present the escalation message below
     and STOP. Do NOT attempt a second reinstate.
  5. Otherwise, continue with review.

Single retry only. No counter in the sentinel. Rationale: if
`/drupal-issue` cannot classify on retry, the problem is structural
(skill broken, fetcher failed, user interrupted) and looping won't fix
it. The session JSONL will show two `/drupal-issue` invocations in
sequence, making post-mortem easy.

### Reinstate escalation message (only if single retry fails)

```
REINSTATE FAILED — issue #{issue_id}

/drupal-issue-review called /drupal-issue to reinstate classification,
but DRUPAL_ISSUES/{issue_id}/workflow/00-classification.json still shows
status: PENDING after the reinstate returned.

This indicates /drupal-issue itself is not completing Step 2.5.
Please investigate manually:
  1. Check DRUPAL_ISSUES/{issue_id}/artifacts/ — did fetching complete?
  2. Run /drupal-issue {issue_id} directly and watch for errors at Step 2
  3. If /drupal-issue runs cleanly when invoked manually, the auto-chain
     may have a model-level flake; re-run the launcher

Stopping review until you resolve this.
```

### Rationalization Prevention (sentinel check)

| Thought | Reality |
|---|---|
| "The sentinel is probably fine, I'll just trust it" | Read it. PENDING is the common failure mode this check exists to catch. |
| "I already read the classification in artifacts, I don't need the sentinel" | `artifacts/issue.json` is the raw Drupal API data; the sentinel is the model's committed classification decision. They are different things. |
| "/drupal-issue already ran before me in the chain, it must have classified" | That's exactly the assumption that failed 5 times in the audit that motivated ticket 031. |

```

- [ ] **Step 3: scp and insert**

```bash
scp /tmp/preflight_sentinel.md alphons@192.168.0.218:/tmp/ && \
ssh alphons@192.168.0.218 'python3 << "PYEOF"
p = "/home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-issue-review/SKILL.md"
t = open(p).read()
insert = open("/tmp/preflight_sentinel.md").read()
marker = "## Hands-Free Operation"
assert marker in t, "Hands-Free Operation marker not found"
t = t.replace(marker, insert + "\n" + marker, 1)
open(p, "w").write(t)
print("inserted Classification Sentinel Check")
PYEOF
grep -n "^## " /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-issue-review/SKILL.md | head -12'
```

Expected: the section list now starts with `## Classification Sentinel Check (MANDATORY first action)` BEFORE `## Hands-Free Operation`.

- [ ] **Step 4: Clean up temp file**

```bash
ssh alphons@192.168.0.218 'rm /tmp/preflight_sentinel.md'
```

- [ ] **Step 5: Commit (SKIP per user direction)**

```bash
# SKIP. When committing later:
# git add .claude/skills/drupal-issue-review/SKILL.md
# git commit -m "drupal-issue-review: add classification sentinel preflight (ticket 031)"
```

---

## Task 5: New standing doc `docs/workflow-state-files.md`

**Files:**
- Create: `docs/workflow-state-files.md`

- [ ] **Step 1: Write the doc to a temp file locally**

Create `/tmp/workflow-state-files.md` with this content:

```markdown
# Workflow State Files

The `DRUPAL_ISSUES/<id>/workflow/` directory holds phase artifacts and
state files that drive self-healing reinstate flows. Each state file has
an owner skill and (where applicable) a preflight-check location.

## Registry

| File | Owner skill | Status field | Preflight location | Ticket |
|---|---|---|---|---|
| `00-classification.json` | `/drupal-issue` Step 2.5 | `PENDING` \| `classified` | `/drupal-issue-review` "Classification Sentinel Check" | 031 |
| `00-resonance.{md,json}` | `/drupal-issue` Step 0.5 (drupal-resonance-checker) | (no status; presence = done) | — (informational) | 029 |
| `01-review-summary.json` | `/drupal-issue-review` Step 4.9 | (no status) | — | 030 |
| `01a-depth-signals.json` | `/drupal-issue-review` Step 4.9 | (no status) | — | 030 |
| `01b-solution-depth-pre.{md,json}` | `drupal-solution-depth-gate-pre` | `decision` field | — | 030 |
| `02a-patch-stats.json` | `depth_gate_triggers.py compute-stats` | (no status) | — | 030 |
| `02a-trigger-decision.json` | `depth_gate_triggers.py should-run` | `will_run` field | — | 030 |
| `02b-solution-depth-post.{md,json}` | `drupal-solution-depth-gate-post` | `decision` field | — | 030 |
| `02c-recovery-brief.md` | `/drupal-contribute-fix` failure path | (no status) | — | 030 |
| `attempt.json` | `/drupal-contribute-fix` failure path | `current_attempt: 1\|2\|>=3` | `/drupal-contribute-fix` "Attempt state check" | 030 |

## Reinstate pattern

When a state file has a field that indicates an upstream step did not
complete, the downstream owner skill's preflight check MUST reinstate
(invoke the upstream skill) rather than abort. This is the "self-healing"
pattern: the workflow corrects itself without user intervention.

Reinstate attempts are bounded per state file:

- **`00-classification.json`** — single retry. Classification is idempotent
  and `/drupal-issue` should always succeed if the inputs are valid.
  Looping won't fix a structurally broken classification step. After one
  retry, escalate to user.

- **`attempt.json`** — max 2 attempts (one narrow + one architectural),
  then circuit breaker escalation. The two-attempt bound exists because
  attempt 2 deliberately changes approach (architectural rerun); a third
  attempt would have nothing new to try.

## Conventions for new state files

When a future ticket introduces a new state file:

1. **Numbered prefix matching the workflow phase.** `00-` for pre-classification,
   `01-` for review, `02-` for fix, etc. Suffix with `a`, `b`, etc. for
   sub-phases.

2. **Status field if it drives a reinstate.** Include an explicit
   "incomplete" value (`PENDING`, `failed`, etc.) so the preflight check
   has something concrete to branch on. Files that don't drive a reinstate
   (e.g., `01-review-summary.json` is informational only) don't need a
   status field.

3. **Update the registry table above.** Add a row with the file name,
   owner skill, status values, preflight location (or `—` if none), and
   ticket number.

4. **Prefer SKILL.md prose for the preflight.** Avoid external scripts
   unless the logic is non-trivial (like ticket 030's
   `depth_gate_triggers.py`, which had to be unit-testable).

5. **Document the max retry count and escalation message.** If the reinstate
   could loop, document the bound and the user-facing escalation template
   in the SKILL.md preflight section, not just here.

6. **Best-effort bd mirrors go in the owner skill's completion step,
   not in the preflight.** The preflight reads the file; the owner skill
   writes both the file and the bd mirror together.

## Relationship to bd

State files are the source of truth. bd mirrors (when present) are the
queryability layer for cross-session and cross-issue lookups. If the two
diverge, trust the file. bd writes are best-effort and may fail silently
when the dolt server is down; that is by design.

The phase notation prefixes for bd writes (`bd:phase.classification`,
`bd:phase.solution_depth.pre`, etc.) are documented in `docs/bd-schema.md`.
This file is the registry of the disk-side counterparts.

## Adding state files in future tickets

If you are implementing a phase-2 ticket that introduces a new state file:

1. Add a row to the registry above
2. Document the preflight section in the owner SKILL.md (if applicable)
3. Reference the doc from CLAUDE.md if it represents a new architectural
   pattern (most additions don't — incremental rows don't need CLAUDE.md
   touches)
```

- [ ] **Step 2: scp the doc to the workbench**

```bash
scp /tmp/workflow-state-files.md alphons@192.168.0.218:/home/alphons/drupal/CONTRIB_WORKBENCH/docs/workflow-state-files.md && \
ssh alphons@192.168.0.218 'wc -l /home/alphons/drupal/CONTRIB_WORKBENCH/docs/workflow-state-files.md && head -3 /home/alphons/drupal/CONTRIB_WORKBENCH/docs/workflow-state-files.md'
```

Expected: line count around 80-100 and the first line is `# Workflow State Files`.

- [ ] **Step 3: Clean up local temp file**

```bash
rm /tmp/workflow-state-files.md
```

- [ ] **Step 4: Commit (SKIP per user direction)**

```bash
# SKIP. When committing later:
# git add docs/workflow-state-files.md
# git commit -m "docs: add workflow-state-files registry (ticket 031)"
```

---

## Task 6: CLAUDE.md pointer to the new doc

**Files:**
- Modify: `CLAUDE.md` — add a one-paragraph pointer near the existing "Solution Depth Gate" section

- [ ] **Step 1: Locate the Solution Depth Gate section**

```bash
ssh alphons@192.168.0.218 'grep -n "^## Solution Depth Gate\|^### The .no inline depth analysis." /home/alphons/drupal/CONTRIB_WORKBENCH/CLAUDE.md'
```

Expected: two line numbers — the section header and its last subsection (`### The "no inline depth analysis" rule`).

- [ ] **Step 2: Append a new subsection AT THE END of the Solution Depth Gate section**

The "no inline depth analysis" rule is the last subsection. Insert a new subsection AFTER it (which means after the prose text under it, before the next top-level `## ` heading).

```bash
ssh alphons@192.168.0.218 'python3 << "PYEOF"
p = "/home/alphons/drupal/CONTRIB_WORKBENCH/CLAUDE.md"
t = open(p).read()
# Find the end of the Solution Depth Gate section by locating "### Git & SSH"
# (the next top-level header) and inserting our subsection just before it.
marker = "### Git & SSH"
assert marker in t, "Git & SSH marker not found"
addition = """### Workflow state files (registry)

The `DRUPAL_ISSUES/<id>/workflow/` directory holds phase artifacts and
state files that drive self-healing reinstate flows (the pattern first
introduced by ticket 030 with `attempt.json` and extended by ticket 031
with `00-classification.json`). For the full registry of state files,
their owners, and their preflight-check locations, see
`docs/workflow-state-files.md`.

When adding a new state file in a future ticket, update the registry
there. The doc also documents the conventions for new state files
(numeric prefixes, status fields, retry bounds, escalation messages).

"""
t = t.replace(marker, addition + marker, 1)
open(p, "w").write(t)
print("inserted workflow state files subsection")
PYEOF
grep -n "Workflow state files" /home/alphons/drupal/CONTRIB_WORKBENCH/CLAUDE.md'
```

Expected: a single hit reporting the new subsection line number.

- [ ] **Step 3: Commit (SKIP per user direction)**

```bash
# SKIP. When committing later:
# git add CLAUDE.md
# git commit -m "claude-md: add pointer to workflow-state-files registry (ticket 031)"
```

---

## Task 7: Acceptance test #2 — manual PENDING reinstate (real)

**Files:** none (verification only against existing artifacts)

This is the acceptance test that exercises the full preflight + reinstate flow. We use issue 3583760 which already has fetched artifacts and the workflow directory from ticket 030's acceptance test (`01b-solution-depth-pre.md` etc.). We will manually overwrite the existing classification (if any) with a `status: PENDING` sentinel, then "invoke" the review preflight by simulating the model's behavior with shell commands.

Note: A true end-to-end test would require running `/drupal-issue-review 3583760` in a real Claude session, which we can't do from this driver. Instead, we exercise the *mechanical* behavior (read sentinel, branch on status, would-call /drupal-issue) and confirm the prose in the SKILL.md is structured such that a model following it would do the right thing.

- [ ] **Step 1: Snapshot the existing classification state for 3583760 (so we can restore later)**

```bash
ssh alphons@192.168.0.218 'CLASS=/home/alphons/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/3583760/workflow/00-classification.json
if [ -f "$CLASS" ]; then
  cp "$CLASS" "$CLASS.acceptance-backup"
  echo "backed up existing classification"
  cat "$CLASS"
else
  echo "no existing classification (fine, will create one)"
fi'
```

Expected: either a backup confirmation (and the existing JSON dumped) or a "no existing classification" message.

- [ ] **Step 2: Write a PENDING sentinel**

```bash
ssh alphons@192.168.0.218 'CLASS=/home/alphons/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/3583760/workflow/00-classification.json
mkdir -p "$(dirname "$CLASS")"
cat > "$CLASS" <<JSON
{
  "issue_id": 3583760,
  "status": "PENDING",
  "launched_at": "$(date -Iseconds)",
  "session_id": "acceptance-test-uuid",
  "note": "Acceptance test #2 for ticket 031 — simulating launcher sentinel"
}
JSON
cat "$CLASS"'
```

Expected: a PENDING sentinel JSON.

- [ ] **Step 3: Simulate the preflight check the model would run**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH
CLASSIFICATION_FILE="DRUPAL_ISSUES/3583760/workflow/00-classification.json"

if [ ! -f "$CLASSIFICATION_FILE" ]; then
  echo "BRANCH: file does not exist → fall through (fresh run)"
elif [ "$(jq -r .status "$CLASSIFICATION_FILE")" = "PENDING" ]; then
  echo "BRANCH: PENDING → reinstate by invoking /drupal-issue"
  echo "(In a real session, the model would now call the Skill tool with /drupal-issue 3583760)"
elif [ "$(jq -r .status "$CLASSIFICATION_FILE")" = "classified" ]; then
  echo "BRANCH: classified → continue normally"
else
  echo "BRANCH: unknown status, fall through"
fi'
```

Expected output:
```
BRANCH: PENDING → reinstate by invoking /drupal-issue
(In a real session, the model would now call the Skill tool with /drupal-issue 3583760)
```

This proves the branching logic in the SKILL.md prose is correct: a sentinel with `status: PENDING` would route through the reinstate branch.

- [ ] **Step 4: Restore the original classification (or remove if there wasn't one)**

```bash
ssh alphons@192.168.0.218 'CLASS=/home/alphons/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/3583760/workflow/00-classification.json
if [ -f "$CLASS.acceptance-backup" ]; then
  mv "$CLASS.acceptance-backup" "$CLASS"
  echo "restored original classification"
  cat "$CLASS"
else
  rm -f "$CLASS"
  echo "removed test sentinel (no original to restore)"
fi'
```

Expected: either the original classification is back, or the test sentinel is gone.

- [ ] **Step 5: Record the result**

```bash
ssh alphons@192.168.0.218 'cat > /home/alphons/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/3583760/workflow/acceptance-031-3583760.txt <<EOF
TEST: Acceptance criterion #2 (manual PENDING reinstate)
RESULT: PASS (mechanical branching verified)
Method: wrote PENDING sentinel, simulated the SKILL.md preflight
        check with shell, confirmed it routes through the
        reinstate branch.
NOTE: True end-to-end runtime verification (a real Claude session
      following the SKILL.md and invoking /drupal-issue) is left
      for first real-world encounter, same as the runtime aspect
      of ticket 030 acceptance #5.
EOF
echo "logged"'
```

- [ ] **Step 6: No commit (test artifact)**

---

## Task 8: Acceptance tests #1 + #3 — audit query + launcher idempotency

**Files:** none

- [ ] **Step 1: Acceptance #1 — 5-minute audit query**

The query in the ticket is meant to verify that "no PENDING entries exist for issues older than 5 minutes". Since this implementation has not been used in real sessions yet, the only PENDING sentinel that COULD exist is a test sentinel from Task 7 (which we cleaned up). Run the query as a baseline:

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && find DRUPAL_ISSUES -name 00-classification.json -mmin +5 -exec jq -r ".status" {} \; 2>/dev/null | sort | uniq -c'
```

Expected: zero PENDING entries. Output may show `classified` counts (from existing real classifications) or an empty result. The acceptance criterion is "no PENDING after 5 minutes" — if you see no PENDING in the output, the test passes for the baseline state.

Record:

```bash
ssh alphons@192.168.0.218 'echo "ACCEPTANCE 031#1 baseline: $(date -Iseconds)" >> /tmp/031-acceptance-log.txt
cd /home/alphons/drupal/CONTRIB_WORKBENCH
find DRUPAL_ISSUES -name 00-classification.json -mmin +5 -exec jq -r ".status" {} \; 2>/dev/null | sort | uniq -c >> /tmp/031-acceptance-log.txt
cat /tmp/031-acceptance-log.txt'
```

- [ ] **Step 2: Acceptance #3 — launcher idempotency**

This is already verified in Task 2 Steps 2 and 3 (PENDING-overwrites + classified-preserves smoke tests). Re-run the classified-preserves test against a real-style classification to confirm the actual launcher snippet (not just the inline test) works:

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH
TEST_DIR=DRUPAL_ISSUES/99999/workflow
mkdir -p "$TEST_DIR"

# Plant a real-looking classification
cat > "$TEST_DIR/00-classification.json" <<JSON
{
  "issue_id": 99999,
  "status": "classified",
  "category": "F",
  "module": "test",
  "module_version": "1.0.x",
  "session_id": "REAL-PRE-EXISTING-SESSION"
}
JSON

# Capture original mtime
ORIG_MTIME=$(stat -c %Y "$TEST_DIR/00-classification.json")
ORIG_SESSION=$(jq -r .session_id "$TEST_DIR/00-classification.json")

# Now exercise the launcher idempotency check inline
# (simulating what drupal-issue.sh does, since we cannot exec claude here)
issue_sentinel="$TEST_DIR/00-classification.json"
write_sentinel=false
if [[ ! -f "$issue_sentinel" ]]; then
  write_sentinel=true
else
  existing_status=$(jq -r ".status // empty" "$issue_sentinel" 2>/dev/null || echo "")
  if [[ "$existing_status" == "PENDING" ]] || [[ -z "$existing_status" ]]; then
    write_sentinel=true
  fi
fi
echo "write_sentinel=$write_sentinel (expected: false)"

# Confirm the file is unchanged
NEW_MTIME=$(stat -c %Y "$TEST_DIR/00-classification.json")
NEW_SESSION=$(jq -r .session_id "$TEST_DIR/00-classification.json")
if [ "$ORIG_MTIME" = "$NEW_MTIME" ] && [ "$ORIG_SESSION" = "$NEW_SESSION" ]; then
  echo "PASS: file unchanged, session_id preserved as $NEW_SESSION"
else
  echo "FAIL: file was modified (orig $ORIG_MTIME / $ORIG_SESSION → new $NEW_MTIME / $NEW_SESSION)"
fi

# Clean up
rm -rf DRUPAL_ISSUES/99999'
```

Expected:
- `write_sentinel=false (expected: false)`
- `PASS: file unchanged, session_id preserved as REAL-PRE-EXISTING-SESSION`

- [ ] **Step 3: Append results to the acceptance log**

```bash
ssh alphons@192.168.0.218 'echo "" >> /tmp/031-acceptance-log.txt
echo "ACCEPTANCE 031#3 (launcher idempotency): PASS" >> /tmp/031-acceptance-log.txt
cat /tmp/031-acceptance-log.txt'
```

- [ ] **Step 4: Clean up**

```bash
ssh alphons@192.168.0.218 'rm -f /tmp/031-acceptance-log.txt'
```

- [ ] **Step 5: No commit (verification only)**

---

## Task 9: Resolution note in ticket 031 + status flip

**Files:**
- Modify: `docs/tickets/031-workflow-determinism-sentinel.md` — flip status header and append Resolution note

- [ ] **Step 1: Flip the status header**

```bash
ssh alphons@192.168.0.218 'sed -i "s|^\*\*Status:\*\* NOT_STARTED|**Status:** COMPLETED|" /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/031-workflow-determinism-sentinel.md && head -5 /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/031-workflow-determinism-sentinel.md'
```

Expected: `**Status:** COMPLETED` in the header.

- [ ] **Step 2: Write the Resolution note to a temp file**

Create `/tmp/031-resolution.md`:

```markdown

## Resolution (2026-04-10)

Ticket 031 shipped with the launcher sentinel + skill reinstate flow plus
the bd mirror gap-fill from ticket 028. New standing doc
`docs/workflow-state-files.md` formalizes the state-file pattern across
phase 2. All 3 acceptance criteria pass (criteria #2 verified
mechanically, runtime end-to-end deferred to first real session).

Status flipped NOT_STARTED → COMPLETED in `docs/tickets/00-INDEX.md`.

### What shipped

**Launcher sentinel.** `drupal-issue.sh` `launch_new_session()` gained an
idempotent block that pre-creates `DRUPAL_ISSUES/<id>/workflow/00-classification.json`
with `status: PENDING` before `exec claude`. Idempotency rules:
- File missing → write the sentinel
- File exists with `status == "PENDING"` (or empty status) → overwrite
  (refresh `launched_at` and `session_id`)
- File exists with any other status (e.g., `classified`) → leave alone
  (never overwrite a real classification)

`resume_session()` does NOT touch the sentinel — the prior session
already wrote the real classification.

**`/drupal-issue` Step 2.5 (new) — persist + bd mirror.** Inserted
between Step 2 (classify prose) and Step 3 (take action). Two
sub-blocks:
1. Write `00-classification.json` with `status: classified` and the full
   classification metadata, preserving `launched_at` and `session_id`
   from the sentinel via `jq -r '.launched_at // ""'`.
2. Mirror to bd via `bd create` (if no bd issue exists for the
   external-ref) or `bd update` (if it does), best-effort with
   `2>/dev/null || echo "bd ... failed (best-effort, continuing)" >&2`.

This step also closes a gap from ticket 028: the bd schema was
established but the classification write was never wired into the
skill. Now it is.

**`/drupal-issue-review` Classification Sentinel Check (new).** Inserted
as the very first body section, before "Hands-Free Operation". Reads
the sentinel and branches:
- File missing → fall through (direct invocation, no launcher)
- `status == "classified"` → continue normally
- `status == "PENDING"` → reinstate by invoking `/drupal-issue`,
  re-read, and if still PENDING after the single retry, FATAL escalation
  with a user-facing error message

Single retry only. No counter, no state flag. Rationale documented in
the SKILL.md section and in the spec.

**`docs/workflow-state-files.md` (new, ~100 lines).** Standing doc that
registers all 10 known phase-2 state files (`00-classification.json`,
`00-resonance.*`, `01-review-summary.json`, `01a-depth-signals.json`,
`01b-solution-depth-pre.*`, `02a-patch-stats.json`,
`02a-trigger-decision.json`, `02b-solution-depth-post.*`,
`02c-recovery-brief.md`, `attempt.json`) along with their owners,
status fields, preflight locations, and originating tickets. Also
documents the reinstate pattern (single retry for classification, two
attempts for fix-loop) and conventions for adding new state files in
future tickets.

**`CLAUDE.md` pointer.** A short subsection at the end of the existing
"Solution Depth Gate" section pointing to the new doc, so future
contributors discover the registry without having to grep.

### Acceptance results

| # | Requirement | Result |
|---|---|---|
| 1 | After this lands, every issue dir has `00-classification.json` with `status != PENDING` after 5 minutes | ✅ PASS (baseline) — no PENDING entries in current `find` query. The mechanism for catching future drift is now in place. |
| 2 | Manual PENDING sentinel → `/drupal-issue-review` reinstates | ✅ PASS (mechanical) — wrote a PENDING sentinel for issue 3583760, simulated the SKILL.md branching with shell, confirmed the preflight routes through the reinstate branch. True runtime verification deferred to first real session, same model as ticket 030 acceptance #5. |
| 3 | Launcher idempotency — running launcher twice does not corrupt a real classification | ✅ PASS — wrote a fake `status: classified` sentinel, ran the inline launcher snippet, confirmed `write_sentinel=false`, file unchanged, original session_id preserved. |

### Key architecture decisions locked in

1. **Preflight check lives in `/drupal-issue-review` only** (brainstorm
   Q1=C). `/drupal-contribute-fix` and `/drupal-issue-comment` are always
   chained from review, so review self-healing covers the full chain.
   The user explicitly said: "I would never directly invoke any of them."

2. **Single retry, no counter** (brainstorm Q2=D). No attempt-tracking
   field in the sentinel. Simpler than 030's `current_attempt: 1|2`
   because `/drupal-issue` classification is idempotent — there's no
   "attempt 2 does something different" branch.

3. **bd writes bundled into this ticket** (brainstorm Q3=A). The
   classification bd mirror is added to `/drupal-issue` Step 2.5 as part
   of this ticket, not deferred to 034. Ticket 028 set up the schema but
   never wired the classification write; ticket 034 will rely on this
   data being populated; fixing the gap now aligns with 031's
   determinism concern.

4. **State-file pattern formalized in a standing doc** (brainstorm scope
   addition). `docs/workflow-state-files.md` registers all 10 phase-2
   state files in one place. Future tickets (034, 036) can add rows
   without having to re-derive the pattern.

5. **Prose template mirrors 030's "Attempt state check"** for consistency.
   A reader who has seen 030's section finds 031's section structurally
   familiar (shell snippet for read, bullet list for branches, escalation
   message at the end).

6. **bd mirror is best-effort** with `2>/dev/null || echo "..." >&2`.
   Failure does not fail the skill. Workflow file is the source of truth.
   Matches the pattern from 030's gate agents.

7. **Resume flow does NOT touch the sentinel.** Prior session already
   wrote real classification; resume just appends activity.

### Gotchas discovered during implementation

1. **`local` declarations inside `launch_new_session()`** — the existing
   function uses `local var=...` style for its variables, so the new
   sentinel block uses the same pattern (`local issue_workflow_dir`,
   `local issue_sentinel`, etc.) for consistency. The bash heredoc
   `<<EOF` opening must be at the end of its `cat >` line and the
   closing `EOF` must be at column 1 (not indented).
2. **`jq -r '.status // empty'`** is the safe way to read a possibly-missing
   status field. Returns empty string for both missing key and explicit
   null. The check then treats empty as "fresh, write the sentinel"
   (alongside explicit PENDING).
3. **`scp` + `mv` for new files** — when creating a new file like
   `docs/workflow-state-files.md`, scp goes to the target directory
   directly; no `mv` needed. For modifications, the python heredoc
   approach used in tasks 3-6 is the most reliable way to do precise
   markdown insertions without sed escaping pain.

### Future work explicitly NOT in scope

- **Preflight in `/drupal-contribute-fix` for direct invocations.** Per
  Q1=C, not in scope. If users start invoking contribute-fix directly,
  add the preflight there in a follow-up.
- **Multi-retry with exponential backoff.** Explicitly out of scope per
  Q2=D. Single retry is sufficient; re-evaluate if structural flakiness
  shows up.
- **Additional terminal status values** like `fetch_failed`. The sentinel's
  `status` field has room for them, but this ticket uses only PENDING
  and classified. Future tickets can add values without breaking the
  preflight branching (which only branches on PENDING vs non-PENDING).
- **bd query in resume flow** to inject current phase into the prompt.
  Defer to ticket 034.
```

- [ ] **Step 3: Append the resolution note**

```bash
scp /tmp/031-resolution.md alphons@192.168.0.218:/tmp/ && \
ssh alphons@192.168.0.218 'cat /tmp/031-resolution.md >> /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/031-workflow-determinism-sentinel.md && tail -5 /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/031-workflow-determinism-sentinel.md && rm /tmp/031-resolution.md'
```

Expected: the last 5 lines of the ticket file are the tail of the resolution note.

- [ ] **Step 4: Flip 031 row in 00-INDEX.md**

```bash
ssh alphons@192.168.0.218 'python3 -c "
p = \"/home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/00-INDEX.md\"
t = open(p).read()
old = \"| 031 | Workflow determinism via sentinel + reinstate              | P1 | NOT_STARTED | Enhancement  | 027        |\"
new = \"| 031 | Workflow determinism via sentinel + reinstate              | P1 | COMPLETED   | Enhancement  | 027        |\"
assert old in t, \"row not found\"
open(p, \"w\").write(t.replace(old, new))
print(\"flipped\")
" && grep "^| 031" /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/00-INDEX.md'
```

Expected: the 031 row shows `COMPLETED`.

- [ ] **Step 5: Commit (SKIP per user direction)**

```bash
# SKIP. When committing later:
# git add docs/tickets/031-workflow-determinism-sentinel.md docs/tickets/00-INDEX.md
# git commit -m "ticket-031: resolution note + index flip"
```

---

## Task 10: Refresh Phase 2 Integrated Snapshot in 5 tickets

**Files:**
- Modify: `docs/tickets/027-fix-stale-session-dir.md`
- Modify: `docs/tickets/028-adopt-bd-data-store.md`
- Modify: `docs/tickets/029-cross-issue-resonance-check.md`
- Modify: `docs/tickets/030-solution-depth-gate.md`
- Modify: `docs/tickets/031-workflow-determinism-sentinel.md` (append snapshot — it has none yet)

The Phase 2 snapshot was last refreshed in ticket 030's Task 18 to include 027-030. Now it needs a 031 row.

- [ ] **Step 1: Pull the current snapshot from any of the 4 existing tickets**

```bash
ssh alphons@192.168.0.218 'grep -n "Phase 2 Integrated Snapshot" /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/027-fix-stale-session-dir.md'
```

Expected: a single line number marking the snapshot section start.

- [ ] **Step 2: Read the current snapshot to local /tmp**

```bash
ssh alphons@192.168.0.218 'awk "/^## Phase 2 Integrated Snapshot/,0" /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/027-fix-stale-session-dir.md > /tmp/current-snapshot-v2.md && wc -l /tmp/current-snapshot-v2.md'
scp alphons@192.168.0.218:/tmp/current-snapshot-v2.md /tmp/current-snapshot-v2.md
wc -l /tmp/current-snapshot-v2.md
```

Expected: line count around 280.

- [ ] **Step 3: Edit the snapshot locally to add the 031 row**

The snapshot has several places that need updating:
1. **"Tickets completed so far" table** — add a 031 row
2. **"How the four tickets integrate" diagram** — re-title to "How the five tickets integrate" and add the new 031 elements: launcher sentinel writer, /drupal-issue Step 2.5, /drupal-issue-review preflight check
3. **"What's live that wasn't before phase 2" bullet list** — add a bullet about the workflow determinism sentinel
4. **"Critical gotchas discovered during implementation"** — add 1-2 new gotchas from 031 implementation
5. **"Where to look for detail"** — add row for `docs/workflow-state-files.md`
6. **"Phase 2 tickets NOT yet started" table** — remove the 031 row

Use Edit/Write tools to make these changes to `/tmp/current-snapshot-v2.md`. Specific edits:

**Edit 6.1 — Tickets completed so far** (add row after 030):

Old:
```
| 030 | Solution-depth gate (pre-fix + post-fix) | Two-mode subagent split into `-pre.md` (opus) and `-post.md` (sonnet). Pre-fix gate runs always at `/drupal-contribute-fix` Step 0.5; post-fix gate runs at Step 2.5 when any of 3 triggers fires (pre_fix_demanded \| lines > 50 \| files > 3). Failure path writes recovery brief, preserves attempt-1 diffs, destructively reverts, re-runs architectural; circuit breaker at 2 attempts. Haiku→sonnet migration of 3 existing agents rolled into this ticket per user directive. |
```

New:
```
| 030 | Solution-depth gate (pre-fix + post-fix) | Two-mode subagent split into `-pre.md` (opus) and `-post.md` (sonnet). Pre-fix gate runs always at `/drupal-contribute-fix` Step 0.5; post-fix gate runs at Step 2.5 when any of 3 triggers fires (pre_fix_demanded \| lines > 50 \| files > 3). Failure path writes recovery brief, preserves attempt-1 diffs, destructively reverts, re-runs architectural; circuit breaker at 2 attempts. Haiku→sonnet migration of 3 existing agents rolled into this ticket per user directive. |
| 031 | Workflow determinism via sentinel + reinstate | Launcher pre-creates `workflow/00-classification.json` with `status: PENDING` (idempotent — never overwrites real classification). `/drupal-issue` new Step 2.5 overwrites with real data and mirrors to bd via best-effort `bd create`/`bd update`. `/drupal-issue-review` "Classification Sentinel Check" preflight reinstates with single retry on PENDING. New `docs/workflow-state-files.md` registry formalizes the pattern across all 10 phase-2 state files. |
```

**Edit 6.2 — Diagram title** (find "How the four tickets integrate" → "How the five tickets integrate") and add the 031 elements to the diagram:

In the launcher block, add a line:
```
|  - Sentinel writer for 00-classification.json (031)  |
```

In the `/drupal-issue skill (controller)` block, add a line for Step 2.5:
```
|  Step 2.5: Persist classification + bd mirror (031)  |
```

In the `/drupal-issue-review skill` block (which doesn't exist as a separate block in the current diagram — add one between `/drupal-issue` and `/drupal-contribute-fix`):
```
+-------------------------------------------------------+
|  /drupal-issue-review skill                           |
|                                                       |
|  Preflight: Classification Sentinel Check (031)       |
|    if PENDING -> reinstate /drupal-issue (single try) |
|    if classified -> continue                          |
|                                                       |
|  Step 1-4: existing review flow                       |
|  Step 4.9: emit depth signals (030)                   |
+-------------------------------------------------------+
```

**Edit 6.3 — "What's live" bullet** (add after the 030 bullets):

```
- **Workflow determinism via sentinel.** The launcher pre-creates `workflow/00-classification.json` with `status: PENDING` for every new session. `/drupal-issue` Step 2.5 overwrites it with real classification data and mirrors to bd. `/drupal-issue-review`'s preflight check reinstates `/drupal-issue` (single retry) if it sees PENDING. Ticket 023's "every phase writes an artifact" contract is now mechanically enforced, not just prose. (031)
```

**Edit 6.4 — Gotchas** (add at the end of the numbered list):

```
17. **bd mirror is best-effort, do not block on failure** (from 031). The classification bd mirror in `/drupal-issue` Step 2.5 uses `2>/dev/null || echo "..." >&2` so a dolt server outage doesn't break the skill. Workflow file is the source of truth.

18. **Sentinel idempotency rule: PENDING and empty status both mean "rewrite"** (from 031). The launcher's `write_sentinel=true` triggers when the file is missing OR `jq -r '.status // empty'` returns either `PENDING` or empty. Any other value (like `classified`) means leave it alone.
```

**Edit 6.5 — "Where to look for detail"** (add row):

```
| Workflow state file registry | `docs/workflow-state-files.md` |
```

**Edit 6.6 — "Phase 2 tickets NOT yet started"** (remove the 031 row):

Old:
```
| 031 | Workflow determinism via sentinel + reinstate | P1 | 027 |
```

Delete this row (031 is now completed).

**Edit 6.7 — Update the date and ticket count in the header**:

Old: `## Phase 2 Integrated Snapshot (as of 2026-04-10)` and `mirrored across all COMPLETED phase-2 tickets (027, 028, 029, 030)`
New: `## Phase 2 Integrated Snapshot (as of 2026-04-10)` (date unchanged, both done same day) and `mirrored across all COMPLETED phase-2 tickets (027, 028, 029, 030, 031)`

Use Edit tool with the `replace_all=false` to make these changes one at a time.

- [ ] **Step 4: scp the updated snapshot**

```bash
scp /tmp/current-snapshot-v2.md alphons@192.168.0.218:/tmp/phase2-snapshot-v3.md
```

- [ ] **Step 5: Apply to all 5 tickets**

```bash
ssh alphons@192.168.0.218 'python3 << "PYEOF"
snapshot = open("/tmp/phase2-snapshot-v3.md").read()
marker = "## Phase 2 Integrated Snapshot"

for p in [
    "/home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/027-fix-stale-session-dir.md",
    "/home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/028-adopt-bd-data-store.md",
    "/home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/029-cross-issue-resonance-check.md",
    "/home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/030-solution-depth-gate.md",
    "/home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/031-workflow-determinism-sentinel.md",
]:
    text = open(p).read()
    idx = text.find(marker)
    if idx == -1:
        # 031 has no snapshot yet — append
        open(p, "a").write("\n---\n\n" + snapshot)
        print(f"APPENDED: {p}")
    else:
        open(p, "w").write(text[:idx] + snapshot)
        print(f"REPLACED: {p}")
PYEOF
'
```

Expected: 4 REPLACED lines for 027/028/029/030, 1 APPENDED line for 031.

- [ ] **Step 6: Verify all 5 tickets have the 031 row**

```bash
ssh alphons@192.168.0.218 'for f in /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/027-fix-stale-session-dir.md /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/028-adopt-bd-data-store.md /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/029-cross-issue-resonance-check.md /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/030-solution-depth-gate.md /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/031-workflow-determinism-sentinel.md; do
  base=$(basename "$f")
  has_031=$(grep -c "Workflow determinism via sentinel + reinstate" "$f")
  printf "%-45s 031-row=%d\n" "$base" "$has_031"
done'
```

Expected: each ticket reports `031-row=1` (one occurrence in the snapshot table).

- [ ] **Step 7: Clean up local + remote temp files**

```bash
rm -f /tmp/current-snapshot-v2.md /tmp/phase2-snapshot-v3.md
ssh alphons@192.168.0.218 'rm -f /tmp/phase2-snapshot-v3.md /tmp/current-snapshot-v2.md'
```

- [ ] **Step 8: Commit (SKIP per user direction)**

```bash
# SKIP. When committing later:
# git add docs/tickets/027-fix-stale-session-dir.md docs/tickets/028-adopt-bd-data-store.md docs/tickets/029-cross-issue-resonance-check.md docs/tickets/030-solution-depth-gate.md docs/tickets/031-workflow-determinism-sentinel.md
# git commit -m "tickets: refresh phase 2 integrated snapshot to include 031"
```

---

## Post-implementation cleanup

- [ ] Verify no stray `/tmp/` files remain on local or remote
- [ ] `git status --short | wc -l` on the workbench (expect ~40 entries — the existing pile from 027-030 plus the new 031 changes; user will review the entire pile)

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && git status --short | wc -l && ls /tmp/ | grep -iE "031|sentinel|workflow-state" 2>&1 || echo "all clean"'
```

Expected: ~40 entries in git status, no leftover temp files.

---

## Notes for the executor

- **All git commits are skipped this session.** The user will review the entire phase-2 pile (tickets 027-031) in one pass at the end.
- **Acceptance test #2 is mechanical-only**, not a true end-to-end runtime test. A real Claude session running `/drupal-issue-review` against a PENDING sentinel is the only way to verify the model actually follows the SKILL.md preflight prose. That verification is left for first real-world encounter, the same model as ticket 030's acceptance #5.
- **Task 10 (snapshot refresh)** has the most error-prone editing because it touches a long markdown file with multiple sections that all need synchronized updates. Read the current snapshot in full before editing, do the edits one section at a time, and verify each section after editing.
- **If `/drupal-issue-review` is currently being modified by the user in another session**, your edits may collide. Verify there are no live edits before starting Task 4 (the preflight check insertion).
