# Drupal Contribution Workbench

This workspace is for contributing to Drupal core and contributed modules on drupal.org.

## User

- **ajv009** on drupal.org is Alphons — the person running this Claude Code setup and all associated commands/skills.

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

### Git & SSH
- Always use `git.drupal.org` (not `git.drupalcode.org`) for SSH remotes — see SSH config

### MR Workflow (Critical)
- **Never create a new MR if one already exists.** Push follow-up commits to the existing MR branch.
- **Never manually create MRs via GitLab URLs.** MRs are created via the "Issue fork" button on the drupal.org issue page.
- **Switch to the issue fork early.** After reproducing/verifying an issue, check out the issue fork branch and do all remaining work (fix, tests, PHPCS) directly there. Do not develop in the DDEV composer-installed copy and transplant later.
- **Rebasing MR branches is fine.** The drupal.org docs recommend rebasing over merging. The "X commits from branch" noise in GitLab is expected. Use `--force-with-lease` when pushing after a rebase.

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

## Available Agents

### `drupal-reviewer`
Code review before submitting to drupal.org. Uses prompt template at `skills/drupal-contribute-fix/agents/reviewer-prompt.md`.

**Reports:** APPROVED | NEEDS_WORK (with file:line issues) | CONCERNS (with observations)

### `drupal-verifier`
Verify fixes work in DDEV environment. Uses prompt template at `skills/drupal-contribute-fix/agents/verifier-prompt.md`.

**Reports:** VERIFIED (with evidence) | FAILED (with error output) | BLOCKED (with reason)

### `drupal-contributor`
DEPRECATED. Use the `/drupal-issue` skill chain instead.

### `drupal-spec-reviewer`
Spec compliance review before code quality review. Verifies implementation matches issue requirements.

**Reports:** SPEC_COMPLIANT | SPEC_GAPS (with requirement:file mappings)

### `drupal-pipeline-watch`
Monitors GitLab CI pipeline after pushing to an MR. Dispatched automatically after push.

**Reports:** PIPELINE_PASSED | PIPELINE_FAILED (with error extract) | PIPELINE_TIMEOUT

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
