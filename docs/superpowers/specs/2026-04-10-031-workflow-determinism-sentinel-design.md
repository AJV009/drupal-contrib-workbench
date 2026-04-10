# Design: Workflow Determinism via Sentinel + Reinstate (Ticket 031)

**Date:** 2026-04-10
**Ticket:** `docs/tickets/031-workflow-determinism-sentinel.md`
**Status:** Design approved, ready for implementation plan
**Phase:** Phase 2.4 (Workflow improvements)

## Problem

Ticket 023 established the contract that every workflow phase writes an
artifact to `DRUPAL_ISSUES/<id>/workflow/`. Audit shows the contract is
leaking under load: **5 of the most recent worked issues are missing
`00-classification.json`** despite being post-ticket-023. Prose-only
enforcement doesn't hold when the model is under pressure or mid-chain.

## Solution summary

Two-part mechanical pressure that does NOT abort on failure (per user
direction: "not abort and stop, but instead reinstate to make it
happen"):

1. **Launcher pre-creates a sentinel** — `drupal-issue.sh` writes
   `workflow/00-classification.json` with `status: "PENDING"` before
   exec'ing claude. Idempotent: only writes if file is missing or has
   status PENDING; never overwrites a real classification.

2. **Skill reinstate at the top of `/drupal-issue-review`** — reads the
   sentinel; if `status == "PENDING"`, invokes `/drupal-issue` to force
   classification, re-reads, and continues. Single retry only; if still
   PENDING after the retry, FATAL escalation to user.

3. **bd mirror at end of `/drupal-issue` Step 2** — after the real
   classification JSON is written, mirror it into bd via `bd create` (if
   the bd issue doesn't exist yet) or `bd update` (if it does),
   best-effort. This fills a gap left by ticket 028 where the schema was
   set up but the classification write was never wired in.

This is the same architectural pattern as ticket 030's `attempt.json`
flow (state file + preflight check + re-invoke), applied to a different
concern. A new standing doc `docs/workflow-state-files.md` formalizes the
pattern so future tickets (034+) can add state files consistently.

## Architecture

```
drupal-issue.sh
    │
    ├─ launch_new_session() gains a new step BEFORE exec claude:
    │   Pre-create workflow/00-classification.json with status=PENDING
    │   (idempotent: only if file is missing OR existing status is PENDING)
    │
    v  exec claude "/drupal-issue ..."
+---------------------------------------------------------------+
|  /drupal-issue skill                                          |
|                                                               |
|  Step 0:   drupal-issue-fetcher (existing)                    |
|  Step 0.5: drupal-resonance-checker (existing, 029)           |
|  Step 1:   Read the issue (existing)                          |
|  Step 2:   Classify (existing prose)                          |
|  Step 2.5: Persist classification + bd mirror (NEW)           |
|              - Overwrite workflow/00-classification.json      |
|                with real data (status = classified)           |
|              - Preserve launched_at + session_id from sentinel|
|              - bd create|update --status classified           |
|                --metadata @00-classification.json             |
|              - bd writes are best-effort                      |
|  Step 3:   Take action — chains to review/contribute-fix      |
+---------------------------------------------------------------+
                    │
                    v auto-chain
+---------------------------------------------------------------+
|  /drupal-issue-review skill                                   |
|                                                               |
|  NEW FIRST STEP: Classification sentinel check (MANDATORY)    |
|    Read workflow/00-classification.json                       |
|    Branch on status:                                          |
|      - file missing: treat as fresh run, continue             |
|      - "classified" (or any terminal state): continue         |
|      - "PENDING": REINSTATE                                   |
|          1. Invoke Skill: /drupal-issue with the issue id     |
|          2. Re-read sentinel                                  |
|          3. If still PENDING: FATAL escalation, stop          |
|          4. Otherwise continue                                |
|    Single retry only — no counter, no state flag              |
|                                                               |
|  Before You Begin (existing)                                  |
|  Step 1-5: (existing)                                         |
+---------------------------------------------------------------+
```

Nothing is added to `/drupal-contribute-fix` or `/drupal-issue-comment`.
Only `/drupal-issue-review` gets the preflight check, because it is the
first downstream skill in the auto-chain. Once review reinstates, the
classification is guaranteed present for any further chain hop.

## Components

### 1. Sentinel file format

`DRUPAL_ISSUES/{id}/workflow/00-classification.json` — two states:

**PENDING state** (written by launcher):

```json
{
  "issue_id": 3582345,
  "status": "PENDING",
  "launched_at": "2026-04-10T14:23:11+02:00",
  "session_id": "0f3a9c48-b2d1-4e7f-a1c3-123456789abc",
  "note": "Sentinel created by drupal-issue.sh. The /drupal-issue skill MUST overwrite it with real classification data before invoking any companion skill."
}
```

**Classified state** (written by `/drupal-issue` Step 2.5):

```json
{
  "issue_id": 3582345,
  "status": "classified",
  "launched_at": "2026-04-10T14:23:11+02:00",
  "session_id": "0f3a9c48-b2d1-4e7f-a1c3-123456789abc",
  "classified_at": "2026-04-10T14:24:37+02:00",
  "category": "E",
  "category_description": "Respond to reviewer feedback",
  "module": "ai",
  "module_version": "1.4.x-dev",
  "component": "AI CKEditor",
  "existing_mr": {"iid": 1425, "source_branch": "1.4.x", "apply_clean": null},
  "rationale": "Maintainer asked for a deeper look at the architectural question raised in comment 8."
}
```

Field purposes:
- `issue_id` — redundant with directory path but useful for bd joins
- `status` — `PENDING` (sentinel) or `classified` (after Step 2.5). Other
  terminal values are reserved for future (e.g., `fetch_failed`) but NOT
  introduced in this ticket.
- `launched_at` — ISO-8601 with timezone from `date -Iseconds`; used in
  the 5-minute audit query and as diagnostic delta signal.
- `session_id` — UUID assigned by the launcher, for cross-referencing the
  Claude session JSONL.
- `classified_at` — set by `/drupal-issue` Step 2.5. `classified_at` minus
  `launched_at` is diagnostic: fast classifications = model on-task;
  multi-minute deltas = something slow.
- `note` — reinstate hint visible to the model when it reads the file.
- Classification fields (`category`, `module`, etc.) are sourced from
  what the skill already gathers during Step 1-2.

### 2. Launcher change — `drupal-issue.sh`

Add inside `launch_new_session()` BEFORE `exec claude`:

```bash
# --- Sentinel: pre-create workflow/00-classification.json with status=PENDING ---
ISSUE_WORKFLOW_DIR="$SCRIPT_DIR/DRUPAL_ISSUES/$ISSUE_ID/workflow"
ISSUE_SENTINEL="$ISSUE_WORKFLOW_DIR/00-classification.json"
mkdir -p "$ISSUE_WORKFLOW_DIR"

# Idempotency: only write the sentinel if the file is missing, OR if it exists
# but has status=PENDING (meaning the previous session was killed before
# /drupal-issue could overwrite it). Never overwrite a real classification.
WRITE_SENTINEL=false
if [ ! -f "$ISSUE_SENTINEL" ]; then
  WRITE_SENTINEL=true
else
  EXISTING_STATUS=$(jq -r '.status // empty' "$ISSUE_SENTINEL" 2>/dev/null || echo "")
  if [ "$EXISTING_STATUS" = "PENDING" ] || [ -z "$EXISTING_STATUS" ]; then
    WRITE_SENTINEL=true
  fi
fi

if [ "$WRITE_SENTINEL" = "true" ]; then
  cat > "$ISSUE_SENTINEL" <<EOF
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

`resume_session()` does NOT touch the sentinel — the prior session
already wrote real classification data.

### 3. `/drupal-issue-review` preflight section

Inserted at the very top of the SKILL.md body (before "Before You Begin"),
mirroring the structural template of ticket 030's "Attempt state check"
for consistency:

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

This indicates /drupal-issue itself is not completing Step 2.
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

### 4. `/drupal-issue` Step 2.5 — persist + bd mirror

Inserted after the existing Step 2 classification prose, before Step 3
"Take action":

```markdown
### Step 2.5: Persist classification (MANDATORY)

After deciding the category and gathering the metadata, write the
classification artifact and mirror it to bd. The disk write is required;
the bd mirror is best-effort (failure does not fail the skill).

#### Write the classification artifact

```bash
mkdir -p DRUPAL_ISSUES/{issue_id}/workflow

# Preserve launched_at and session_id from the sentinel if present
SENTINEL="DRUPAL_ISSUES/{issue_id}/workflow/00-classification.json"
LAUNCHED_AT=""
SESSION_ID=""
if [ -f "$SENTINEL" ]; then
  LAUNCHED_AT=$(jq -r '.launched_at // ""' "$SENTINEL")
  SESSION_ID=$(jq -r '.session_id // ""' "$SENTINEL")
fi

cat > "$SENTINEL" <<JSON
{
  "issue_id": {issue_id},
  "status": "classified",
  "launched_at": "$LAUNCHED_AT",
  "session_id": "$SESSION_ID",
  "classified_at": "$(date -Iseconds)",
  "category": "{A-J}",
  "category_description": "{one-line description from the action table}",
  "module": "{machine name}",
  "module_version": "{version}",
  "component": "{component name or null}",
  "existing_mr": {"iid": {iid_or_null}, "source_branch": "...", "apply_clean": null},
  "rationale": "{1-2 sentences explaining the classification decision}"
}
JSON
```

#### Mirror to bd (best-effort)

```bash
BD_ID=$(bd list --external-ref "external:drupal:{issue_id}" --format json 2>/dev/null | jq -r '.[0].id // empty')

if [ -z "$BD_ID" ]; then
  bd create "Drupal issue {issue_id}: {title}" \
    --type bug \
    --priority 2 \
    --external-ref "external:drupal:{issue_id}" \
    -l "drupal-{issue_id},module-{module}" \
    --metadata "@DRUPAL_ISSUES/{issue_id}/workflow/00-classification.json" \
    --status classified 2>/dev/null || true
else
  bd update "$BD_ID" \
    --status classified \
    --metadata "@DRUPAL_ISSUES/{issue_id}/workflow/00-classification.json" 2>/dev/null || true
fi
```

Best-effort means: if bd is unreachable (config issue, dolt server down,
network flake), log to stderr via `|| true` and continue. Workflow file
is the source of truth; bd is the queryability layer (ticket 034 relies
on this data being populated).
```

### 5. New standing doc — `docs/workflow-state-files.md`

```markdown
# Workflow State Files

The `DRUPAL_ISSUES/<id>/workflow/` directory holds phase artifacts and
state files that drive self-healing reinstate flows. Each state file has
an owner skill and (where applicable) a preflight-check location.

## Registry

| File | Owner skill | Status field | Preflight location | Ticket |
|---|---|---|---|---|
| `00-classification.json` | `/drupal-issue` Step 2.5 | `PENDING` \| `classified` | `/drupal-issue-review` "Classification Sentinel Check" | 031 |
| `00-resonance.{md,json}` | `/drupal-issue` Step 0.5 (resonance checker) | (no status; presence = done) | — (informational) | 029 |
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
(invoke the upstream skill) rather than abort.

Reinstate attempts are bounded per state file:
- `00-classification.json`: **single retry**, then escalate. Classification
  is idempotent; looping won't fix a broken `/drupal-issue`.
- `attempt.json`: **max 2 attempts** (one narrow + one architectural),
  then circuit breaker escalation.

## Conventions for new state files

When a future ticket introduces a new state file:

1. Place it under `DRUPAL_ISSUES/<id>/workflow/` with a numeric prefix
   matching the workflow phase (`00-`, `01-`, `02-`, etc.).
2. If the file drives a reinstate, include a `status` (or semantically
   equivalent) field with an explicit "incomplete" value.
3. Document the owner skill and preflight location by adding a row to
   the registry table above.
4. Prefer SKILL.md prose for the preflight check; avoid external scripts
   unless the logic is non-trivial (like `depth_gate_triggers.py`).
5. If the reinstate could loop, document the max retry count and the
   escalation message template.
6. Best-effort bd mirrors go in the owner skill's step that completes the
   phase, not in the preflight check itself.

## Relationship to bd

State files are the source of truth. bd mirrors (when present) are the
queryability layer for cross-session and cross-issue lookups. If the two
diverge, trust the file. bd writes are best-effort and may fail silently
when the dolt server is down; that's by design.
```

## Files created

1. `docs/workflow-state-files.md` — new standing doc (~80 lines)

## Files modified

1. `drupal-issue.sh` — sentinel writer in `launch_new_session()` (~25 lines added)
2. `.claude/skills/drupal-issue/SKILL.md` — new Step 2.5 (classification persist + bd mirror) (~70 lines added)
3. `.claude/skills/drupal-issue-review/SKILL.md` — new "Classification Sentinel Check" section at top (~60 lines added)
4. `CLAUDE.md` — short pointer to `docs/workflow-state-files.md` near the Solution Depth Gate section
5. `docs/tickets/031-workflow-determinism-sentinel.md` — status flip + Resolution note
6. `docs/tickets/00-INDEX.md` — flip 031 to COMPLETED
7. `docs/tickets/027/028/029/030-*.md` — Phase 2 snapshot refresh to include 031

## Files NOT touched (deliberate scope exclusions)

- `.claude/skills/drupal-contribute-fix/SKILL.md` — preflight lives in review only (Q1=C)
- `.claude/skills/drupal-issue-comment/SKILL.md` — same
- `docs/bd-schema.md` — `bd:phase.classification` is already present; this ticket USES it but doesn't add new notation prefixes

## Acceptance criteria

Mapping to the ticket's original 3 criteria:

| # | Requirement | Verification |
|---|---|---|
| 1 | Every issue dir has `00-classification.json` with `status != PENDING` after 5 minutes | Run `find DRUPAL_ISSUES -name 00-classification.json -mmin +5 -exec jq -r '.status' {} \; \| sort \| uniq -c`. Expected: 0 PENDING entries. Note: pre-ticket-031 issue dirs may have no sentinel at all, which is fine — the check only flags PENDING, not missing. |
| 2 | Manual PENDING sentinel → `/drupal-issue-review` reinstates | On an issue with existing artifacts (e.g., 3583760), manually write a sentinel with `status: PENDING`. Directly invoke `/drupal-issue-review 3583760`. Verify: the preflight invokes `/drupal-issue`, sentinel flips to `classified`, review continues. Observable in session JSONL as a nested `/drupal-issue` call inside `/drupal-issue-review`. |
| 3 | Launcher sentinel idempotency | Write a fake real classification (`status: classified`, full fields) for an issue, run `./drupal-issue.sh <id>`, confirm the real classification is unchanged. Then manually set status back to PENDING and re-run the launcher — confirm the sentinel is rewritten (launched_at/session_id refreshed). |

## Design decisions locked in

1. **Preflight check lives in `/drupal-issue-review` only** (brainstorm
   Q1=C). `/drupal-contribute-fix` and `/drupal-issue-comment` are always
   chained from review, so review self-healing covers the full chain.
   Rejected option: replicating the check in all three skills.

2. **Single retry, no counter** (brainstorm Q2=D). No attempt-tracking
   field in the sentinel. If one reinstate doesn't fix it, the problem is
   structural and the user must investigate. Simpler than 030's
   `current_attempt` tracking because `/drupal-issue` classification is
   idempotent.

3. **bd writes bundled into this ticket** (brainstorm Q3=A). The
   classification bd mirror is added to `/drupal-issue` Step 2.5 as part
   of this ticket, not deferred to 034. Reason: ticket 028 set up the
   schema but never wired the classification write; 034 relies on this
   data being populated; fixing the gap now aligns with 031's
   determinism concern.

4. **`docs/workflow-state-files.md` as a new standing doc**
   (brainstorm Q-scope=C). Formalizes the state-file + preflight +
   reinstate pattern first introduced by ticket 030's `attempt.json`.
   Registry table lists all known state files across 029/030/031, with
   owners and preflight locations. Future tickets can add rows.

5. **Prose template mirrors 030's "Attempt state check"** for consistency.
   A reader who has seen 030's section should find 031's section
   structurally familiar (shell snippet for read, bullet list for
   branches, escalation message template at the end).

6. **bd mirror is best-effort with `2>/dev/null || true`**. Failure does
   not fail the skill. Workflow file is the source of truth. Matches the
   pattern from 030's gate agents.

7. **Resume flow (`resume_session()`) does NOT touch the sentinel.** The
   prior session already wrote the real classification; resume just
   appends activity to the same session.

8. **Empty sentinel file is treated as "fresh run, no reinstate"** in the
   preflight. If a user invokes `/drupal-issue-review` directly without
   the launcher, there's no sentinel and the skill falls through to
   normal review. This handles direct-invocation cases gracefully.

## Open risks

- **False-PENDING during legitimate interruption.** If a user hits Ctrl+C
  mid-classification, the next session's launcher sees `status: PENDING`
  and overwrites the sentinel (refresh `launched_at`). The skill then
  reinstates correctly. Not a real risk — the desired behavior is
  self-healing regardless of why the prior session left PENDING.
- **Single-retry fatalism.** If `/drupal-issue` has a flaky failure mode
  (e.g., fetcher timeout once but succeeds on retry), we'll escalate too
  fast. Mitigation: if this shows up in practice, upgrade to a 2-retry
  bound later. Doesn't require changes to the sentinel format.
- **Direct-invocation review has no classification.** If a user invokes
  `/drupal-issue-review` directly on an issue dir with no sentinel, the
  preflight falls through (as designed). Review proceeds without a
  classification record. This is fine because the user explicitly chose
  to skip the controller. Not a regression.

## Out of scope (future work)

- **`fetch_failed` and other terminal error states.** The sentinel's
  `status` field has room for values beyond `PENDING` and `classified`,
  but this ticket only uses those two. If a future ticket needs to
  represent fetcher failures or permission denials, it can add values
  without breaking the preflight check (which only branches on PENDING
  vs non-PENDING).
- **Preflight in `/drupal-contribute-fix`** for direct invocations. Per
  Q1=C, not in scope. If users later start invoking contribute-fix
  directly, revisit.
- **Multi-retry with exponential backoff.** Explicitly out of scope per
  Q2=D. Single retry is sufficient; re-evaluate if structural flakiness
  shows up.
- **bd query for resume flow**. A future ticket could make the launcher's
  `resume_session()` check bd for the current phase of the issue and
  inject it into the prompt. Not needed for determinism; defer to 034.
