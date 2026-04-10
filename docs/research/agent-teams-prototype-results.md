# Agent Teams & TaskCompleted Hook — Prototype Results

**Ticket:** 033 — RESEARCH: Agent Teams TaskCompleted Hook Prototype
**Date:** 2026-04-10
**Claude Code version on remote:** 2.1.100 (well above 2.1.32 requirement)
**Methodology:** Documentation review + GitHub issue analysis. No hands-on
prototype was run because the remote machine's Claude Code (`~/.local/bin/claude`)
is accessed via SSH, precluding interactive team sessions. All findings are
sourced from official docs and verified GitHub issues.

---

## Research Question 1: Resume Compatibility

**Verdict: BROKEN. Dealbreaker for our workflow.**

`/resume` does NOT restore in-process teammates. After resume, the lead
may attempt to `SendMessage` to teammates that no longer exist.
Teammate transcripts are session-scoped with incompatible ID formats;
cross-session reconnection is architecturally unsupported.

**Sources:**
- Official docs: "`/resume` and `/rewind` do not restore in-process teammates."
- GitHub #26265 (closed as dup of #23620): code-level analysis confirms the
  resume logic is unreachable for teammates.
- Workaround: spawn new teammates after resume. This loses all teammate-local
  context and partially-done work.

**Impact on our workbench:** `drupal-issue.sh` is built around resume. Ticket
027 specifically fixed the session-mapping path to make resume reliable.
Every real-world usage pattern involves killing the terminal, sleeping,
and resuming the next day. Agent Teams are incompatible with this.

---

## Research Question 2: Hook Viability

**Verdict: VIABLE. Works without Agent Teams.**

### TaskCompleted hook mechanics

| Property | Detail |
|---|---|
| Stdin JSON fields | `session_id`, `transcript_path`, `cwd`, `permission_mode`, `hook_event_name`, `task_id`, `task_subject`, `task_description`, `teammate_name` (if in team), `team_name` (if in team) |
| Exit code 2 behavior | **Confirmed mechanical block.** Prevents the task from being marked complete. Stderr text is fed back to the model as an error message. Task remains in-progress. Stdout and JSON on exit 2 are ignored. |
| File access | Full. Hooks are ordinary shell commands — can read `workflow/*.json`, `git diff`, anything on disk. |
| Execution model | Runs in CWD at the time the hook fires. Environment includes Claude Code's vars + `$CLAUDE_PROJECT_DIR`. Default timeout: 600 seconds. |
| Configuration | `settings.json` (user, project, or local scope) under `"hooks"` key. The workbench already has hooks configured (SessionStart + PreCompact for `bd prime`). |

### Prototype hook (not run live, but validated against docs)

```bash
#!/usr/bin/env bash
# .claude/hooks/verify-before-done.sh
# TaskCompleted hook: blocks completion if verification artifacts are missing or stale.
set -euo pipefail

INPUT=$(cat)
TASK_SUBJECT=$(echo "$INPUT" | jq -r '.task_subject // ""')

# Only gate tasks that look like "fix" or "push" phases
[[ ! "$TASK_SUBJECT" =~ (fix|push|commit|verify) ]] && exit 0

# Find the most recent workflow dir
CWD=$(echo "$INPUT" | jq -r '.cwd')
WORKFLOW_DIR=$(find "$CWD" -maxdepth 3 -name "workflow" -type d 2>/dev/null | head -1)
[[ -z "$WORKFLOW_DIR" ]] && exit 0  # no workflow dir = not our concern

# Check verification results exist
VERIFY="$WORKFLOW_DIR/02-verification-results.json"
if [[ ! -f "$VERIFY" ]]; then
  echo "BLOCKED: $VERIFY does not exist. Run verification before claiming done." >&2
  exit 2
fi

# Check freshness (< 30 min old)
FILE_AGE=$(( $(date +%s) - $(stat -c %Y "$VERIFY") ))
if (( FILE_AGE > 1800 )); then
  echo "BLOCKED: $VERIFY is $(( FILE_AGE / 60 )) minutes old (max 30). Re-verify." >&2
  exit 2
fi

exit 0
```

### Configuration (would go in `.claude/settings.json`)

```json
{
  "hooks": {
    "TaskCompleted": [
      {
        "hooks": [
          {
            "command": "bash .claude/hooks/verify-before-done.sh",
            "type": "command"
          }
        ],
        "matcher": ""
      }
    ]
  }
}
```

### Other useful hook events for the workbench

| Event | Use case | Priority |
|---|---|---|
| **TaskCompleted** | Block "done" without verification artifacts | P0 |
| **PreToolUse** | Block `git push` unless verification passed | P1 |
| **Stop** | Auto-write bd summary on session end | P2 |
| **SubagentStop** | Validate subagent return before accepting | P2 |
| **PreCompact** | Already used for `bd prime` | Existing |
| **SessionStart** | Already used for `bd prime` | Existing |

Total: **26 hook events available** in Claude Code. The workbench currently uses 2 (SessionStart, PreCompact).

---

## Research Question 3: Linear-Flow Expression as Task DAG

**Verdict: POSSIBLE but pointless given resume incompatibility.**

Tasks DO support `depends_on` edges. The system auto-unblocks dependent
tasks when blockers complete. Our chain could be expressed as:

```
fetcher → resonance → classify → review → solution-depth → fix → reviewer → verifier → spec-reviewer → push
```

Each step as a task, each depending on the prior. The lead would dispatch
the whole DAG upfront and teammates would claim tasks as they unblock.

**But this adds no value over our current skill chain:**
- Sequential execution is already guaranteed by skill ordering.
- The DAG adds token overhead (lead + teammates).
- Resume breaks it (Q1).
- Task status can lag — teammates sometimes fail to mark tasks complete,
  blocking dependents. GitHub reports confirm this.

---

## Research Question 4: Parallelism Opportunity

**Verdict: REAL but marginal, doesn't justify the costs.**

The only parallelism opportunity in our workflow:

```
fix-draft → { reviewer, verifier, spec-reviewer } → push-gate
```

These three review phases are genuinely independent and could run as
parallel siblings all depending on `fix-draft`. Estimated wall-clock
savings: 3-5 minutes (reviews currently take ~2-3 min each sequentially,
~3-5 min in parallel including coordination overhead).

**Token cost:** 3 parallel teammates = 3-4x the tokens for that phase.
At ~$0.03-0.05 per review phase currently, that's $0.09-0.20 per issue
for marginal time savings. Not economically justified for our volume.

**Risk:** Ghost message bug (#28627) — after ~50+ idle notifications,
fabricated commands appear in the lead's terminal. One documented case
triggered `TeamDelete`, destroying an active team. For a workflow that
handles real Drupal.org contributions, this is unacceptable.

---

## Research Question 5: Token Cost

**Not measured directly** (no live prototype). From official docs:

- "Agent teams use significantly more tokens than a single session"
- Each teammate is a separate Claude instance with its own context window
- Broadcasts scale linearly with team size
- Recommended: 3-5 teammates, 5-6 tasks per teammate

**Estimated for our workflow:**
- Current full issue end-to-end (skill chain): ~100-200K tokens
- Same flow as full team: ~400-800K tokens (4x from lead overhead +
  teammate contexts + inter-teammate messaging)
- Hooks only (no teammates): ~100-200K tokens (zero overhead — hooks are
  shell scripts, not Claude instances)

---

## Research Question 6: Skill Compatibility

**Verdict: WORKS with a caveat.**

Teammates load project-local skills from `settings.json` / `.claude/` the
same as a regular session. So `/drupal-issue-review`, `/drupal-contribute-fix`,
etc. would be available.

**Caveat:** If a teammate is spawned from a subagent definition (`.claude/agents/*.md`),
the `skills` and `mcpServers` fields in that agent's frontmatter are NOT
applied to the teammate. Skills must come from project/user-level settings.

**Identity string:** Confirmed difference (#32721, closed as wontfix).
Teammates report as "Claude Agent SDK" instead of "Claude Code." This is
unlikely to affect skill behavior since skills are prose-driven, not
identity-gated. But it means any logic that checks `User-Agent` or
similar strings would see a different identity.

---

## Known Critical Bugs

| Bug | Severity | Issue | Status |
|---|---|---|---|
| Ghost messages → fabricated commands | **CRITICAL** | #28627 (dup of #27128) | Open |
| Silent spawn failures (long commands) | HIGH | #42391 | Open |
| Task status lag blocks dependents | MEDIUM | Community reports | Unresolved |
| `/resume` doesn't restore teammates | HIGH (for us) | #26265, #23620 | Closed (by design) |
| Identity string difference | LOW | #32721 | Closed (wontfix) |
| 429/529 errors with concurrent teammates | MEDIUM | #44481 | Open |

---

## Verdict

### **ADOPT (verification hooks only)**

**Adopt TaskCompleted hooks. Reject Agent Teams.**

### Reasoning

1. **TaskCompleted hooks deliver the primary value** (mechanical enforcement
   of verification gates) **without any of the Agent Teams risks.** Hooks
   are shell scripts that run as side-effects of Claude Code's existing
   event lifecycle. Zero additional Claude instances. Zero token overhead.
   Zero resume risk.

2. **Agent Teams are incompatible with our resume model.** This alone is
   disqualifying. The workbench's primary operating mode is kill-and-resume
   across days/sessions. Agent Teams can't survive that.

3. **The ghost message bug is a safety risk.** Fabricated commands in a
   workflow that pushes code to Drupal.org is unacceptable. The bug is
   still open.

4. **The parallelism opportunity is marginal.** 3-5 minutes of wall-clock
   savings doesn't justify 3-4x token cost and the operational complexity
   of managing a team.

5. **The hook infrastructure already exists in the workbench.** SessionStart
   and PreCompact hooks are live and working. Adding TaskCompleted is
   incremental — a new key in `settings.json` and a bash script in
   `.claude/hooks/`.

### What this means for other tickets

| Ticket | Impact |
|---|---|
| **022 (verification gate)** | Already COMPLETED with prose enforcement. Hooks give us the mechanical gate we lacked. A follow-up ticket should add a TaskCompleted hook that checks `workflow/02-verification-results.json` and `workflow/02a-trigger-decision.json`. |
| **031 (sentinel + reinstate)** | Already COMPLETED with sentinel pattern. No change needed — sentinels are upstream of any hookable task (classification happens before any "task" boundary). The sentinel pattern and hooks are complementary, not competing. |
| **030 (solution-depth gate)** | Unaffected. The pre-fix/post-fix gates are subagent-driven, not task-boundary-driven. |
| **034 (bd cross-issue memory)** | The `Stop` hook is a candidate for auto-syncing workflow files to bd at session end. Research this when implementing 034. |

### Suggested follow-up ticket

**"Add TaskCompleted verification hook (mechanical push gate)"**

Scope:
1. Create `.claude/hooks/verify-before-done.sh` (prototype above)
2. Add `TaskCompleted` entry to `.claude/settings.json`
3. Test: attempt to claim "fix done" without verification artifacts → should be blocked
4. Test: attempt to claim "fix done" with stale (>30 min) artifacts → should be blocked
5. Test: claim "fix done" with fresh verification → should pass

Optional stretch:
6. Add `PreToolUse` hook that blocks `git push` unless `02-verification-results.json` exists
7. Add `Stop` hook for bd session summary

**Priority:** P1. Can be done after 034 or alongside it.

---

## Appendix: All 26 Claude Code Hook Events

SessionStart, InstructionsLoaded, UserPromptSubmit, PreToolUse,
PermissionRequest, PermissionDenied, PostToolUse, PostToolUseFailure,
Notification, SubagentStart, SubagentStop, TaskCreated, TaskCompleted,
Stop, StopFailure, TeammateIdle, ConfigChange, CwdChanged, FileChanged,
WorktreeCreate, WorktreeRemove, PreCompact, PostCompact, Elicitation,
ElicitationResult, SessionEnd.
