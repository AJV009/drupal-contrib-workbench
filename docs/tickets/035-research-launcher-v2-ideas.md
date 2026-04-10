# TICKET-035: RESEARCH — Mine orc, bernstein, kodo for Launcher v2 Ideas

**Status:** NOT_STARTED
**Priority:** P0 (research, do early to inform 027/028/031)
**Affects:** New file `docs/research/launcher-v2-ideas.md`
**Type:** Research

## Why this is research, not implementation

`drupal-issue.sh` has grown organically into a 200-line bash script. Three orchestrator projects in the broader Claude Code ecosystem have novel design patterns worth borrowing for the next iteration of the launcher. This ticket is reading + idea-mining only — no code changes, no new tickets created automatically.

## What to mine

### 1. spencermarx/orc

URL: https://github.com/spencermarx/orc (~12 stars but philosophically closest to our stack)

What to read:
- README + any docs/
- The bash entry point and any helper scripts
- How it structures phases (`Investigate→Plan→Decompose→Dispatch→Setup→Build→Review→Deliver`)
- How it integrates with beads
- How it manages tmux sessions

What to extract:
- Bash patterns for phase functions (vs our inline orchestration)
- Three-tier hierarchy concept (Root/Project/Goal) — could it map to (Launcher / Issue / Phase)?
- Worktree avoidance patterns (orc uses worktrees; we use full DDEV installs — what patterns translate?)

### 2. chernistry/bernstein

URL: https://github.com/chernistry/bernstein (~89 stars, April 2026 activity)

What to read:
- README and architecture docs
- Python orchestrator entry point
- The "Janitor" verification layer (this is the most interesting part)
- The decompose→spawn→verify→merge pipeline

What to extract:
- The "zero LLM tokens for scheduling" principle — could `drupal-issue.sh` v2 adopt this? What scheduling logic is currently model-driven that should be deterministic?
- Janitor verification layer design — how does it mechanically verify worker output? Could replace or augment the verification gate (ticket 022) without needing Agent Teams hooks?

### 3. ikamensh/kodo

URL: https://github.com/ikamensh/kodo (~56 stars, claims +24% on SWE-bench)

What to read:
- README + architecture
- The agent specialization model (Architect → Smart-worker → Tester)
- How tasks are decomposed and dispatched

What to extract:
- Whether further decomposition of `drupal-contribute-fix` (beyond ticket 005's modes) is suggested
- Whether the SWE-bench number is for "small model orchestrating big model" (the inverse of our setup) or vice versa
- Token-cost techniques

## Deliverable

`docs/research/launcher-v2-ideas.md` containing:

1. **One section per project** with:
   - Architecture summary (what is it actually)
   - 2-5 patterns worth stealing, each with a concrete proposal for how it would fit `drupal-issue.sh` v2
   - 1-2 patterns explicitly NOT worth stealing (and why)

2. **Synthesis section**:
   - Top 5 ideas across all three projects
   - Suggested next-version `drupal-issue.sh` skeleton incorporating the best ideas
   - Tickets to file as follow-ups (do NOT file them in this ticket; just propose them in the synthesis for user review)

## Constraint

This is reading + writing one markdown file. No code changes. No new tickets created automatically — let the user review the synthesis and decide what to file.

## Dependencies

None.

## Notes

Why P0 despite being research: the synthesis output may suggest changes to ticket 027 (launcher fix), 028 (bd integration in launcher), or 031 (sentinel pattern). Doing those tickets first, then realizing a better pattern existed, is wasted work. Better to mine ideas first.

Keep the deliverable opinionated. "These are interesting" is useless; "these 3 patterns would unambiguously improve drupal-issue.sh, and here is how" is the goal.

## Resolution (2026-04-10)

Research completed. Deliverable at `docs/research/launcher-v2-ideas.md`.

### Key findings

**Top pattern across all 3 projects:** Bernstein's "completion signals as data" — declare what "done" looks like as structured `{type, value}` pairs, evaluate generically. This subsumes our current hand-coded hook checks (039) into a declarative, extensible system.

**Second pattern:** "Zero LLM for scheduling" (bernstein + kodo) — move phase routing from skill prose to the launcher (bash state machine). Claude Code only handles phase execution, not sequencing.

**Third pattern:** orc's status-file protocol — formalize `workflow/status.json` as the machine-readable progress tracker that the launcher reads on resume.

**Not worth stealing:** Worktree-per-worker isolation (conflicts with DDEV), multi-project orchestration (we work one issue at a time), FastAPI task servers (overkill for single-session), adaptive planning (our phases have fixed domain-logic ordering).

### Suggested follow-up tickets

| # | Title | Source | Effort | Priority |
|---|---|---|---|---|
| 040 | Declarative completion signals + generic evaluator | bernstein | Medium | P1 |
| 041 | Status-file protocol (workflow/status.json) | orc | Low | P1 |
| 042 | Config cascade (config.yaml 3-level inheritance) | orc | Low-Med | P2 |
| 043 | Deterministic phase machine in launcher v2 | bernstein+kodo | High | P1 |

Recommended order: 041 → 040 → 042 → 043.
