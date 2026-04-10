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
| `03-push-gate-checklist.json` | `/drupal-contribute-fix` Step 5.5 | (no status; verdicts checked by hooks) | `.claude/hooks/push-gate.sh` + `.claude/hooks/workflow-completion.sh` | 039 |

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
