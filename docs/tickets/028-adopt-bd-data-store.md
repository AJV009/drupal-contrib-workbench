# TICKET-028: Adopt bd (steveyegge/beads) as Workbench Data Store

**Status:** COMPLETED
**Priority:** P0 (Critical, foundation for phase 2)
**Affects:** Workbench root, `drupal-issue.sh`, all skill files that read/write workflow state, new `docs/bd-schema.md`
**Type:** Architecture

## Problem

Today the workbench has three separate ad-hoc data stores:

1. **`DRUPAL_ISSUES/session-map.json`** — flat file mapping issue id → claude session id
2. **`DRUPAL_ISSUES/<id>/workflow/0X-*.json|md`** — per-phase workflow artifacts
3. **Cross-issue dependencies** — tracked nowhere; recorded ad-hoc in commit messages with phpstan ignores (e.g., `phpstan.neon.dist - ignores error for soft dependency on ai_ckeditor event class` in issue 3581955 referencing not-yet-merged 3581952)

There is no programmatic way to ask "what other issues are related to this one?" or "what did we learn last time we touched module ai_agents?" Every cross-issue connection is re-derived manually each session.

## Solution

Initialize `bd` (https://github.com/steveyegge/beads) as the workbench's persistent store. bd provides:

- **18 dependency types** including `blocks`, `related-to`, `duplicates`, `supersedes`, `discovered-from` (first-class graph edges, not free-form labels)
- **Custom statuses** (max 50, with `active`/`wip`/`done`/`frozen` categories) — maps directly to our phase state machine
- **5 long-form text fields per issue** (`Description`, `Design`, `AcceptanceCriteria`, `Notes`, `SpecID`) plus arbitrary-JSON `Metadata` plus full `Comments` table — enough to hold all our workflow phase outputs
- **`bd remember`/`bd recall`** project-level memory injected at SessionStart via `bd setup claude` hook
- **`bd duplicates --auto-merge` and `bd merge`** for the scope-expansion / duplicate-detection problem (used by ticket 029)

## Critical limitations to know up front

1. **bd hooks are async fire-and-forget** (`internal/hooks/hooks.go`). Only `on_create`, `on_update`, `on_close` events. Hooks run AFTER the write succeeds and **cannot block transitions**. Do NOT rely on bd hooks for enforcement gates — that responsibility stays in skill prose for now (or moves to ticket 033 if Agent Teams hooks pan out).

2. **Embedded mode is single-writer** (file locking enforced). The user runs **3-6 parallel claude sessions at peak** (confirmed via session count audit). Embedded mode would serialize their writes painfully or fail outright. **We must use server mode** (`bd init --server` connecting to an external `dolt sql-server`).

## Implementation

### Step 1 — Initialize bd in server mode

```bash
cd /mnt/data/drupal/CONTRIB_WORKBENCH

# Install bd if not present (one-time, system or user install)
# See https://github.com/steveyegge/beads for current install instructions

bd init --server                # creates .beads/ with server-mode config
bd setup claude --project       # installs SessionStart hook for `bd prime`
```

### Step 2 — Configure custom statuses matching our phase state machine

```bash
bd config set status.custom \
  "classified:active,ddev_setup:wip,reproduced:wip,fix_drafted:wip,\
tests_added:wip,verified:wip,push_gate:wip,pushed:wip,\
awaiting_review:wip,merged:done,duplicate:done,deferred:frozen"
```

These map 1:1 to the phases already documented in CLAUDE.md "Workflow State Artifacts" section.

### Step 3 — Lifecycle: drupal-issue.sh manages the dolt sql-server (single instance)

Per user direction: "**one bd instance, keep running forever in the background, the issue sh will manage launching it and not launching it twice**."

Add to top of `drupal-issue.sh` (after the `SCRIPT_DIR` definition, before dependency check):

```bash
ensure_bd_server() {
  local pidfile="$SCRIPT_DIR/.beads/sql-server.pid"
  local logfile="$SCRIPT_DIR/.beads/sql-server.log"

  # Already running?
  if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile" 2>/dev/null)" 2>/dev/null; then
    return 0
  fi

  # Stale pidfile cleanup
  [ -f "$pidfile" ] && rm -f "$pidfile"

  echo "Starting bd dolt sql-server (background, persistent)..."
  cd "$SCRIPT_DIR"
  nohup dolt sql-server --config .beads/dolt-config.yaml \
    > "$logfile" 2>&1 &
  echo $! > "$pidfile"
  sleep 1  # give it a moment to bind the socket
}

ensure_bd_server
```

This is idempotent: subsequent invocations of `drupal-issue.sh` see the live PID and skip launch. Use a PID file + `kill -0` check; do NOT use `pgrep` (race-prone).

The dolt sql-server then runs forever in the background until explicitly killed. Add `dolt sql-server` to `~/.tmux.conf` startup or systemd-user if you want it to survive reboots — outside this ticket's scope.

### Step 4 — Memory notation schema (per user request)

Per user: "**Maybe we can have some kind of notations of memory to keeping stuff organized in our workflow.**"

Define the canonical mapping in a new file `docs/bd-schema.md`:

| What                              | Where in bd                          | Notation prefix              |
|-----------------------------------|--------------------------------------|------------------------------|
| Per-issue classification          | bd issue `Metadata` JSON             | `bd:phase.classification`    |
| Solution depth analysis (pre-fix) | bd issue `Design`                    | `bd:phase.solution_depth.pre`|
| Solution depth analysis (post-fix)| bd issue `Comments`                  | `bd:phase.solution_depth.post`|
| Review findings                   | bd issue `Description` (mirror)      | `bd:phase.review`            |
| Verification result               | bd issue `Comments` (one per push)   | `bd:phase.verification`      |
| Push gate summary                 | bd issue `Notes` (cumulative)        | `bd:phase.push_gate`         |
| Maintainer-feedback notes         | bd issue `Notes` + `bd remember`     | `bd:maintainer_pref.<module>`|
| Cross-issue resonance findings    | bd issue `Comments`                  | `bd:resonance.<bd-id>`       |
| Module-level conventions          | `bd remember "module:<X>:<key>"`     | `bd:module_lore`             |
| File-level history                | bd label `file:<path>`               | `bd:file_history`            |

This schema is referenced by tickets 029, 030, 031, 034 — they all write into specific slots defined here. If you change the schema later, update those tickets in lockstep.

### Step 5 — One-time backfill of existing issue dirs

Write a script `scripts/bd-backfill.sh` that walks `DRUPAL_ISSUES/[0-9]*/` and creates a bd issue per dir with:
- `--external-ref "do-<id>"`
- Status from any existing `workflow/00-classification.json`
- `Metadata` populated from any existing workflow artifacts

This should NOT auto-run; the user runs it once after init, reviews output, then commits.

## Acceptance

1. `bd list` returns the existing 38 issue dirs as bd issues after backfill
2. `bd dep add bd-X bd-Y --type blocks` succeeds; `bd dep tree bd-X` shows the edge
3. `bd config get status.custom` returns the 12 custom statuses
4. Running `./drupal-issue.sh 3577173` does NOT start a second dolt sql-server if one is already running (verify via `pgrep -fc dolt`)
5. Running claude on the workbench primes any `bd remember` entries on SessionStart (verify by setting `bd remember "test-key" "test-value"` and confirming it appears in the next session's prompt context)
6. `docs/bd-schema.md` exists with the notation table

## Sub-decisions to make during implementation

- **Where does the bd binary live?** System install vs. workbench-local. Probably system install via `go install` or release tarball. Document in CLAUDE.md.
- **Backup strategy** for `.beads/` directory — already covered by Dolt's git-syncable storage, but worth noting in docs.
- **Migration cutover** — old `session-map.json` and `workflow/*.json` files stay as transitional cache. Tickets 029/030/031/034 will gradually shift reads to bd.

## Dependencies

- 027 (fix stale SESSION_DIR) — needed because `drupal-issue.sh` is being modified here too; doing 027 first avoids merge conflicts

## Notes

This ticket establishes the SUBSTRATE only. Tickets 029, 031, 034 actually USE bd. Without bd, those tickets cannot function — that is why this is the foundation ticket and they all depend on it.

Future evolution: if the dolt sql-server proves flaky under heavy parallel load, evaluate moving bd into a Docker container alongside DDEV. Out of scope for this ticket.

## Resolution (2026-04-09)

Phase 2's foundation ticket is live. The implementation diverged from the original ticket in several important ways based on verifying bd's actual behavior before shipping.

### Discrepancies between ticket and bd reality

During Phase A research I ran a deep read of the upstream bd repo and discovered five places where the ticket's assumptions were wrong. Smoke testing confirmed each, and the implementation reflects the corrected understanding.

| # | Ticket claim | Reality | Decision |
|---|---|---|---|
| 1 | `bd init --server` requires a self-managed `dolt sql-server` with `ensure_bd_server()` pidfile dance | **Shared-server mode** (`BEADS_DOLT_SHARED_SERVER=1`) — bd auto-starts and manages `dolt sql-server` with idle-timeout. Zero launcher lifecycle code. | **Pivoted to shared-server mode.** Deleted the `ensure_bd_server()` plan. Single env export in `drupal-issue.sh`. |
| 2 | bd has async workflow hooks (`on_create`, `on_update`, `on_close`) that "cannot block transitions" | **CONTRADICTED**. bd has git hooks (synchronous, can block git ops) and editor hooks (SessionStart/PreCompact). No per-issue transition hooks exist at all. | The conclusion ("don't rely on bd for gate enforcement") is still right — the mechanism just doesn't exist. Documented in `docs/bd-schema.md` "What bd does NOT do". |
| 3 | `bd recall` exists for cross-session memory read | **CONTRADICTED**. Real surface: `bd remember` (write), `bd memories [search]` (read/search), `bd forget` (delete). `bd prime` auto-injects at SessionStart. Zero `bd recall` command. | `docs/bd-schema.md` documents the real memory surface. Ticket 034 was updated (appendix) to match. |
| 4 | External-ref strict format `external:<project>:<capability>` enforced by bd | **CONTRADICTED by smoke test**. bd accepts any string as external-ref, no validation. | We standardize on `external:drupal:<id>` by convention for consistency with ticket 034 memory keys, not because bd requires it. |
| 5 | "bd has 18 dependency types" | **CORRECTED**. Real count: **13** — `blocks, parent-child, conditional-blocks, waits-for, related, discovered-from, replies-to, relates-to, duplicates, supersedes, authored-by, assigned-to, approved-by`. | Schema doc lists all 13. Also `related-to` is `related` or `relates-to`; not a separate type. |

### Other discoveries during smoke testing

- **Custom status `deferred` collides with the built-in** `deferred` status. Configured 11 custom statuses instead of 12 (dropped our custom `deferred`, use bd's built-in instead).
- **Labels with colons work** (e.g. `file:src/Foo.php`) — this was UNVERIFIED in research, now confirmed. Ticket 034's file-history label scheme is viable.
- **`--label-pattern` and `--label-regex` both return all issues** in our smoke test — either a bd bug or we're misusing the glob syntax. Workaround: use `--label <exact>` or `bd sql` for fuzzy queries. Documented in `docs/bd-schema.md` "Known quirks".
- **`bd dep add` ordering**: first arg is the **dependent**, second arg is the dependency. "A blocks B" → `bd dep add A B --type blocks` makes A BLOCKED, with B as the blocker (verified).
- **`bd delete` requires `--force`** for non-interactive use; without it, bd prints a preview and refuses to delete.
- **Parallel writes work cleanly** — 3 concurrent `bd create` calls via `&` all succeeded. Shared-server mode confirmed for our 3-6 parallel sessions use case.
- **`bd init` auto-commits to git** and auto-modifies `CLAUDE.md` (adds a ~46-line "Beads Issue Tracker" section between `<!-- BEGIN BEADS INTEGRATION -->` markers). Not optional.
- **`bd prime` text is opinionated**: it injects prescriptive rules like "Prohibited: Do NOT use TodoWrite, TaskCreate, or markdown files for task tracking" at every SessionStart. This conflicts with our workflow. Documented in `docs/bd-schema.md` "Tensions with bd's opinions" as an explicit override; may revisit if bd overwrites our override on future `bd setup claude` runs.

### Install path pivot

- **AUR `beads-bin`** package (user installed first) is a prebuilt binary linked against `libicui18n.so.74` — incompatible with Arch's current ICU 78.3. Uninstalled.
- **Source build via `go install github.com/steveyegge/beads/cmd/bd@latest`** — required installing `go` (`sudo pacman -S go`) and `dolt` (`sudo pacman -S dolt`). Builds cleanly against system ICU 78.3. Binary lands at `~/go/bin/bd`.
- **PATH**: `~/go/bin` prepended in both `~/.zshrc` (interactive shells) and `drupal-issue.sh` (non-interactive / launched-claude shells). Belt-and-suspenders so the SessionStart hook can find `bd` regardless of parent environment.

### Backfill

Per user direction, **backfill was skipped**. bd starts empty. New issues populate organically as they're worked. Old `DRUPAL_ISSUES/<id>/workflow/0X-*.json|md` files stay on disk as historical cache.

### What shipped

- `drupal-issue.sh` — 2 new lines: `export PATH="$HOME/go/bin:$PATH"` and `export BEADS_DOLT_SHARED_SERVER=1`, after the SESSION_DIR line
- `~/.zshrc` — one line: `export PATH="$HOME/go/bin:$PATH"` with a bd comment header
- `.beads/` — bd init state (dolt-server.port, config.yaml, metadata.json, hooks/, interactions.jsonl, gitignore)
- `.claude/settings.json` — bd-written SessionStart + PreCompact hooks running `bd prime`
- `CLAUDE.md` — bd-inserted "Beads Issue Tracker" section between markers, lines 253-298
- `AGENTS.md` — bd-created, 84 lines, documentation
- `docs/bd-schema.md` — 213 lines, **the canonical schema reference for phase 2 tickets 029, 030, 031, 034**. Lists verified commands, notation prefixes, known quirks, and explicit override of bd's opinionated prime text.
- Git commit `2ce92a0 bd init: initialize beads issue tracking` (auto-created by `bd init`; reversible)
- Appendix notes appended to tickets 029, 030, 031, 034 cross-referencing `docs/bd-schema.md` for the corrections above

### Acceptance criteria

All 6 passed (documented inline in the implementation trace):
1. `bd list` works ✓ (empty, as expected with no backfill)
2. `bd dep add` + `bd dep tree` round-trip works ✓
3. `bd config get status.custom` returns 11 custom statuses ✓
4. Single `dolt sql-server` process under launcher env ✓
5. SessionStart hook installed and verified via `bd setup claude --check` ✓
6. `docs/bd-schema.md` exists ✓ (213 lines)

### Still open for future work

- **Schema doc is single source of truth**. When tickets 029/030/031/034 are implemented, they MUST cross-reference `docs/bd-schema.md` — the appendix notes added to those tickets call this out explicitly.
- **`bd prime` opinion vs our workflow** — if bd's prescriptive text becomes too noisy, we may need `bd setup claude --remove` and have skills invoke `bd` commands directly instead of relying on auto-prime. Revisit if it bites.
- **`~/drupal/CONTRIB_WORKBENCH` vs `/mnt/data/...` path duality** — bd init created everything under the canonical `/mnt/data/...` path. The 027 `pwd -P` fix ensures the launcher also uses the canonical path. Consistent across the stack now.

---

## Phase 2 Integrated Snapshot

See [phase-2-integrated-snapshot.md](phase-2-integrated-snapshot.md) for the
shared cross-ticket snapshot (maintained as a single file to avoid duplication).

