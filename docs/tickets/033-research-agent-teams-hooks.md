# TICKET-033: RESEARCH — Agent Teams TaskCompleted Hook Prototype

**Status:** NOT_STARTED
**Priority:** P0 (research, do early to inform other tickets)
**Affects:** Throwaway DDEV install for prototyping; deliverable `docs/research/agent-teams-prototype-results.md`
**Type:** Research

## Why this is research, not implementation

The user previously dismissed Agent Teams as "too parallel for our linear flow." That dismissal was based on incomplete information. Reinvestigation revealed:

**The single most important fact** (per https://code.claude.com/docs/en/hooks):

> "Exit code 2 prevents completion and feeds stderr back to the model as feedback."

The `TaskCompleted` hook is the **only mechanism in the entire Claude Code ecosystem** that mechanically blocks an agent from claiming "done" based on an external check. Everything else (skills, prose IRON LAWS, structured agent returns from ticket 021) trusts the model to obey.

Our current verification gate (ticket 022) is prose-only. Session 9b75cb81 proves prose enforcement leaks: the workflow proposed mocks despite IRON LAWS, and the user had to manually inject "do this the PROPER way."

If `TaskCompleted` hooks are viable for our workflow, they replace the leaky prose with hard mechanical gates. That is a huge win.

## Known costs (must validate)

| Cost                                                              | Severity                              | How to validate |
|-------------------------------------------------------------------|---------------------------------------|-----------------|
| `/resume` does not restore in-process teammates                   | **HIGH** — conflicts with our resume model | Prototype: launch a session with teammates, kill the terminal, try `/resume`, see what survives |
| Token cost scales linearly with teammate count                    | MEDIUM                                | Measure: full issue end-to-end with N=1 vs N=5 teammates |
| Hooks receive metadata only, not task output                      | LOW                                   | We have workflow/*.json files; hooks check those externally |
| Experimental + community reports of teammates losing messages     | MEDIUM                                | Stress-test: dispatch 10 tasks rapidly, check survival |
| One team per session, no nested teams                             | LOW                                   | Our controller is already flat |

## Research questions

1. **Resume compatibility** (the biggest risk): does `claude --resume <uuid>` actually break with teammates? What about split-pane mode (tmux + multiple claude processes)? Test on a throwaway issue.

2. **Hook viability**: write a `TaskCompleted` hook that checks `workflow/02-verification-results.json` exists and is < 10 min old. Verify exit code 2 actually blocks the task and surfaces stderr. Test scaffolding:
   ```bash
   #!/bin/bash
   # .claude/hooks/task-completed-verification.sh
   INPUT=$(cat)
   TASK_SUBJECT=$(echo "$INPUT" | jq -r '.task_subject')
   [[ ! "$TASK_SUBJECT" =~ ^verify ]] && exit 0
   # extract issue id, check file freshness
   exit 2  # if check fails
   ```

3. **Linear-flow expression**: can the existing chain (fetcher → resonance → classify → review → solution-depth → fix → reviewer → verifier → spec-reviewer → push) be expressed as a task DAG with `depends_on` edges? Does it actually run linearly? Does plan-approval mode interfere?

4. **Parallelism opportunity**: after fix-draft, can `reviewer + verifier + spec-reviewer` run as 3 parallel sibling tasks all depending on `fix-draft`? Measure wall-clock vs current sequential. This is the only place in the workflow where parallelism actually fits the domain.

5. **Token cost**: prototype one full issue end-to-end. Compare token usage to current Skill-tool flow.

6. **Skill compatibility**: per docs, teammates load project-local skills the same as a regular session. Verify that a teammate can invoke `/drupal-issue-review` cleanly. Note: there's a documented identity-string difference (teammates report as "Claude agent" not "Claude Code") per anthropics/claude-code#32721 — confirm whether this affects skill behavior.

## Activation

```json
// settings.json
{ "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }
```
Requires Claude Code v2.1.32+.

## Deliverable

`docs/research/agent-teams-prototype-results.md` containing:

1. Summary of each research question + answer with evidence
2. Token cost numbers (before/after)
3. A verdict: one of
   - **ADOPT (verification hooks only)** — keep existing controller, add `TaskCompleted` hook for verification gate enforcement
   - **ADOPT (parallel review only)** — switch to Agent Teams for the post-draft phase only (reviewer/verifier/spec-reviewer in parallel)
   - **ADOPT (full)** — express the entire workflow as a team
   - **REJECT** — resume incompatibility or flakiness kills it; document why so we don't reconsider

4. If ADOPT: a follow-up ticket spec for the actual migration

## Constraint: do not migrate production yet

This ticket is investigation only. Do not change `drupal-issue.sh` or any skill until the verdict is in. Use a throwaway issue dir (e.g., `DRUPAL_ISSUES/test-agent-teams-NNNN/`) for prototyping.

## Dependencies

None.

## Notes

Why P0 despite being research: the research outcome will REWRITE tickets 022 (already complete) and 031 (not yet started). Doing 031 with the sentinel pattern, then later realizing we should have used hooks, wastes implementation time. Better to know first.

If REJECT: ticket 031 stays as-planned with the sentinel pattern. If ADOPT (verification hooks only): ticket 031 gets revised to use hooks instead of sentinels for the verification phase, but keeps sentinels for the classification phase (which is upstream of any hookable task).

## Resolution (2026-04-10)

Research completed. Deliverable at `docs/research/agent-teams-prototype-results.md`.

**Verdict: ADOPT (verification hooks only). Reject Agent Teams.**

Key findings:
1. `/resume` does NOT restore in-process teammates — dealbreaker for our resume-based workflow
2. Ghost message bug (#28627) causes fabricated commands after ~50+ idle notifications — safety risk for a workflow that pushes code to d.o
3. TaskCompleted hooks with exit code 2 mechanically block task completion and feed stderr back to the model — works WITHOUT Agent Teams, zero token overhead
4. Parallelism opportunity (3 parallel reviewers) saves 3-5 min wall clock but costs 3-4x tokens — not justified
5. The workbench already has hooks infrastructure (SessionStart + PreCompact for bd prime); adding TaskCompleted is incremental

**Impact on other tickets:** 031 (already completed with sentinel pattern) is unaffected — sentinels and hooks are complementary. A follow-up ticket for the actual verification hook is suggested in the deliverable.

**Methodology note:** Documentation review + GitHub issue analysis. No live prototype was run because the remote machine's Claude Code is accessed via SSH, precluding interactive team sessions. All findings are sourced from official docs and verified GitHub issues.
