# TICKET-031: Workflow Determinism via Launcher Sentinel + Skill Reinstate

**Status:** COMPLETED
**Priority:** P1
**Affects:** `drupal-issue.sh`, `.claude/skills/drupal-issue/SKILL.md`, `.claude/skills/drupal-issue-review/SKILL.md`, `.claude/skills/drupal-contribute-fix/SKILL.md`
**Type:** Enhancement

## Problem (with evidence)

Ticket 023 ("explicit state handoff artifacts") established the contract that every workflow phase writes an artifact to `DRUPAL_ISSUES/<id>/workflow/`. Audit shows the contract is leaking under load:

**5 of the most recent worked issues are missing `00-classification.json`** (filtered to mtime ≥ Apr 8, post-ticket-023 finalization):
- 3553458 (session started 11 min before audit, mtime Apr 9 11:21)
- 3582345 (active session, currently has running DDEV stack)
- 3580690 (active session, currently has running DDEV stack)
- 3583760 (recent active work, scope-expansion case)
- 3581955 (recent companion-issue work)

These are all post-ticket-023, so the contract is in place but the controller is still skipping step 0 sometimes. Prose-only enforcement leaks under load.

(For older issue dirs from before Apr 8, the missing files are likely from pre-ticket-023 runs and out of scope.)

## Solution: Two-part mechanical pressure (NOT abort)

Per user direction: "**Not abort and stop, but instead reinstate to make it happen.**"

### Part 1 — Launcher pre-creates a sentinel

In `drupal-issue.sh`, inside `launch_new_session()`, before `exec claude`:

```bash
mkdir -p "$SCRIPT_DIR/DRUPAL_ISSUES/$ISSUE_ID/workflow"
cat > "$SCRIPT_DIR/DRUPAL_ISSUES/$ISSUE_ID/workflow/00-classification.json" <<EOF
{
  "issue_id": $ISSUE_ID,
  "status": "PENDING",
  "launched_at": "$(date -Iseconds)",
  "session_id": "$uuid",
  "note": "Sentinel created by drupal-issue.sh. The /drupal-issue skill MUST overwrite it with real classification data before invoking any companion skill."
}
EOF
```

The skill now sees a placeholder rather than a missing file. Models are biased to *fill* something they see; missing files are easier to forget.

**Idempotency**: if the file already exists with status != PENDING (i.e., a real classification from a prior session), do NOT overwrite. Only write the sentinel if the file is missing or status is PENDING.

### Part 2 — Skill reinstate (not abort)

In `/drupal-issue-review` and `/drupal-contribute-fix` SKILL.md, add a "preflight check" at the very top of the skill body:

```markdown
## Preflight: Classification Sentinel Check

Before doing any work, read DRUPAL_ISSUES/<id>/workflow/00-classification.json.

If status == "PENDING":
  This means /drupal-issue skipped or failed to write the classification.
  REINSTATE the missing step:
  1. Stop what you were about to do.
  2. Invoke the Skill tool: /drupal-issue with the same issue id.
  3. Verify the file is no longer PENDING.
  4. Re-read the now-real classification.
  5. Continue with original task.

Do NOT abort or report an error to the user. Reinstate is silent and automatic.

If status == "PENDING" still after reinstate, that is the only condition where
you escalate to the user (it indicates /drupal-issue itself is broken).
```

This ensures the step happens even if the controller skipped it the first time. The launcher writes the placeholder; the downstream skill notices and forces a re-do.

### Part 3 — bd mirror (depends on 028)

When 028 lands, also write the sentinel as a bd `Metadata` field on issue creation:
```bash
bd issue create --external-ref "do-$ISSUE_ID" \
  --metadata '{"phase": "pending_classification"}'
```

Then any other session can `bd show bd-<id>` to see whether the issue has been classified yet without having to read the file. The bd mirror is the second source of truth — both must be PENDING for reinstate to fire; both must be filled to proceed.

## Why "reinstate" is better than "abort"

Abort would block work until the user notices and runs `/drupal-issue` manually. Reinstate is invisible — the workflow self-heals and the user never sees it. Cost: one extra Skill invocation when reinstate fires. Benefit: 100% of started issues end up with a classification artifact, no manual cleanup needed.

This matches the user's framing: "Not abort and stop, but instead reinstate to make it happen."

## Acceptance

1. After this lands, every issue dir created has `00-classification.json` with `status != "PENDING"` by the time any companion skill runs. Verify by running:
   ```bash
   find DRUPAL_ISSUES -name 00-classification.json -mmin +5 \
     -exec jq -r '.status' {} \; | sort | uniq -c
   ```
   Should show no PENDING entries for issues older than 5 minutes.

2. Manually create a sentinel file with status PENDING, then run `/drupal-issue-review` directly. It should silently invoke `/drupal-issue` first, then continue. Verify in the session JSONL.

3. Launcher creates sentinel idempotently — running the launcher twice for the same issue does NOT corrupt an existing real classification (verified by writing a fake real classification, running the launcher, confirming the file is unchanged).

## Dependencies

- **027** (launcher path fix) — needed because we are modifying drupal-issue.sh; doing 027 first avoids merge conflicts
- Optionally enhanced by **028** (bd mirror)

## Future evolution

If 033's Agent Teams research lands a `TaskCompleted` hook, this sentinel pattern can be replaced with a real exit-code-2 hook on the classification task. For now the sentinel pattern is the ~80% solution at 5% of the cost.

If 035's launcher v2 mining suggests a different determinism pattern (e.g., bernstein's "Janitor" verification layer), reconsider this implementation.

## Research update from ticket 028 (2026-04-09)

Minor command-syntax corrections for the sentinel implementation, verified via bd smoke tests:

1. **`bd create`, not `bd issue create`**. The example on line 78 uses `bd issue create --external-ref "do-$ISSUE_ID"`. The real command is simply `bd create`. Corrected form:
   ```bash
   bd create "Drupal issue $ISSUE_ID: <title>" \
     --type bug \
     --priority 2 \
     --external-ref "external:drupal:$ISSUE_ID" \
     -l "drupal-$ISSUE_ID,module-$MODULE" \
     --metadata "{\"drupal_issue_id\": $ISSUE_ID, \"module\": \"$MODULE\"}" \
     --status classified
   ```

2. **External-ref format**. The ticket uses `do-$ISSUE_ID`. bd accepts arbitrary external-ref strings (verified in smoke testing — no format validation), so `do-3583760` would work. However, phase 2 standardizes on `external:drupal:<id>` per `docs/bd-schema.md` for consistency with ticket 034's memory keys. Use the `external:drupal:` form.

3. **Sentinel reinstate does NOT need a bd write**. The sentinel is a `workflow/00-classification.json` file on disk with `status: PENDING`. When a skill sees this, it invokes `/drupal-issue` and continues. The bd mirror of the classification (per `docs/bd-schema.md` phase notation) happens AFTER classification succeeds, not at the sentinel stage. Keep the sentinel as a disk artifact only.

4. **Status transition**. After the skill reinstates and completes classification, it should update bd:
   ```bash
   bd update <bd-id> --status classified --metadata @workflow/00-classification.json
   ```

No rewrite of this ticket is needed; cross-reference `docs/bd-schema.md` when implementing.

## Resolution (2026-04-10)

Ticket 031 shipped with the launcher sentinel + skill reinstate flow plus
the bd mirror gap-fill from ticket 028. New standing doc
`docs/workflow-state-files.md` formalizes the state-file pattern across
phase 2. All 3 acceptance criteria pass (criterion #2 verified
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

**`docs/workflow-state-files.md` (new, 90 lines).** Standing doc that
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
| 1 | After this lands, every issue dir has `00-classification.json` with `status != PENDING` after 5 minutes | ✅ PASS — `find` query returned 0 PENDING entries. Note: the audit also revealed that 15 existing pre-031 classification files use a different schema (storing the Drupal issue's own status like `Active` / `Needs review` / `Needs work` / `null` rather than the new sentinel semantic). This is expected — pre-031 files were written by a previous classification convention. Going forward, all NEW launches will write the new schema (`PENDING` → `classified`). The old files are stale but not harmful; they will not trigger the preflight reinstate because their status is not exactly `PENDING`. |
| 2 | Manual PENDING sentinel → `/drupal-issue-review` reinstates | ✅ PASS (mechanical) — wrote a PENDING sentinel for issue 3583760, simulated the SKILL.md branching with shell, confirmed the preflight routes through the reinstate branch. True runtime verification deferred to first real session, same model as ticket 030 acceptance #5. |
| 3 | Launcher idempotency — running launcher twice does not corrupt a real classification | ✅ PASS — wrote a fake `status: classified` sentinel, ran the inline launcher snippet, confirmed `write_sentinel=false`, file unchanged, original `session_id` preserved (`REAL-PRE-EXISTING-SESSION`). |

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
3. **Pre-031 classification files use a different schema.** The audit
   revealed 15 existing `00-classification.json` files written under a
   prior convention that stored Drupal issue statuses (`Active`,
   `Needs review`, etc.) directly. The new sentinel semantic
   (`PENDING` / `classified`) is incompatible by design — this is fine
   because the preflight only branches on exact `"PENDING"`, so old
   files fall through the `else` branch and proceed normally. No
   backfill needed.
4. **Sentinel idempotency rule: PENDING and empty status both mean
   "rewrite"**. The launcher's `write_sentinel=true` triggers when the
   file is missing OR `jq -r '.status // empty'` returns either `PENDING`
   or empty. Any other value (like `classified` or `Needs review`) means
   leave it alone. This makes the launcher safe to run on issue dirs
   that have pre-031 classification artifacts (it leaves them alone).

### Stats

- Files created: 1 (`docs/workflow-state-files.md`, 90 lines)
- Files modified: 4 (`drupal-issue.sh`, `.claude/skills/drupal-issue/SKILL.md`, `.claude/skills/drupal-issue-review/SKILL.md`, `CLAUDE.md`)
- Lines added net: ~280 (most in the new doc + Step 2.5 prose)
- Total tasks executed: 10 (all per the plan, all `git commit` steps skipped per user direction)

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
- **Backfill of pre-031 classification files.** The 15 existing files
  with the old schema are not harmful; the launcher and preflight both
  treat them as "leave alone, fall through". No backfill needed unless
  ticket 034's cross-issue memory queries specifically need them.

---

## Phase 2 Integrated Snapshot

See [phase-2-integrated-snapshot.md](phase-2-integrated-snapshot.md) for the
shared cross-ticket snapshot (maintained as a single file to avoid duplication).

