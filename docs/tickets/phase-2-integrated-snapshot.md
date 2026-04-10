## Phase 2 Integrated Snapshot (as of 2026-04-10)

This section is mirrored across all COMPLETED phase-2 tickets (027, 028,
029, 030, 031, 032) so any ticket read in isolation gives the current cross-ticket
landscape. It complements — does not duplicate — each ticket's own
Resolution notes.

### Tickets completed so far

| # | Title | What it shipped |
|---|---|---|
| 027 | Fix stale SESSION_DIR in drupal-issue.sh | Launcher resume path works again. Uses `pwd -P` to get the canonical physical path + `sed 's\|[/_.]\|-\|g'` to encode it as Claude Code's projects-dir key. |
| 028 | Adopt bd as workbench data store | bd 1.0.0 installed (built from source), Dolt 1.85.0, shared-server mode, 11 custom statuses, SessionStart + PreCompact hooks, `docs/bd-schema.md` canonical schema doc. |
| 029 | Cross-issue resonance + data-layer consolidation | 11-mode multi-mode fetcher, `scripts/lib/data/` shared library, resonance check as Step 0.5 with category J classification, ALL inline fetches across the workbench migrated to the fetcher, new `raw-file` mode for arbitrary URL downloads. |
| 030 | Solution-depth gate (pre-fix + post-fix) | Two-mode subagent split into `-pre.md` (opus) and `-post.md` (sonnet). Pre-fix gate runs always at `/drupal-contribute-fix` Step 0.5; post-fix gate runs at Step 2.5 when any of 3 triggers fires (pre_fix_demanded \| lines > 50 \| files > 3). Failure path writes recovery brief, preserves attempt-1 diffs, destructively reverts, re-runs architectural; circuit breaker at 2 attempts. Haiku→sonnet migration of 3 existing agents rolled into this ticket per user directive. |
| 031 | Workflow determinism via sentinel + reinstate | Launcher pre-creates `workflow/00-classification.json` with `status: PENDING` (idempotent — never overwrites real classification). `/drupal-issue` new Step 2.5 overwrites with real data and mirrors to bd via best-effort `bd create`/`bd update`. `/drupal-issue-review` "Classification Sentinel Check" preflight reinstates with single retry on PENDING. New `docs/workflow-state-files.md` registry formalizes the pattern across all 10 phase-2 state files. |
| 032 | DDEV auto-pause for orphaned stacks | `pause-orphaned-ddev.sh` at workbench root (Option R). tui.json `ddev_name` field as ledger. Setup agent writes on creation; `register` subcommand backfills. Default mode read-only. `--dry-run`. Uses `ddev stop` (DDEV 1.25+). |

### How the six tickets integrate

```
+-------------------------------------------------------+
|  drupal-issue.sh (launcher)                           |
|  - SCRIPT_DIR via pwd -P (027)                        |
|  - SESSION_DIR = ~/.claude/projects/                  |
|      $(echo $SCRIPT_DIR | sed 's|[/_.]|-|g') (027)    |
|  - export PATH="$HOME/go/bin:$PATH" (029)             |
|  - export BEADS_DOLT_SHARED_SERVER=1 (028)            |
|  - Sentinel writer: pre-create workflow/             |
|      00-classification.json status=PENDING (031)      |
+-------------------------------------------------------+
               |
               v  claude --resume or --session-id
+-------------------------------------------------------+
|  /drupal-issue skill (controller)                     |
|                                                       |
|  Step 0:   drupal-issue-fetcher agent                 |
|              mode=full -> DRUPAL_ISSUES/<id>/         |
|              artifacts/ populated (029)               |
|                                                       |
|  Step 0.5: drupal-resonance-checker agent (029)       |
|              -> resonance_search.py                   |
|              Layer A: bd list queries (028)          |
|              Layer B: fetch-issue search mode (029)   |
|              -> workflow/00-resonance.{md,json}       |
|                                                       |
|  Step 1:   classify (categories A-I + J) (029)        |
|  Step 2.5: Persist classification + bd mirror (031)   |
|              -> workflow/00-classification.json       |
|                 (overwrites launcher sentinel)        |
|              -> bd create|update --status classified  |
|  Step 3+:  /drupal-issue-review flow, which in        |
|            Step 4.9 emits 01-review-summary.json      |
|            + 01a-depth-signals.json (030)             |
+-------------------------------------------------------+
               |
               v
+-------------------------------------------------------+
|  /drupal-issue-review skill                           |
|                                                       |
|  Preflight: Classification Sentinel Check (031)       |
|    if PENDING -> reinstate /drupal-issue (single try) |
|    if classified -> continue                          |
|    if missing -> fall through (direct invocation)     |
|                                                       |
|  Step 1-4: existing review flow                       |
|  Step 4.9: emit depth signals (030)                   |
+-------------------------------------------------------+
               |
               v
+-------------------------------------------------------+
|  /drupal-contribute-fix skill                         |
|                                                       |
|  Attempt state check (030): read attempt.json,        |
|    branch on current_attempt (1|2|>=3)                |
|                                                       |
|  FIRST STEP: preflight (existing)                     |
|                                                       |
|  Step 0.5: drupal-solution-depth-gate-pre (030)       |
|              opus, ALWAYS runs on attempt 1           |
|              -> 01b-solution-depth-pre.{md,json}      |
|              -> decides narrow|architectural|hybrid   |
|              -> sets must_run_post_fix flag           |
|                                                       |
|  TDD loop (existing)                                  |
|                                                       |
|  Pre-Push Quality Gate:                               |
|    Step 0:   CI parity (existing)                     |
|    Step 1-2: phpcs + phpunit (existing)               |
|    Step 2.5: post-fix gate trigger + dispatch (030)   |
|              compute patch stats                      |
|              should-run -> RUN|SKIP                   |
|              if RUN: dispatch sonnet post-fix gate    |
|              if failed-revert: write recovery brief,  |
|                 preserve attempt-1, revert, re-run    |
|              circuit breaker at attempt 2             |
|    Step 3-5: spec/code/verifier agents (existing)     |
|    Step 6:   draft comment (existing)                 |
|  Push Gate (existing)                                 |
+-------------------------------------------------------+
               |
               v
+-------------------------------------------------------+
|  Data stores (parallel, disjoint):                    |
|                                                       |
|  Workbench git repo:                                  |
|    - code, skills, agents, docs/tickets/              |
|    - CLAUDE.md, AGENTS.md, .beads/ config             |
|    - DRUPAL_ISSUES/ is gitignored                     |
|                                                       |
|  DRUPAL_ISSUES/<id>/: per-issue scratch               |
|    - artifacts/ populated by fetch_issue.py           |
|    - workflow/ populated by skills                    |
|      00-classification.json    (031, sentinel+real)   |
|      00-resonance.*     (029)                         |
|      01-review-summary.json    (030)                  |
|      01a-depth-signals.json    (030)                  |
|      01b-solution-depth-pre.*  (030)                  |
|      02a-patch-stats.json      (030)                  |
|      02a-trigger-decision.json (030)                  |
|      02b-solution-depth-post.* (030, when triggered)  |
|      02c-recovery-brief.md     (030, on failure)      |
|      attempt.json              (030, on failure)      |
|    - per-issue DDEV + gitlab clone                    |
|                                                       |
|  ~/.beads/shared-server/dolt/: bd database            |
|    - cross-session memory                             |
|    - outside workbench entirely                       |
|    - zero git contact after init                      |
+-------------------------------------------------------+
```

### What's live in the workbench that wasn't before phase 2

- **Resume actually resumes.** `./drupal-issue.sh <id>` on an existing session-map entry opens the prior claude session instead of silently starting fresh with a new UUID. (027)
- **Persistent cross-session memory.** bd stores per-issue state, cross-issue graph relationships, and named memories (`bd remember`) that survive across claude sessions and get auto-injected at SessionStart via `bd prime`. (028)
- **Single data layer.** Every d.o/gitlab data acquisition in the workbench goes through one of 11 `fetch_issue.py` modes. Zero inline `curl`, `WebFetch`, or duplicate API wrapper code remains in active skill scripts. (029)
- **Automatic duplicate / scope-expansion detection.** Every `/drupal-issue` invocation runs resonance at Step 0.5 BEFORE classification, surfacing candidates from bd local (Layer A) and d.o (Layer B) without user prompting. (029)
- **Mid-work re-fetch is first-class.** Any skill at any phase can dispatch `drupal-issue-fetcher` with a specific mode. The dispatch contract is documented in `CLAUDE.md` "Mid-work Data Fetching" section. (029)
- **Solution-depth gate.** Every autonomous `/drupal-contribute-fix` run goes through a mandatory pre-fix gate (opus) that forces a narrow-vs-architectural comparison before code is written, and a conditional post-fix gate (sonnet) that scores the drafted patch 1-5 for architectural reconsideration. Score ≥4 causes an in-skill revert + rerun with architectural approach; circuit breaker at 2 attempts. Catches the "workflow proposed narrow, user had to interject demanding the proper way" case without user prompting. (030)
- **Sonnet across all sub-agents.** No `model: haiku` anywhere in `.claude/agents/`. The three migrations (`drupal-issue-fetcher`, `drupal-ddev-setup`, `drupal-resonance-checker`) happened as a scope addition during ticket 030. (030)
- **Workflow determinism via sentinel.** The launcher pre-creates `workflow/00-classification.json` with `status: PENDING` for every new session. `/drupal-issue` Step 2.5 overwrites it with real classification data and mirrors to bd. `/drupal-issue-review`'s preflight check reinstates `/drupal-issue` (single retry) if it sees PENDING. Ticket 023's "every phase writes an artifact" contract is now mechanically enforced, not just prose. (031)

- **Orphaned DDEV stacks get stopped cleanly.** `./pause-orphaned-ddev.sh` reads `tui.json[<nid>].ddev_name` (populated by setup agent on new stacks, backfilled by `register` for existing), checks sessions against live `tmux ls`, stops orphans via `ddev stop`. Default mode read-only. Includes `--dry-run`. (032)

### Key commands available now

```bash
# === Initial issue fetch (what /drupal-issue Step 0 does automatically) ===
./scripts/fetch-issue --mode full \
  --issue <url-or-id> \
  --out DRUPAL_ISSUES/<id>/artifacts \
  --gitlab-token-file git.drupalcode.org.key

# === Mid-work re-fetch (any skill, any phase) ===

# Did anyone comment since I last checked?
./scripts/fetch-issue --mode comments --issue <id> --project <p> --out DRUPAL_ISSUES/<id>/artifacts

# Did the pipeline pass after push?
./scripts/fetch-issue --mode mr-status --issue <id> --mr-iid <iid> --out -

# Is there an existing d.o issue about "X"?
./scripts/fetch-issue --mode search --project <p> --keywords "entity" "access" --out -

# Quickly check a referenced parent issue
./scripts/fetch-issue --mode issue-lookup --issue <parent-id> --project <p> --out -

# Get the raw composer.json for a module branch
./scripts/fetch-issue --mode raw-file \
  --url "https://git.drupalcode.org/project/<m>/-/raw/<branch>/composer.json" --out -

# Delta fetch since timestamp
./scripts/fetch-issue --mode delta --issue <id> --project <p> \
  --since 2026-04-10T00:00:00Z --out DRUPAL_ISSUES/<id>/artifacts \
  --gitlab-token-file git.drupalcode.org.key

# === Resonance check (normally runs automatically at Step 0.5) ===
python3 .claude/skills/drupal-issue/scripts/resonance_search.py \
  --artifacts-dir DRUPAL_ISSUES/<id>/artifacts --out -

# === Solution-depth gate triggers (used by /drupal-contribute-fix Step 2.5) ===
python3 .claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py \
  compute-stats --module-path web/modules/contrib/<m> \
  --out DRUPAL_ISSUES/<id>/workflow/02a-patch-stats.json

python3 .claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py \
  should-run \
  --pre-fix-json DRUPAL_ISSUES/<id>/workflow/01b-solution-depth-pre.json \
  --patch-stats DRUPAL_ISSUES/<id>/workflow/02a-patch-stats.json \
  --issue-id <id> \
  --workflow-dir DRUPAL_ISSUES/<id>/workflow
# -> stdout: RUN or SKIP
# -> writes: workflow/02a-trigger-decision.json

# === bd ops ===
bd list --all
bd show <bd-id>
bd create "title" --external-ref "external:drupal:<nid>" -l "drupal-<nid>,module-<m>"
bd dep add <dependent> <dependency> --type blocks      # first arg = dependent
bd remember "insight" --key <key>
bd memories [search term]
bd prime                                               # what SessionStart hook runs

# === Phar CLI (parallel tool, still available) ===
./scripts/drupalorg issue:search <project> <keywords> --format=llm
./scripts/drupalorg issue:show <nid> --with-comments --format=json
./scripts/drupalorg mr:list <nid> --format=llm
./scripts/drupalorg mr:status <nid> <iid> --format=json
./scripts/drupalorg mr:logs <nid> <iid>
```

### Critical gotchas discovered during implementation

These are things future implementers of phase-2 tickets (031+) MUST know,
because they are non-obvious and cost real time to debug:

1. **`pwd` vs `pwd -P`** (from 027). Any path math in `drupal-issue.sh` or adjacent scripts must use `pwd -P`. Plain `pwd` returns the logical path (following symlinks or bind mounts), which doesn't match Claude Code's physical-path projects-dir key. The resume path silently breaks without the `-P`. The workbench's canonical physical path is `/mnt/data/drupal/CONTRIB_WORKBENCH`; its logical form `/home/alphons/drupal/CONTRIB_WORKBENCH` is a bind mount that `pwd` returns by default.

2. **Projects-dir encoding** (from 027). Claude Code encodes `/`, `_`, AND `.` as `-` in its projects-dir key. A sed rule of just `s|/|-|g` leaves underscores behind and fails to locate the real directory. Use `s|[/_.]|-|g`.

3. **`dolt.auto-push` AND `dolt.auto-pull` must be `false`** (from 028 + discovered in 029 Phase G). bd has **two** layers that can push to git:
   - `backup.git-push` — bd's backup layer
   - `dolt.auto-push` — Dolt's federation layer

   Disabling only the first leaves the second active, and it tries to push Dolt's internal `main` branch to the workbench git's `main` branch, failing with `non-fast-forward` on every bd write and hanging all subsequent bd operations. Both must be set:
   ```bash
   bd config set backup.git-push false
   bd config set dolt.auto-push false
   bd config set dolt.auto-pull false
   ```

4. **bd issue IDs are `<PREFIX>-<slug>`, not `bd-<nid>`** (from 028). Our workbench prefix is `CONTRIB_WORKBENCH`. The Drupal nid lives in **both** an external-ref (`external:drupal:3582345`) AND a label (`drupal-3582345`).

5. **`bd recall` does not exist** (from 028). Memory read is `bd memories [search]`; writes are `bd remember "insight" --key <key>`; auto-inject happens via `bd prime` at SessionStart.

6. **`bd update --notes` replaces, does not append** (from 028). To append cumulative content, you must read existing notes via `bd show --json`, concatenate, then write back.

7. **`bd delete` requires `--force` for non-interactive use** (from 028). Without it, bd prints a preview and refuses to delete.

8. **`--label-pattern` and `--label-regex` match ALL issues** (from 028 smoke tests). `bd list --label <exact>` is the reliable query. Fall back to `bd sql` for fuzzy label matches.

9. **Phar title search is AND-matched** (from 029). `./scripts/drupalorg issue:search <project> <k1> <k2> <k3>` requires ALL keywords in the issue title. The resonance scorer uses a keyword-count fallback (3 → 2 → 1) and supplements with explicit referenced-issue lookup via `issue-lookup` mode.

10. **Phar `mr:logs` returns 404 on passing pipelines** (from 029). Not an error; treat 404 as INFO, not PARTIAL.

11. **Python is the PRIMARY data layer** (from 029). The phar lacks `field_changes`, `is_system_message`, `mr_references`, `images`, and MR inline `DiffNote` comments with file/line positions. Phar fills only `mr-status` and `mr-logs` gaps.

12. **Fetch_issue.py output discipline: JSON/text to stdout, status lines to stderr** (from 029). Load-bearing when piping through `jq` or `git apply`. Do NOT merge streams with `2>&1` unless deliberately capturing both for debugging.

13. **`compute_patch_stats` needs files to be tracked or `git add -N`ed** (from 030 Task 13). `git diff --numstat` only reports tracked changes. In real `/drupal-contribute-fix` runs this is fine because the TDD loop stages files, but standalone synthetic testing needs `git add -N <newfile>` to make untracked files visible.

14. **Two agent files, not one, for the solution-depth gate** (from 030). Claude Code agent frontmatter takes a single `model:` value per file. Pre-fix needs opus and post-fix needs sonnet, so we split into `drupal-solution-depth-gate-pre.md` and `drupal-solution-depth-gate-post.md` instead of engineering a per-invocation model override.

15. **Post-fix gate triggers are objective-facts + agent-judgment, NOT keyword regex** (from 030 brainstorming Q3 pivot). The controller's `should_run_post_fix` only checks three things: `pre_fix.must_run_post_fix` boolean, `lines_changed > 50`, `files_touched > 3`. All reasoning about category, resonance bucket, maintainer criticism, and rationalization patterns happens INSIDE the opus pre-fix agent, which reads raw context. Mechanical keyword matching was rejected during design for false-positive risk.

16. **No CLI flags on `contribute_fix.py` for the gate re-run** (from 030). The spec originally suggested `--approach architectural --recovery-brief <path>` but the implementation uses a `workflow/attempt.json` state-file convention that the SKILL.md "Attempt state check" reads at the top. Cleaner, no argparse changes, and matches how the controller actually works.

17. **Sentinel idempotency rule: PENDING and empty status both mean "rewrite"** (from 031). The launcher's `write_sentinel=true` triggers when the file is missing OR `jq -r '.status // empty'` returns either `PENDING` or empty. Any other value (like `classified` or pre-031 values like `Active`/`Needs review`) means leave it alone. This makes the launcher safe to run on issue dirs that have pre-031 classification artifacts.

18. **bd mirror is best-effort, do not block on failure** (from 031). The classification bd mirror in `/drupal-issue` Step 2.5 uses `2>/dev/null || echo "..." >&2` so a dolt server outage doesn't break the skill. Workflow file is the source of truth.

19. **Pre-031 `00-classification.json` files use a different schema** (from 031). The audit on 2026-04-10 found 15 existing files written under a prior convention that stored Drupal issue statuses (`Active`, `Needs review`, etc.) directly. The new sentinel semantic (`PENDING` / `classified`) is incompatible by design — this is fine because both the launcher idempotency check and the preflight branching only react to exact `"PENDING"`, so old files fall through and proceed normally. No backfill needed.


20. **`ddev pause` does not exist in DDEV 1.25.1** (from 032). The correct command is `ddev stop`. The ticket draft and spec assumed `ddev pause`; existing stacks with status `paused` in `ddev list` were paused by an older DDEV version. `ddev stop` produces status `stopped`. `pause-orphaned-ddev.sh` uses `ddev stop` internally; the script name and labels say "pause" for human readability.

21. **tui.json has two writers now** (from 032). The launcher writes `title`/`fileCwd`/`actions`/`sessions` on every invocation; the `drupal-ddev-setup` agent writes `ddev_name` after `ddev start` succeeds. Both use `jq` with temp-file + `mv`. No locking needed — they run strictly sequentially (launcher before session spawn, agent inside session). Launcher preserves unknown fields. See `docs/tui-json-schema.md`.

22. **Empty `sessions[]` in tui.json → skip, not stop** (from 032). `register` creates entries with only `ddev_name` for stacks that had no pre-existing tui.json entry. Default mode skips these rather than treating empty sessions as "all dead" — the original ticket explicitly said "If no sessions ever recorded -> skip (manual ddev start, leave alone)."

### Where to look for detail

| Topic | Location |
|---|---|
| Phase 2 ticket index | `docs/tickets/00-INDEX.md` |
| bd schema + notation conventions | `docs/bd-schema.md` |
| Fetcher agent modes (all 11 documented) | `.claude/agents/drupal-issue-fetcher.md` |
| Resonance scorer implementation | `.claude/skills/drupal-issue/scripts/resonance_search.py` |
| Resonance agent prose | `.claude/agents/drupal-resonance-checker.md` |
| Pre-fix solution-depth gate (opus) | `.claude/agents/drupal-solution-depth-gate-pre.md` |
| Post-fix solution-depth gate (sonnet) | `.claude/agents/drupal-solution-depth-gate-post.md` |
| Post-fix trigger logic module + tests | `.claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py` + `tests/` |
| Mid-work re-fetch pattern + 7 examples | `CLAUDE.md` → "Mid-work Data Fetching" section |
| Solution depth gate summary | `CLAUDE.md` → "Solution Depth Gate" section |
| Shared data library | `scripts/lib/data/` (drupalorg_api, drupalorg_page_parser, drupalorg_urls, gitlab_api, fetch_issue, raw_fetch) |
| Phar CLI reference | `CLAUDE.md` → "drupalorg CLI" section |
| Launcher internals | `drupal-issue.sh` |
| tui.json schema reference | `docs/tui-json-schema.md` |
| Orphaned DDEV cleanup script | `pause-orphaned-ddev.sh` (workbench root) |
| Orphaned DDEV cleanup docs | `CLAUDE.md` → "Orphaned DDEV cleanup" section |
| Workflow state file registry | `docs/workflow-state-files.md` |
| Classification sentinel preflight | `.claude/skills/drupal-issue-review/SKILL.md` "Classification Sentinel Check" section |

Each completed ticket (027, 028, 029, 030, 031) also has its own
Resolution note with phase-by-phase implementation details.

### Phase 2 tickets NOT YET started

| # | Title | Priority | Depends on |
|---|---|---|---|
| 033 | RESEARCH: Agent Teams TaskCompleted hook prototype | P0 | — |
| 034 | Cross-issue long-term memory via bd | P1 | 028, 029 |
| 035 | RESEARCH: Mine orc/bernstein/kodo for launcher v2 | P0 | — |
| 036 | Comment quality gate (anti-filler) | P2 | — |
| 037 | Cleanup deprecated agents/tickets/scripts | P3 | — |
| 038 | Session pattern evidence log | P3 | — |

Research tickets (033, 035) are the recommended next moves because their
findings can shape implementation choices for future launcher improvements.
Ticket 034 (bd cross-issue memory) now has all its dependencies (028, 029,
031) satisfied and can proceed when appropriate — note that 031's
classification bd mirror is the data source 034 will query.
Dependency graph details in `docs/tickets/00-INDEX.md`.

### Snapshot refresh rule

When a new phase-2 ticket lands in COMPLETED status, this snapshot should
be updated in all previously-completed tickets AND added to the newly-
completed one. Keep the snapshot under 300 lines — if it grows, split the
"critical gotchas" into a separate standing reference doc and link here.
