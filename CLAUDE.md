# Drupal Contribution Workbench

This workspace is for contributing to Drupal core and contributed modules on drupal.org.

## User

- **ajv009** on drupal.org is Alphons — the person running this Claude Code setup and all associated commands/skills.

## Approach

- Think before acting. Read existing files before writing code.
- Prefer editing over rewriting whole files.
- Do not re-read files already read in this session unless they may have changed.
- Keep solutions simple and direct. No abstractions for single-use operations.
- No sycophantic openers or closing fluff.
- User instructions (and additional instructions via `-i`) always override this file.

## Output Style

- Lead with the finding or action, not the reasoning.
- Tables and bullets over prose paragraphs.
- No decorative Unicode: no smart quotes, em dashes, en dashes, or ellipsis characters. Use plain hyphens, commas, colons, and periods.
- Code output must be copy-paste safe.
- No status narration ("Now I will...", "I have completed..."). Just do it.

## Environment

- Local development via **DDEV** (`ddev start`, `ddev drush`, `ddev composer`)
- Run tests via `ddev exec phpunit`

### Directory Structure

- **DRUPAL_ISSUES/** - Clone repos here for issue work (reproducing, fixing, reviewing d.o issues). Use `DRUPAL_ISSUES/{issue_number}/` as the parent directory.
- **TEMP/** - Temporary/throwaway clones.
- **Never clone directly into the workspace root.** Keep it clean.

## Drupal.org Contribution Workflow

1. **Find an issue** on drupal.org (or create one)
2. **Fork** the project on drupal.org (Projects → Fork)
3. **Clone** your fork locally
4. **Create a branch** named `{issue_number}-{short-description}`
5. **Fix + test** following Drupal coding standards
6. **Push** to your fork
7. **Create a Merge Request** on drupal.org linking to the issue
8. Wait for **review → RTBC → commit** cycle

## Coding Standards (Non-Negotiable)

- `declare(strict_types=1)` in every PHP file
- PSR-4 autoloading (`Drupal\{module}\` namespace)
- Constructor injection — never `\Drupal::service()` in services
- PHPDoc on all public methods
- `$this->t()` for user-facing strings, never hardcoded
- 2-space indentation (not 4)
- No docstrings, comments, or type annotations on code you did not change
- Run before submitting: `ddev exec phpcs --standard=Drupal,DrupalPractice`

## Testing Requirements

Every fix MUST include tests. Choose the right type:

| Test Type | Base Class | When to Use |
|-----------|-----------|-------------|
| Unit | `UnitTestCase` | Pure PHP logic, no Drupal |
| Kernel | `KernelTestBase` | Entity/DB/service access |
| Functional | `BrowserTestBase` | Full Drupal + HTTP requests |
| FunctionalJS | `WebDriverTestBase` | JavaScript-dependent behavior |

Run: `ddev exec phpunit modules/contrib/{module}/tests/src/{Type}/{TestFile}.php`

### Dependency Rules (Non-Negotiable)

- **ALWAYS install `drupal/core-dev:^11` with `-W` flag.** This single package provides PHPUnit 11, PHPCS, Coder 8, PHPStan, and all test infrastructure. Command: `ddev composer require --dev "drupal/core-dev:^11" -W --no-interaction`
- **NEVER install `phpunit/phpunit` standalone.** It pulls v12+ which cannot load Drupal test base classes (UnitTestCase, KernelTestBase, etc.). PHPUnit must come through `drupal/core-dev`.
- **NEVER install `drupal/coder` standalone.** It is bundled inside `drupal/core-dev` as coder 8. Installing coder 9 independently creates a composer conflict that blocks `core-dev` installation.

## Drupal.org API

Issue queue search: `https://www.drupal.org/api-d7/node.json?type=project_issue&field_project={nid}&title={search}`

## Hands-Free Workflow (Critical)

The `/drupal-issue` workflow runs **hands-free from invocation to push gate**. The ONLY point where you stop and wait for user input is before pushing to a remote (the Push Gate in `/drupal-contribute-fix`). For comment-only workflows, the stop point is presenting the draft comment.

- Do NOT announce skills before invoking them. Just invoke.
- Do NOT ask the user which category the issue falls into. Classify and proceed.
- Do NOT stop between skill transitions to ask "should I continue?"
- Do NOT create all tasks upfront. Create them lazily as you start each phase.
- Auto-chain: issue -> review -> fix -> comment -> push gate (stop).

### Pre-Work Gate (optional)

When `--pre-work-gate` is passed (via `./drupal-issue.sh <id> --gate`), the workflow
adds a second stop point AFTER analysis/reproduction but BEFORE writing any code fix.
This lets the user review findings and steer the approach. See `/drupal-issue-review`
Step 4.5 for the gate format and user options.

Flow with gate: issue -> review -> **PRE-WORK GATE (stop)** -> fix -> comment -> push gate (stop).
Flow without gate (default): issue -> review -> fix -> comment -> push gate (stop).

### Additional Instructions

The shell script supports `-i "instructions"` to inject session-level guidance.
These appear as an `ADDITIONAL INSTRUCTIONS` preamble in the prompt. Apply them
throughout all phases and companion skill invocations. Do not repeat them to the user.

### Shell Entry Point

```bash
./drupal-issue.sh <issue_id_or_url> [--gate] [-i "additional instructions"]

# Examples:
./drupal-issue.sh 3579079
./drupal-issue.sh 3579079 --gate
./drupal-issue.sh 3579079 -i "focus on the entity access bug only"
./drupal-issue.sh 3579079 --gate -i "use approach from comment #7"
./drupal-issue.sh https://www.drupal.org/i/3579079 -i "ignore JS warnings"
```

## Skills — Auto-Invoke Rules

Skills MUST be invoked automatically via the Skill tool when their trigger conditions match. Do NOT wait for the user to type the slash command — if the condition matches, invoke it.

### Skill Chaining (Critical)

When a skill's instructions say to "delegate to" or "use" a companion skill (e.g., `/drupal-issue` says to delegate comment drafting to `/drupal-issue-comment`), you MUST invoke that companion skill via the Skill tool. Never inline the companion skill's behavior from memory. The companion skill contains formatting rules, tone guidelines, and structural requirements that you will miss if you skip it. This applies to ALL companion skill references, not just comments.

### Issue & Contribution Workflows
| Skill | Auto-invoke when |
|-------|-----------------|
| `/drupal-issue` | User provides a drupal.org issue URL or number |
| `/drupal-issue-review` | Need to reproduce a bug or test an MR in a fresh environment |
| `/drupal-issue-comment` | Writing up findings to post on a d.o issue |
| `/drupal-contribute-fix` | (1) `<module_name> module has an error/bug/issue`, (2) `Acquia/Pantheon/Platform.sh` + module problem, (3) any contrib module name + problem description, (4) about to edit files in `modules/contrib/*` or `core/*`, (5) packaging a fix for a d.o MR |

### Code Quality & Standards
| Skill | Auto-invoke when |
|-------|-----------------|
| `/drupal-coding-standards` | Checking or reviewing code against Drupal coding standards (any file type) |

### Development Patterns
| Skill | Auto-invoke when |
|-------|-----------------|
| `/drupal-dev-patterns` | Implementing hooks, creating services, DI, or security patterns |
| `/drupal-docs` | Need Drupal documentation, API reference, or practical code examples |

### Browser Automation
| Skill | Auto-invoke when |
|-------|-----------------|
| `/agent-browser` | Need to interact with a website: take screenshots, fill forms, click buttons, verify UI, reproduce visual bugs. Installed at `~/.cargo/bin/agent-browser` (v0.19.0, Rust CLI, headless Chrome). No npm/Playwright/Chrome MCP needed. |

### drupalorg-cli (Preferred for MR Operations)

Installed at `scripts/drupalorg` (v0.8.5 phar, runs via Docker PHP, no host PHP needed).
Always invoke from the workspace root with `./scripts/drupalorg`:

```bash
# From CONTRIB_WORKBENCH root:
./scripts/drupalorg issue:show 3579478 --format=llm

# Full command reference:
./scripts/drupalorg issue:show <nid> --format=llm        # Issue details
./scripts/drupalorg issue:get-fork <nid> --format=llm     # Fork + branches
./scripts/drupalorg issue:setup-remote <nid>              # Set up fork remote
./scripts/drupalorg issue:checkout <nid> <branch>         # Check out issue branch
./scripts/drupalorg mr:list <nid> --format=llm            # List MRs
./scripts/drupalorg mr:status <nid> <mr-iid> --format=llm # Pipeline status
./scripts/drupalorg mr:logs <nid> <mr-iid>                # Failing job logs
```

## Mid-work Data Fetching (drupal-issue-fetcher multi-mode)

Any skill at any phase can dispatch `drupal-issue-fetcher` with a specific mode.
11 modes available: `full`, `refresh`, `delta`, `comments`, `mr-status`, `mr-logs`,
`search`, `issue-lookup`, `raw-file`, `related`, `mr-diff`.

Dispatch: `./scripts/fetch-issue --mode <mode> --issue <id> [options]`

See `docs/fetcher-modes-reference.md` for the full mode table with dispatch
examples, required/optional flags, and output formats.

Key patterns:
- **Re-check comments:** `--mode comments` (lightweight, no MR state)
- **Poll pipeline:** `--mode mr-status` (phar-backed, returns JSON)
- **See what changed:** `--mode delta --since <ISO8601>` (filters to new items)
- **Fetch a raw file:** `--mode raw-file --url <gitlab-raw-url>`

## Solution Depth Gate (`/drupal-contribute-fix` Step 0.5 and Step 2.5)

Every autonomous `/drupal-contribute-fix` run goes through a two-mode
solution-depth gate that forces a narrow-vs-architectural comparison:

1. **Pre-fix gate (Step 0.5, ALWAYS runs)** — fresh opus subagent reads the
   review artifacts and drafts both a narrow and an architectural approach,
   fills in a trade-off table, and picks narrow/architectural/hybrid. Output:
   `DRUPAL_ISSUES/{id}/workflow/01b-solution-depth-pre.{md,json}`.

2. **Post-fix gate (Step 2.5, CONDITIONAL)** — sonnet subagent reads the
   actual drafted patch and scores it 1-5 for architectural reconsideration.
   Runs when any of 3 triggers fires:
   - Pre-fix agent set `must_run_post_fix: true`
   - `lines_changed > 50` in the diff
   - `files_touched > 3` in the diff

   Output: `DRUPAL_ISSUES/{id}/workflow/02b-solution-depth-post.{md,json}`.
   Score 1 = pass clean; 2-3 = pass with recommendation note; ≥4 = failed-revert.

### Failure path

When the post-fix gate returns `failed-revert`:
1. Controller writes `workflow/02c-recovery-brief.md` (architectural plan).
2. Controller copies `.drupal-contribute-fix/{issue_id}-*/` to
   `.drupal-contribute-fix/attempt-1-narrow/` for reference.
3. Controller destructively reverts the module tree (`git checkout -- .`,
   scoped `git clean -fd -- tests/ src/ config/`).
4. Controller writes `workflow/attempt.json` with `current_attempt: 2`.
5. Controller re-invokes `/drupal-contribute-fix`. The attempt-state check at
   the top of that SKILL.md skips preflight + pre-fix gate on attempt 2.

### Circuit breaker

Maximum 2 attempts per issue. If attempt 2 ALSO fails the post-fix gate, the
controller stops and presents an escalation prompt to the user. No third
attempt.

### The "no inline depth analysis" rule

Do NOT reason about solution depth inline in the controller. Always dispatch
`drupal-solution-depth-gate-pre` (opus) — it is a fresh subagent specifically
to avoid the controller's anchoring bias on whatever approach it already
proposed.

### Workflow state files (registry)

The `DRUPAL_ISSUES/<id>/workflow/` directory holds phase artifacts and
state files that drive self-healing reinstate flows (the pattern first
introduced by ticket 030 with `attempt.json` and extended by ticket 031
with `00-classification.json`). For the full registry of state files,
their owners, and their preflight-check locations, see
`docs/workflow-state-files.md`.

When adding a new state file in a future ticket, update the registry
there. The doc also documents the conventions for new state files
(numeric prefixes, status fields, retry bounds, escalation messages).

### Git & SSH
- Always use `git.drupal.org` (not `git.drupalcode.org`) for SSH remotes — see SSH config

### MR Workflow (Critical)
- **Never create a new MR if one already exists.** Push follow-up commits to the existing MR branch.
- **Never manually create MRs via GitLab URLs.** MRs are created via the "Issue fork" button on the drupal.org issue page.
- **Switch to the issue fork early.** After reproducing/verifying an issue, check out the issue fork branch and do all remaining work (fix, tests, PHPCS) directly there. Do not develop in the DDEV composer-installed copy and transplant later.
- **Rebasing MR branches is fine.** The drupal.org docs recommend rebasing over merging. The "X commits from branch" noise in GitLab is expected. Use `--force-with-lease` when pushing after a rebase.

## Cross-issue memory (bd)

bd serves as the workbench's institutional memory. Every workflow phase
writes its artifacts to bd via `scripts/bd-helpers.sh` (never inline `bd`
commands in skills). The fetcher queries bd for PRIOR KNOWLEDGE at the
start of each issue, surfacing maintainer preferences, module lore, and
historical context from prior issues in the same module.

To manually add maintainer preferences or module lore:

```bash
scripts/bd-helpers.sh remember-maintainer ai marcus "prefers extending existing events"
scripts/bd-helpers.sh remember-lore ai testing "use kernel tests for entity access checks"
```

These are surfaced automatically via `prior-knowledge.json` when working
on any issue in the same module.

All bd writes are best-effort — failure never blocks the workflow. The
on-disk `workflow/*.json` files remain the source of truth; bd is the
cross-issue queryability layer.

## Mechanical enforcement hooks

Two Claude Code hooks enforce the pre-push quality gate and workflow
completion mechanically (exit code 2 blocks the action and feeds stderr
back to the model):

1. **PreToolUse → `.claude/hooks/push-gate.sh`**: blocks `git push`
   unless `workflow/03-push-gate-checklist.json` exists, is < 60 min old,
   and all verdicts pass. This is the hard gate that replaces the prose
   IRON LAW "NEVER AUTO-PUSH."

2. **Stop → `.claude/hooks/workflow-completion.sh`**: blocks Claude from
   stopping if a review happened (`01-review-summary.json` exists within
   the last 120 min) but the push gate wasn't reached
   (`03-push-gate-checklist.json` missing). Forces the model to complete
   the full pre-push quality gate before claiming "done."

Both hooks also write bd memories for cross-session progress tracking
(best-effort; bd failure never blocks the hook's primary gate function).

The fix skill writes the checklist at Step 5.5, after all three review
agents report and before the push gate summary is presented.

To bypass hooks in an emergency: `claude --disable-hooks`.

## Orphaned DDEV cleanup

DDEV stacks accumulate when tmux sessions die (tmux server restart,
machine reboot, manual kill). To stop any stack whose launcher-created
tmux session is no longer alive, run:

```bash
./pause-orphaned-ddev.sh              # stop orphans
./pause-orphaned-ddev.sh --dry-run    # preview only, no stop
./pause-orphaned-ddev.sh register     # one-time backfill after a workbench upgrade
```

How it works: the `drupal-ddev-setup` agent writes `tui.json[<nid>].ddev_name`
when it creates a stack. The pause script reads that mapping, checks
each stack's recorded tmux sessions against live `tmux ls`, and stops
any stack whose sessions are all dead (via `ddev stop`, which DDEV 1.25+
uses instead of the older `ddev pause`). `tui.json` is NOT modified in
default mode (only in `register` mode).

Entries with an empty `sessions` array (stacks created outside the
launcher flow) are skipped with a warning — the script can't verify
liveness without recorded sessions, so it errs on the side of leaving
them alone.

Pre-ticket-032 stacks need a one-time `register` run to populate their
`ddev_name` field. After that, every new issue setup registers itself
automatically.

See `docs/tui-json-schema.md` for the tui.json schema reference.

## AI Module Testing

- When testing AI features in any Drupal AI modules (e.g., `ai`, `ai_agent`, `mcp`, etc.), always use **Anthropic** as the provider.
- The Anthropic API key is stored at `anthropic.key` in the workspace root. Read it from there when configuring the provider module or setting up keys for tests/usage.
- Feel free to set the key however is most convenient: paste it into the provider settings UI, inject it via `ddev drush config:set`, put it in config YAML, or hardcode it wherever needed. These are local test instances so there are no security concerns about where the key ends up.

## Agent Status Protocol (All Agents)

Every agent MUST report one of these statuses:

| Status | Meaning | Controller Action |
|--------|---------|-------------------|
| DONE | Completed successfully | Proceed to next phase |
| DONE_WITH_CONCERNS | Completed but has observations | Read concerns, address if relevant, proceed |
| NEEDS_CONTEXT | Missing info to proceed | Provide info, re-dispatch (max 2) |
| BLOCKED | Cannot proceed | Escalate: more context -> better model -> break task -> ask human |
| FAILED | Unrecoverable error | Retry once. If fails again, ask human |

When dispatching agents, handle all 5 statuses. Do not assume DONE.

### Agent Dispatch Rules

- Agents execute. They do not narrate what they are doing.
- Agent output must be structured: status code, findings, evidence. No prose filler.
- Never invent file paths, API endpoints, function names, or field names in agent prompts or output. If a value is unknown, use "UNKNOWN". Never guess.
- Token efficiency matters: pipeline calls compound. Return minimum viable output that satisfies the task.
- If an agent step fails: state what failed, why, and what was attempted. Stop.

## Available Agents

### `drupal-reviewer`
Code review before submitting to drupal.org. Uses prompt template at `skills/drupal-contribute-fix/agents/reviewer-prompt.md`.

**Reports:** APPROVED | NEEDS_WORK (with file:line issues) | CONCERNS (with observations)

### `drupal-verifier`
Verify fixes work in DDEV environment. Uses prompt template at `skills/drupal-contribute-fix/agents/verifier-prompt.md`.

**Reports:** VERIFIED (with evidence) | FAILED (with error output) | BLOCKED (with reason)

### `drupal-spec-reviewer`
Spec compliance review before code quality review. Verifies implementation matches issue requirements.

**Reports:** SPEC_COMPLIANT | SPEC_GAPS (with requirement:file mappings)

### `drupal-pipeline-watch`
Monitors GitLab CI pipeline after pushing to an MR. Dispatched automatically after push.

**Reports:** PIPELINE_PASSED | PIPELINE_FAILED (with error extract) | PIPELINE_TIMEOUT

### `drupal-ddev-setup`
Sets up a DDEV environment for a Drupal issue. Handles packagist and fork modes, discovers composer dependencies, registers ddev_name in tui.json (ticket 032).

**Reports:** DDEV_READY | FAILED (with error) | BLOCKED (with reason)

### `drupal-issue-fetcher`
Multi-mode data fetcher (11 modes: full, refresh, delta, comments, mr-status, mr-logs, search, issue-lookup, raw-file, related, mr-diff). Queries bd for PRIOR KNOWLEDGE (ticket 034).

**Reports:** COMPLETE | PARTIAL | FAILED

### `drupal-resonance-checker`
Pre-classification cross-issue resonance check. Queries bd + d.o for duplicate/related issues.

**Reports:** resonance report with Layer A (bd-local) + Layer B (d.o) matches

### `drupal-solution-depth-gate-pre`
Pre-fix solution-depth gate (model: opus). Forces narrow-vs-architectural comparison before code is written.

**Reports:** decision={narrow|architectural|hybrid}, must_run_post_fix={true|false}

### `drupal-solution-depth-gate-post`
Post-fix solution-depth gate (model: sonnet). Scores the drafted patch 1-5 for architectural reconsideration.

**Reports:** approved-as-is | approved-with-recommendation | failed-revert

## Workflow State Artifacts

Each workflow phase should write a state file to `DRUPAL_ISSUES/{issue_id}/workflow/`:

| Phase | File | Content |
|-------|------|---------|
| Classification | `00-classification.json` | Action type, rationale, next skill |
| Pre-work gate | `00b-pre-work-gate.json` | Findings summary, user decision (if gate enabled) |
| Review findings | `01-review-findings.md` | Static review results, test coverage gaps |
| Verification | `02-verification-results.json` | PHPCS, test, reviewer, verifier results |
| Push gate | `03-push-gate-summary.md` | Complete summary for user review |

This enables workflow resumption if a session is interrupted, and provides an audit trail.

## Workflow Tracking

All workflow skills use lazy TaskCreate for progress tracking. Create tasks only when starting a phase, not upfront.


<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
