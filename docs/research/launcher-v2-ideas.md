# Launcher v2 Ideas — Mining orc, bernstein, kodo

**Ticket:** 035 — RESEARCH: Mine orc/bernstein/kodo for launcher v2 ideas
**Date:** 2026-04-10
**Methodology:** Source code review of all three repos via GitHub.

---

## 1. spencermarx/orc

**What it is:** Pure bash CLI (~2000-line shared library in `_common.sh`)
that orchestrates multiple AI coding agents across projects. Uses tmux as
the UI layer, git worktrees for isolation, bd (beads) for work decomposition.

### Patterns worth stealing

**1. Status-file protocol for agent-to-agent communication.**
Engineers write `.worker-status` (working/review/blocked/done) and
`.worker-feedback` files. Goal orchestrators poll these. Simple, debuggable,
no IPC framework needed. Our workbench already has `workflow/*.json` files
that serve a similar role (ticket 031's sentinel pattern), but orc's approach
is more systematic: every agent tier writes status, and the tier above polls it.

**Concrete proposal:** Formalize a `.worker-status` equivalent in
`DRUPAL_ISSUES/<nid>/workflow/status.json` with `{phase, status, agent, timestamp}`.
The launcher could poll this on resume to know exactly where the workflow was.

**2. Hierarchical teardown.**
`teardown.sh` handles bead/goal/project/all levels with branch cleanup,
worktree removal, and pane killing in dependency order. Our `pause-orphaned-ddev.sh`
(ticket 032) is the beginning of this, but orc's approach is more comprehensive.

**Concrete proposal:** Extend `pause-orphaned-ddev.sh` into a broader
`workbench-teardown.sh` that handles DDEV + tmux + bd status for an issue.

**3. Config cascade: global → project → local.**
TOML config with 3-level inheritance. Our settings are scattered across
`drupal-issue.sh` env vars, `.claude/settings.json`, and `CLAUDE.md` prose.

**Concrete proposal:** A `config.yaml` at workbench root that consolidates
launcher settings (default model, DDEV prefix, resume strategy, hook toggles)
with per-issue overrides possible via `DRUPAL_ISSUES/<nid>/config.yaml`.

**4. Adapter pattern for AI backends.**
One adapter per CLI (claude.sh, codex.sh, gemini.sh), each implementing
`_adapter_build_launch_cmd`. Easy to swap backends.

**Concrete proposal:** If we ever support Codex or Gemini CLI alongside
Claude Code, the adapter pattern is the way. Low priority unless the user
wants multi-backend support.

### Patterns NOT worth stealing

**1. Three-tier hierarchy (Root/Project/Goal).** Orc manages N projects
simultaneously with M goals each. Our workbench works one issue at a time.
The multi-project orchestration is interesting engineering but doesn't map
to our single-issue-at-a-time workflow.

**2. Worktree-per-worker isolation.** Orc gives every engineer its own
git worktree. We use full DDEV installs per issue with composer-managed
module trees. Our isolation is at the container level, not the git level.
Worktrees would conflict with DDEV's `.ddev/` config expectations.

---

## 2. chernistry/bernstein

**What it is:** Python 3.12+ deterministic orchestrator. Spawns CLI coding
agents as subprocesses. State in `.sdd/` files (YAML/JSONL). FastAPI task
server on port 8052. The orchestrator itself never calls an LLM — only the
"Manager" (decomposition) and "Janitor" (optional LLM judge) touch models.

### Patterns worth stealing

**1. Completion signals as data, not code.**
Tasks carry structured `CompletionSignal` objects: `{type: "path_exists",
value: "tests/test_foo.py"}`, `{type: "test_passes", value: "pytest -x"}`,
`{type: "file_contains", value: "src/api.py :: def handle_request"}`.
The janitor evaluates these generically — no task-specific verification code.

**Concrete proposal:** This is the single most impactful pattern across all
three projects. Our push-gate checklist (ticket 039) is a manual version of
this: the skill writes verdicts, the hook reads them. Bernstein's approach
turns it into data: each phase declares what "done" looks like as structured
signals, and a generic verifier checks them. We could evolve the
`workflow-state-files.md` registry into signal declarations:

```yaml
# workflow/signals.yaml
classification:
  - type: path_exists
    value: workflow/00-classification.json
  - type: file_contains
    value: "workflow/00-classification.json :: \"status\":\"classified\""
push_gate:
  - type: path_exists
    value: workflow/03-push-gate-checklist.json
  - type: test_passes
    value: "jq -e '.reviewer_verdict == \"APPROVED\"' workflow/03-push-gate-checklist.json"
```

This would replace the hand-coded checks in `push-gate.sh` and
`workflow-completion.sh` with a declarative, extensible system.

**2. Mechanical verification before LLM verification.**
Bernstein's janitor runs `path_exists`, `test_passes`, `file_contains` first.
Only if all pass does it escalate to `llm_judge`. This saves tokens and catches
obvious failures instantly.

**Concrete proposal:** Already partially implemented. Our hooks (039) are
mechanical checks (file exists, jq query passes). The LLM layer is the skill
prose itself. The ordering is correct; formalizing it as a two-tier system
(mechanical → LLM) would make the boundary explicit.

**3. Zero LLM tokens for scheduling.**
The orchestrator is pure Python: dependency resolution via DAG, model routing
via tiered rules, retry with exponential backoff. The only LLM call is the
initial decomposition (Manager).

**Concrete proposal:** Our `drupal-issue.sh` launcher is already zero-LLM
for scheduling — it's bash that launches Claude Code with a skill prompt.
But the SKILL.md prose drives phase sequencing inside the session, which IS
LLM-driven. Moving more phase transitions to the launcher (bash) and using
the LLM only for phase execution would improve determinism. This aligns with
ticket 031's sentinel pattern, which moved classification enforcement from
prose to a mechanical check.

**4. Auto-fix task creation on verification failure.**
When the janitor fails a task, it auto-creates a scoped fix task with failure
details. Self-healing loop with a budget cap.

**Concrete proposal:** Already implemented as ticket 030's failure path:
post-fix gate score ≥4 → revert + re-run architectural with circuit breaker
at 2 attempts. The pattern is the same; bernstein's version is more generic
(works for any task type, not just post-fix).

### Patterns NOT worth stealing

**1. FastAPI task server.** A REST API for task management is overkill for a
single-session, single-issue workflow. Our `workflow/*.json` files + bd serve
the same role with zero infrastructure.

**2. `.sdd/` file-based state instead of a database.** We already chose bd
(Dolt-backed) as the data layer (ticket 028). Reverting to flat YAML files
would regress on queryability.

---

## 3. ikamensh/kodo

**What it is:** Multi-agent orchestration layer on top of existing coding CLIs.
A cheap API-based orchestrator (Gemini Flash, ~$0.13/run) coordinates expensive
subscription-covered coding agents. Agents are pydantic-ai tool calls. Claims
+24% relative improvement on SWE-bench Verified (57% vs 46% Cursor alone).

### Patterns worth stealing

**1. Cheap orchestrator / expensive worker split.**
Gemini Flash (~pennies) as coordinator, Claude Code Opus as worker. The
orchestrator sees agents as tool calls, not prompts — clean separation.
The orchestrator explicitly avoids coding CLIs as coordinators because
"they'll try to write code instead of delegating."

**Concrete proposal:** Our `/drupal-issue` controller runs inside Claude Code
(expensive). Moving the phase-routing logic to a cheaper model or to bash
(deterministic) and only dispatching to Claude Code for phase execution would
reduce costs. This reinforces bernstein's "zero LLM for scheduling" principle.

For v2, the launcher could use Sonnet (or even Haiku) as the router model
that reads `workflow/status.json` and decides the next skill to invoke, while
Opus handles the actual code/review/fix work.

**2. Verification gate on `done()` with anti-gaming.**
When the orchestrator calls `done()`, tester + architect agents verify
independently. The check regex-strips code blocks, quotes, and negations
to prevent gaming. Rejection loops back to fix.

**Concrete proposal:** Our hooks (039) are the mechanical version of this.
The anti-gaming aspect is interesting — our post-fix gate (030) has a
rationalization-prevention table, but it's prose-based. A mechanical
anti-gaming layer (strip markdown before checking verdicts) could be added
to the hook scripts.

**3. Persistent agent notes surviving context resets.**
`.kodo/<role>-notes.md` files carry forward project-specific knowledge
across context window resets. Cheap to implement, high value for long sessions.

**Concrete proposal:** This is exactly what `bd prime` does at SessionStart
and PreCompact. Our implementation is already stronger: bd provides structured
queries, not just flat files. The pattern is validated.

**4. Fire-and-forget summarizer for token management.**
After each agent call, a background thread summarizes the result using a cheap
model (ollama → Gemini Flash Lite → truncation fallback). Reports capped at
10K chars.

**Concrete proposal:** Our subagent returns are already structured (DONE/
NEEDS_CONTEXT/BLOCKED/FAILED status codes from ticket 021). But the idea of
summarizing long subagent output before feeding it to the controller could
help with context pressure in long sessions. Low priority but interesting.

### Patterns NOT worth stealing

**1. Parallel stages via git worktrees.** Same issue as orc — our DDEV
containers don't compose with worktrees. Module code lives inside a
Drupal site, not in a standalone git tree.

**2. Adaptive planning (Advisor).** Interesting for open-ended work, but
our workflow is linear and well-defined (fetch → classify → review → fix →
verify → push). The phases don't benefit from dynamic reordering — they're
ordered by domain logic, not by opportunity.

---

## Synthesis: Top 5 Ideas for drupal-issue.sh v2

### 1. Completion signals as data (from bernstein) — **HIGHEST IMPACT**

Replace the hand-coded hook checks with declarative signal definitions.
Each workflow phase declares its "done" criteria as structured data.
A generic signal evaluator replaces task-specific verification code.

This subsumes the current push-gate hook and workflow-completion hook into
a single, extensible mechanism. New phases automatically get verification
by declaring their signals — no new hook code needed.

**Effort:** Medium (new `signals.yaml` format + generic evaluator script).
**Blocks:** Nothing. Can be added alongside existing hooks.

### 2. Zero LLM for phase scheduling (from bernstein + kodo)

Move phase-routing logic from skill prose to the launcher (bash) or a
cheap model. The launcher reads `workflow/status.json`, determines the
next phase, and dispatches the appropriate Claude Code skill. Claude Code
only handles phase execution, not sequencing.

This makes the workflow deterministic at the scheduling level: the same
`status.json` always produces the same next-phase decision, regardless
of model temperature or prompt interpretation.

**Effort:** High (requires refactoring the `/drupal-issue` controller
from a single skill into a bash-driven phase machine).
**Blocks:** Significant architectural change. Should be a dedicated ticket.

### 3. Status-file protocol (from orc)

Formalize `DRUPAL_ISSUES/<nid>/workflow/status.json` as a machine-readable
progress tracker: `{phase, status, agent, timestamp, last_error}`. The
launcher reads this on resume to know exactly where the workflow was and
what to dispatch next. Skills update it at each phase boundary.

This is the complement to idea #2: the status file is the state that the
scheduler reads.

**Effort:** Low (one new file, small edits to each skill).
**Blocks:** Nothing. Incremental improvement.

### 4. Config cascade (from orc)

Consolidate launcher settings into `config.yaml` with 3-level inheritance:
`workbench/config.yaml` (defaults) → `DRUPAL_ISSUES/<nid>/config.yaml`
(per-issue overrides) → env vars (runtime). Replaces the current scatter
across `drupal-issue.sh` env exports, `.claude/settings.json`, and prose.

**Effort:** Low-medium (new config parser, migrate existing settings).
**Blocks:** Nothing. Quality-of-life improvement.

### 5. Cheap orchestrator / expensive worker split (from kodo)

Use Sonnet (or bash) as the phase router, dispatch Opus only for actual
code/review work. Reduces token cost for the scheduling overhead.

**Effort:** Medium (requires the phase-machine refactor from idea #2).
**Blocks:** Depends on idea #2.

---

## Suggested v2 launcher skeleton

```bash
#!/usr/bin/env bash
# drupal-issue.sh v2 — deterministic phase machine

# Phase 0: Parse args, resolve session, write sentinel
# (existing v1 logic, cleaned up)

# Phase 1: Read status.json → determine current phase
status=$(jq -r '.phase' "$WORKFLOW_DIR/status.json" 2>/dev/null || echo "init")

# Phase 2: Dispatch to the appropriate skill for this phase
case "$status" in
  init)           dispatch_skill "/drupal-issue" ;;
  classified)     dispatch_skill "/drupal-issue-review" ;;
  reviewed)       dispatch_skill "/drupal-contribute-fix" ;;
  pushed)         dispatch_skill "/drupal-pipeline-watch" ;;
  *)              echo "unknown phase: $status" ;;
esac

# dispatch_skill() launches claude with the skill prompt,
# waits for exit, reads updated status.json, loops.
```

This is a simplification — the real v2 would handle resume, error recovery,
and the signal-verification step between phases. But the core idea is: the
launcher is a bash state machine, Claude Code is the executor.

---

## Suggested follow-up tickets (for user review)

| Ticket | Title | Source | Effort | Priority |
|---|---|---|---|---|
| 040 | Declarative completion signals + generic evaluator | bernstein | Medium | P1 |
| 041 | Status-file protocol (`workflow/status.json`) | orc | Low | P1 |
| 042 | Config cascade (config.yaml 3-level inheritance) | orc | Low-Med | P2 |
| 043 | Deterministic phase machine in launcher v2 | bernstein+kodo | High | P1 |

Tickets 040 and 041 are independent quick wins. Ticket 043 is the big
architectural refactor that ideas #2 and #5 require. Ticket 042 is
quality-of-life.

**Recommended execution order:** 041 → 040 → 042 → 043.
Status file first (tiny, unblocks everything), then signals (subsumes
current hooks), then config cascade (cleanup), then the full phase machine
(major refactor informed by the first three).
