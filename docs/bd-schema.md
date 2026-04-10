# bd (beads) Workbench Schema

This document is the **canonical reference** for how the Drupal contrib workbench uses bd. Skills, agents, and launcher code that read or write bd data MUST conform to this schema. If this doc drifts from reality, fix the doc — it is the single source of truth phase 2 tickets (029, 030, 031, 034) rely on.

Background: ticket 028 introduced bd as the workbench's persistent data layer. See `docs/tickets/028-adopt-bd-data-store.md` for the original design rationale and `docs/tickets/028-adopt-bd-data-store.md`'s Resolution section for the discrepancies the original plan had with bd's actual behavior.

## Install and runtime

- **bd binary**: built from source via `go install github.com/steveyegge/beads/cmd/bd@latest`, lands at `~/go/bin/bd`. Version pinned in sessions by whatever was built most recently.
- **Dolt binary**: `sudo pacman -S dolt` (extra repo). bd's shared-server mode invokes `dolt sql-server` behind the scenes.
- **PATH setup**: `~/go/bin` is prepended to PATH in two places:
  1. `~/.zshrc` (interactive shells)
  2. `drupal-issue.sh` near the top (non-interactive / launched-claude shells)
- **Storage mode**: `BEADS_DOLT_SHARED_SERVER=1` exported in `drupal-issue.sh`. bd starts a single `dolt sql-server` on `127.0.0.1:3308` the first time it is needed, writes the port into `.beads/dolt-server.port`, and auto-stops the server after an idle timeout. No launcher-managed pidfile. If the server dies, the next `bd` invocation restarts it transparently.
- **Init state**: `.beads/` contains `config.yaml`, `metadata.json`, `dolt-server.port`, `hooks/`, `interactions.jsonl`. The Dolt database lives under `.beads/dolt/` (or wherever bd chooses under shared-server mode).

## Issue identity

bd issues are named `<PREFIX>-<slug>` where `<PREFIX>` defaults to the repo directory name (so ours is `CONTRIB_WORKBENCH`) and `<slug>` is a 3-character random suffix assigned at create time. Example: `CONTRIB_WORKBENCH-tpl`.

To map a bd issue to its Drupal issue we use **two mechanisms together**:

| Mechanism | Example | Purpose |
|---|---|---|
| `--external-ref` | `external:drupal:3580677` | Canonical identity. Human-readable, survives re-indexing, stored in the `external_ref` column. |
| Label `drupal-<id>` | `drupal-3580677` | Fast `bd list --label drupal-3580677` queries. |

**Verified**: bd does NOT validate external-ref format — any string is accepted. The `external:drupal:<id>` format is a convention, not an enforced schema.

**Create recipe**:
```bash
bd create "Drupal issue 3580677: Entity access bug in ai_agents" \
  --type bug \
  --priority 2 \
  --external-ref "external:drupal:3580677" \
  -l "drupal-3580677,module-ai_agents" \
  --metadata '{"drupal_issue_id": 3580677, "module": "ai_agents", "url": "https://www.drupal.org/i/3580677"}'
```

## Status state machine

Custom statuses configured via `bd config set status.custom "..."`. Current configuration:

| Custom status | Category | Meaning (phase) |
|---|---|---|
| `classified` | active | Classification JSON produced; next skill chosen |
| `ddev_setup` | wip | DDEV install started |
| `reproduced` | wip | Bug reproduced in local environment |
| `fix_drafted` | wip | Fix committed locally but not verified |
| `tests_added` | wip | Test coverage written for the fix |
| `verified` | wip | Static analysis + verifier passed |
| `push_gate` | wip | Awaiting push-gate review |
| `pushed` | wip | Pushed to drupal.org GitLab MR |
| `awaiting_review` | wip | Waiting on maintainer response |
| `merged` | done | Maintainer merged the MR |
| `duplicate` | done | Closed as duplicate of another issue |

**Built-in statuses we also use**:
| Built-in | Category | Meaning |
|---|---|---|
| `open` | active | Default on create, pre-classification |
| `in_progress` | wip | Generic "someone is working on this" (rarely used — prefer custom phases) |
| `blocked` | wip | Waiting on a `blocks` dependency to clear |
| `deferred` | frozen | Intentionally shelved (replaces the custom `deferred` we originally planned — it collided with the built-in) |
| `closed` | done | Generic close (use `merged` / `duplicate` when more specific) |
| `pinned` | frozen | Persistent issue, never auto-closes |
| `hooked` | wip | Attached to an agent hook (bd internal) |

**Transition convention**: skills write the new status via `bd update <id> --status <name>` and mirror the phase artifact per the notation table below. The status IS the single source of truth; `workflow/0X-*.json` files remain a transitional cache but should not be read preferentially over bd.

## Phase notation schema

Each workflow phase mirrors its artifact to bd using a specific slot. The "notation" column is a stable prefix that appears inside the written text so future readers (skill-maintainer, resonance checker, etc.) can reliably locate the phase data.

| Phase | bd slot | Command | Notation prefix (inside the field) |
|---|---|---|---|
| Classification | `metadata` JSON | `bd update <id> --metadata @00-classification.json` | `bd:phase.classification` |
| Pre-work gate | `notes` append | `bd update <id> --notes "$(cat 00b-pre-work-gate.json)"` | `bd:phase.pre_work_gate` |
| Review findings | `description` | `bd update <id> --description "$(cat 01-review-findings.md)"` | `bd:phase.review` |
| Solution depth (pre-fix) | `design` | `bd update <id> --design "$(cat 01b-solution-depth-pre.md)"` | `bd:phase.solution_depth.pre` |
| Solution depth (post-fix) | comment | `bd comment <id> "bd:phase.solution_depth.post $(cat 02b-solution-depth-post.md)"` | `bd:phase.solution_depth.post` |
| Solution depth (post-fix FAIL) | comment | `bd comment <id> "bd:phase.solution_depth.post.failed_revert $(cat 02b-solution-depth-post.md)"` | `bd:phase.solution_depth.post.failed_revert` |
| Solution depth (attempt 2 start) | comment | `bd comment <id> "bd:phase.solution_depth.attempt_2_start $(cat 02c-recovery-brief.md)"` | `bd:phase.solution_depth.attempt_2_start` |
| `bd:phase.push_gate.<nid>` | Stop hook (039) | Push gate reached, includes spec/reviewer/verifier verdicts |
| `bd:phase.session_incomplete.<nid>` | Stop hook (039) | Session ended before push gate was reached |
| `bd:phase.push_gate.blocked.<nid>` | PreToolUse hook (039) | Premature `git push` was blocked by the hook |
| `module.<mod>.maintainer_pref.<who>` | `bd remember` via `bd-helpers.sh remember-maintainer` (034) | Maintainer's stated preference for this module |
| `module.<mod>.lore.<topic>` | `bd remember` via `bd-helpers.sh remember-lore` (034) | Module-specific institutional knowledge |
| Verification result | comment (one per push) | `bd comment <id> "bd:phase.verification $(cat 02-verification-results.json)"` | `bd:phase.verification` |
| Push gate summary | `notes` append (cumulative) | `bd update <id> --notes "$(cat 03-push-gate-summary.md)"` | `bd:phase.push_gate` |
| Cross-issue resonance | comment | `bd comment <id> "bd:resonance $(cat resonance-report.md)"` | `bd:resonance.<related-bd-id>` |

**Note on `--notes`**: bd's `--notes` flag REPLACES the field, it does not append. To append, skills must read existing notes via `bd show <id> --json`, concatenate, then write back. A helper `scripts/bd-helpers.sh` in ticket 034 will wrap this.

## Memory / cross-session knowledge

bd has a project-scoped key-value memory store accessed via:

| Command | Purpose |
|---|---|
| `bd remember "<insight>" --key <key>` | Write a memory with a stable key |
| `bd memories [search term]` | List or grep memories |
| `bd forget <key>` | Delete a memory |
| `bd prime` | Dump current workflow context + memories (runs automatically at SessionStart via the `.claude/settings.json` hook bd installs) |

**No `bd recall` command**. Earlier ticket drafts referenced `bd recall` — this does not exist. Use `bd memories` for listing/searching and rely on `bd prime` for auto-priming at session start.

**Memory key convention** (for ticket 034):

| Kind of memory | Key format | Example |
|---|---|---|
| Maintainer preference | `module.<module>.maintainer_pref.<maintainer>` | `module.ai_agents.maintainer_pref.cadence96` |
| Module-level lore | `module.<module>.lore.<topic>` | `module.ai_agents.lore.serializer_hardening` |
| File-level gotcha | `file.<slugified-path>.gotcha.<topic>` | `file.src-plugin-aiagent-agentbase-php.gotcha.perf` |
| Cross-session workflow note | `workflow.<topic>` | `workflow.comment_quality.filler_patterns` |

Slugify: replace `/`, `.`, `_` with `-` (matches the launcher's SESSION_DIR encoding).

## Dependency graph

bd has **13 dependency types** (not 18 as earlier ticket drafts claimed):

**Workflow relationships** (affect `bd ready`):
- `blocks` — source blocks target until source is closed
- `parent-child` — source contains target (epic decomposition)
- `conditional-blocks` — source blocks target only under certain conditions
- `waits-for` — source waits on target without hard-blocking

**Association relationships** (informational):
- `related` — loose link
- `discovered-from` — this issue was discovered while working on another
- `replies-to` — comment-like threading
- `relates-to` — alias of `related` in some contexts
- `duplicates` — this issue duplicates another (used by 029)
- `supersedes` — this issue replaces another

**Entity relationships** (rare in this workbench):
- `authored-by`, `assigned-to`, `approved-by`

**Add syntax** (verified — note the ordering):
```bash
bd dep add <dependent-issue> <dependency-issue> --type blocks
# ^ first arg depends on second arg, via the type
# Example: "tpl is blocked by fgm" → bd dep add tpl fgm --type blocks
```

**Query**:
```bash
bd dep tree <issue>           # show dependency tree
bd dep list <issue>            # flat listing
bd dep remove <src> <dst>      # remove edge
```

## Query cheat-sheet

All verified via smoke tests:

| Goal | Command |
|---|---|
| All issues | `bd list` |
| By status | `bd list --status classified` |
| By exact label | `bd list --label drupal-3580677` |
| By any of multiple labels | `bd list --label-any module-ai_agents,module-ai` |
| Notes full-text | `bd list --notes-contains "serializer"` |
| Description full-text | `bd list --desc-contains "entity access"` |
| Ready work (no open blockers) | `bd ready` |
| Open only | `bd list --status open` |
| JSON output | `bd list --format json` or `bd list --json` |
| Raw SQL | `bd sql "SELECT ..."` (against the Dolt DB) |

**Known quirks (from smoke testing)**:
- `--label-pattern "file:*"` and `--label-regex "^file:"` both return all issues in the smoke test — either a bd bug or the glob syntax is different from what's documented. Use `--label <exact>` reliably, fall back to `bd sql` for fuzzy label queries.
- `bd delete` without `--force` prints a preview and does NOT delete. Add `--force` for non-interactive delete.

## What bd does NOT do (important gotchas)

1. **No workflow transition hooks**. bd's hooks are git hooks (pre-commit, post-merge, etc., installed in `.git/hooks/`) and Claude Code editor hooks (SessionStart, PreCompact). There is **no** `on_issue_status_change` style hook. If you need a side effect when an issue transitions from `classified` → `ddev_setup`, implement it in the skill itself or in launcher code — not in bd.

2. **`bd duplicates --auto-merge` does not combine fields**. It closes the source issue and adds a `related` link to the target. Ticket 029's resonance-check MUST handle any actual field merging itself.

3. **`--notes` replaces**. As noted above, to append you read + concat + write.

4. **Git commits**. `bd init` auto-commits to git if the workbench is a git repo. Subsequent `bd update` and similar operations also commit automatically ("bd auto-commit to Dolt"). Keep this in mind when running bd in dirty-tree contexts.

5. **bd's opinionated `bd prime` output**. The `bd prime` text injected at SessionStart contains prescriptive rules like "Prohibited: Do NOT use TodoWrite, TaskCreate, or markdown files for task tracking". This conflicts with our workflow (which uses TodoWrite and docs/tickets/ actively). We currently override with a local note in the `BEGIN BEADS INTEGRATION` section of CLAUDE.md; if bd overwrites it on future `bd setup claude` runs we may need to disable the hooks entirely via `bd setup claude --remove`.

6. **bd writes an `AGENTS.md`** at the repo root on init. We leave it alone (it is documentation, not runtime).

## Tensions with bd's opinions

bd's design assumes it is THE task tracker. Our workbench has:
- `docs/tickets/` — markdown phase-2 tickets (this is how you're reading this doc)
- `TodoWrite` — in-session task tracking inside claude
- Workflow state files on disk — `DRUPAL_ISSUES/<id>/workflow/0X-*.json|md`
- bd issues — the new persistent substrate

bd's prime text calls several of these "Prohibited". We do NOT follow that directive. Instead:
- `docs/tickets/` remains the planning substrate for phase-2 work (it is markdown, version-controlled, human-edited — bd is not a good fit for planning tickets that span weeks of design)
- `TodoWrite` remains the in-session progress tracker (it is session-scoped; bd is cross-session)
- `workflow/0X-*.json|md` files remain as transitional cache; they will gradually shift to being write-only mirrors of bd data
- bd is the **cross-session persistent store** for per-issue workflow state, memories, and cross-issue graph

This doc is the override. If a skill reads `bd prime` output and sees conflicting advice, this schema wins.

## Verification log (2026-04-09)

The following were smoke-tested during ticket 028 implementation, on the real workbench:

| Check | Result |
|---|---|
| bd source build via `go install` | bd 1.0.0 (dev) builds cleanly against system ICU 78.3 |
| `bd init` with `BEADS_DOLT_SHARED_SERVER=1` | ✓ dolt server started on 127.0.0.1:3308, `.beads/` populated |
| Custom statuses (11 of 12; `deferred` dropped due to built-in collision) | ✓ `bd statuses` shows all |
| Create with `external-ref "external:drupal:<id>"` | ✓ accepted, persisted, retrievable via `bd show` |
| Create with plain external-ref `do-<id>` | ✓ also accepted (no format validation) |
| Create with colon-label `file:src/Foo.php` | ✓ accepted, exact-match query works |
| `bd dep add A B --type blocks` | ✓ A becomes BLOCKED with B as its blocker in `bd dep tree` |
| 3 parallel `bd create` calls via `&` | ✓ all 3 created, no lock contention |
| `bd remember` + `bd memories` + `bd prime` | ✓ memory stored and auto-included in prime output |
| `bd setup claude --check` | ✓ project hooks present in `.claude/settings.json` |
