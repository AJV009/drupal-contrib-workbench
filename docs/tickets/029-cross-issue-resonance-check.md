# TICKET-029: Pre-Classification Cross-Issue Resonance Check

**Status:** COMPLETED
**Priority:** P0
**Affects:** `.claude/skills/drupal-issue/SKILL.md`, new agent `.claude/agents/drupal-resonance-checker.md`
**Type:** Enhancement

## Problem (with concrete evidence)

The workflow does not proactively detect when a new issue is actually a scope expansion of, or duplicate of, a recently worked issue. The user has to notice and intervene manually.

**Session `2c83c3e7-c7aa-4e55-a2f3-5affa0787990.jsonl` on issue 3583760** (Apr 9 2026, 113 user messages):
> "I rather have this fixed man, also thinking why stop at name, lets also patch that other arguments thing, look into that issue, pull its complete conversation and see what is being done there. **MAYBE we can move all the stuff we are doing here to that issue, if the conversations there make sense for this scope**"

> "I got push access to the existing MR in 3582345, **lets work on this issue complete end to end and go beyond just some particular argument and stuff**... **draft a comment mentioning why we expanded the scope of this issue**"

**Session `14f9b85b-2627-45a3-ba7c-955836268a1f.jsonl`** (Apr 9 2026):
> "So i previously worked on this https://www.drupal.org/project/ai_agents/issues/3560681 and after sometime I worked on this https://www.drupal.org/project/ai/issues/3582345... **I just need you to verify if anything from the ai_agents issue need to removed or refactored to accommodate ai issue 3582345 once it gets merged**"

In both cases, the workflow had no programmatic way to surface the connection on its own.

## Solution

Insert a new mandatory **Step 0.5 — Resonance Check** between the fetcher (step 0) and classification (step 1) in `/drupal-issue` SKILL.md.

### New agent: drupal-resonance-checker

`.claude/agents/drupal-resonance-checker.md`

**Inputs**: the freshly-fetched issue metadata (title, body, module name, files mentioned in MR diffs, error messages from comments).

**Behavior**:
1. Query bd: `bd list --label-any "module:<module_name>"` for past work in the same module
2. Query bd: `bd list --search "<keywords from issue title>"`
3. Query bd: `bd list --notes-contains "<key file path>"` for issues that touched the same file
4. For each candidate, compute a similarity score from:
   - File paths overlap with the candidate's recorded touched files (from `bd:phase.review` data)
   - Function/class names mentioned in both
   - Error messages mentioned in both
   - Direct cross-references in the issue text (e.g., "see #NNNN")
5. Return a structured `RESONANCE` report (text format, parsed by controller):

```
RESONANCE_REPORT
================
DUPLICATE_OF: bd-3582345  (confidence: 92%)
  Rationale: same files touched, same root cause class, target MR is open

RELATED_TO:
  - bd-3560681 (confidence: 67%) — shares ToolsFunctionOutput refactor
  - bd-3580690 (confidence: 54%) — same module, different feature

BLOCKED_BY:
  - bd-3581952 (status: needs_review) — provides event class needed by this issue

SCOPE_EXPANSION_CANDIDATE:
  - bd-3582345 — open MR, user has push access, this issue could be folded

NONE: false
STATUS: DONE
```

If `confidence > 80` for any DUPLICATE_OF or SCOPE_EXPANSION_CANDIDATE, the agent ALSO returns a draft "close as duplicate" or "fold into existing" comment template appended to the report.

**Model selection**: Haiku is sufficient for this — it's a structured-search task, not deep reasoning.

### Controller integration in /drupal-issue SKILL.md

Add Step 0.5 after Step 0 (fetcher dispatch) and before Step 1 (classification):

```markdown
## Step 0.5 — Resonance Check (Mandatory)

After the fetcher returns, IMMEDIATELY dispatch drupal-resonance-checker. You
MUST read its full report before classifying.

If the report has DUPLICATE_OF (>80% confidence) or SCOPE_EXPANSION_CANDIDATE,
classification gains a new option: "fold into bd-NNNN, close this as duplicate."
The push gate then presents the close-comment instead of a fix.

Write the resonance report to:
  - workflow/00-resonance.md (on disk, transitional cache)
  - bd issue: bd issue update bd-<id> --comment "$(cat workflow/00-resonance.md)"
    using the bd:resonance.<bd-id> notation prefix from docs/bd-schema.md
```

### Update classification action types

Add a new classification category to the existing A-I list in SKILL.md:

| Category | Meaning | Next skill |
|---|---|---|
| **J** | Duplicate / fold into existing issue | `/drupal-issue-comment` (close-as-duplicate) |

Category J is selected ONLY when resonance check returns `DUPLICATE_OF` or `SCOPE_EXPANSION_CANDIDATE` with confidence > 80.

## Acceptance

1. Re-run on issue 3583760 → resonance report contains `SCOPE_EXPANSION_CANDIDATE: bd-3582345`
2. Re-run on issue 3581955 → resonance report contains `BLOCKED_BY: bd-3581952`
3. Re-run on a brand-new unique issue → report contains `NONE: true`
4. New file `workflow/00-resonance.md` exists for every issue worked after this lands
5. `bd show bd-<id>` includes the resonance report as a comment with `bd:resonance.*` notation
6. Classification action types include category J

## Dependencies

- **028** (bd must be initialized and populated) — hard dependency. Without bd, the resonance check has nothing to query.

## Notes

This ticket is one of the highest-leverage in phase 2 because it converts a recurring user-injected nudge ("look into that issue, pull its conversation, MAYBE we can fold this in") into a mechanical step that runs every time without prompting.

The resonance checker should be conservative on the close-as-duplicate path — false positives are very costly (closing a real bug as duplicate). When confidence is in the 60-80 range, present as RELATED_TO only, not as DUPLICATE_OF.

## Research update from ticket 028 (2026-04-09)

Ticket 028 smoke-tested bd's real behavior. Several assumptions in this ticket's examples need to be read with corrections — the ticket's design intent is unchanged, but the exact commands/IDs should be sourced from `docs/bd-schema.md` when implementing.

**Corrections applicable to this ticket:**

1. **bd issue ID format**. The examples in this ticket use `bd-3582345`, `bd-3560681`, etc. as IDs. These are not real bd IDs. bd assigns IDs of the form `<PREFIX>-<slug>` where the prefix is the repo directory name (ours is `CONTRIB_WORKBENCH`) and the slug is a 3-character random suffix (e.g. `CONTRIB_WORKBENCH-tpl`). The Drupal issue number (`3582345`) lives in:
   - `--external-ref "external:drupal:3582345"` (canonical)
   - Label `drupal-3582345` (for fast `bd list --label drupal-3582345` queries)

   The RESONANCE_REPORT format in this ticket should therefore read something like:

   ```
   RESONANCE_REPORT
   ================
   Issue: drupal-3582345 (bd: CONTRIB_WORKBENCH-abc)
   Status: SCOPE_EXPANSION_CANDIDATE
   Confidence: 92%

   Candidates:
     - bd: CONTRIB_WORKBENCH-xyz (drupal-3560681, confidence: 67%) — ...
   ```

2. **Resonance query commands**. Use the verified query cheat-sheet from `docs/bd-schema.md`:
   ```bash
   bd list --label module-ai_agents --format json
   bd list --label drupal-3560681
   bd list --desc-contains "ToolsFunctionOutput"
   ```
   Do NOT use `bd list --label-pattern "module:*"` — it was observed to return all issues in smoke testing; use exact label match or fall back to `bd sql` for fuzzy matches.

3. **Duplicate merge semantics**. This ticket references `bd duplicates --auto-merge`. Per smoke testing: "merge" here means "close the source issue and add a `related` link to the target". It does NOT combine fields. If the resonance checker decides to fold issue A into issue B, it must manually copy any fields worth keeping BEFORE calling close/merge.

4. **Dep-add ordering**. `bd dep add <dependent> <dependency> --type blocks` — first arg is the dependent (becomes BLOCKED), second is the blocker. Verified in smoke testing.

5. **`bd comment`**. Resonance findings get written to an issue comment per the phase notation schema in `docs/bd-schema.md`:
   ```bash
   bd comment <bd-id> "bd:resonance.<related-bd-id>

   $(cat resonance-report.md)"
   ```

**No rewrite of this ticket is needed**. The design and acceptance criteria remain correct; implementation should cross-reference `docs/bd-schema.md` for exact command syntax.

## Expanded scope (2026-04-09)

During implementation planning for this ticket, an audit of the workbench's
d.o/gitlab fetching surface revealed **five parallel code paths** for the same
underlying need:

1. `drupal-issue-fetcher` agent → `fetch_issue.py` (bulk fetch, Python)
2. `drupal-issue-fetcher` Step 4b → inline `curl` to api-d7 (related issues, shell)
3. `drupal-contribute-fix/lib/drupalorg_api.py` + `contribute_fix.py preflight` (Python)
4. `scripts/drupalorg` wrapper + `drupalorg.phar` (PHP CLI, v0.8.5, parallel tool — **not** broken; used today for LLM-controller convenience calls)
5. Scattered inline `WebFetch` / `curl` in other skills

Adding a sixth code path for resonance's d.o search would have cemented the
fragmentation. The revised scope of this ticket **consolidates all five paths
into a single fetcher surface**, then builds resonance on top as the first
consumer of the new API.

Per user direction: no follow-ups, no partial migrations. All inline fetches
migrate in this ticket. The phar path is fixed (not deleted) — wherever it
actually lives on disk, references are updated to point to the real location.

### New scope components

**(A) Data layer consolidation.** Move `drupalorg_api.py` and `gitlab_api.py`
from `.claude/skills/drupal-contribute-fix/lib/` to a workbench-shared
location at `scripts/lib/data/`. All consumers updated. Old location deleted
(per user direction: "no backward compatibility for now"). A brief
re-export shim is kept at the old location during Phase A only, deleted
when all imports are migrated in Phase C.

**(B) Multi-mode drupal-issue-fetcher.** Rewrite the fetcher agent to accept
an explicit mode + args. Modes:

| Mode          | Purpose                                           |
|---------------|---------------------------------------------------|
| `full`        | First-time bulk fetch (existing behavior, default)|
| `refresh`     | Re-fetch everything, ignore cache                 |
| `delta`       | Only what's new since the last fetch              |
| `comments`    | Comments only, fast (mid-work "did anyone reply?")|
| `mr-status`   | Pipeline state + mergeability                     |
| `related`     | Related-issues discovery (replaces Step 4b curl)  |
| `search`      | Keyword search on d.o (used by resonance + preflight) |
| `issue-lookup`| Light metadata only (no body)                     |
| `mr-diff`     | Just the diff for an MR                           |

Each mode returns a mode-specific enriched summary with structured fields.
`full` remains the default if mode is not specified. The underlying
`fetch_issue.py` CLI is expanded with subparsers for each mode; the
`drupal-issue-fetcher` agent prose is rewritten to document them.

**(C) Phar framing corrected.** Earlier planning assumed the phar was
broken or phasing out. Audit showed the opposite: phar lives at
`scripts/drupalorg.phar` (v0.8.5), all references in CLAUDE.md and SKILL.md
Step 10 are correct, and the wrapper `scripts/drupalorg` works as invoked
from the workbench root. **Phar stays untouched** as a parallel tool for
skill-prose convenience calls. It is also used as the backend for two
specific modes (`mr-status`, `mr-logs`) that Python does not currently
cover — wrapped through `fetch_issue.py` so callers never shell-exec phar
directly. All other 8 modes remain Python-backed per the existing Python
data layer (which was built specifically to handle `field_changes`,
`is_system_message`, `mr_references`, `images`, and MR inline
discussions — all gaps the phar does not fill).

**(D) Inline fetch audit and complete migration.** Grep the workbench for
every inline `WebFetch`, `curl`, and direct `drupalorg.phar` call. Produce
an audit report sorted by (1) count of references and (2) surrounding
context — what the call is fetching, how critical, what the failure mode
is. Migrate **every** site to dispatch the `drupal-issue-fetcher` agent
with the appropriate mode. No deferrals.

**(E) Mid-work re-fetch pattern documented.** `CLAUDE.md` and
`/drupal-issue` SKILL.md document the idiom: "any skill can dispatch
`drupal-issue-fetcher <mode> <args>` at any phase for fresh data." Include
at least 3 concrete examples:
- "did anyone comment while I was working?" → `mode=comments since=<ts>`
- "check MR pipeline after push" → `mode=mr-status`
- "fetch a referenced parent issue mid-review" → `mode=full issue=<parent_id>`

**(F) Resonance check (original 029 feature, unchanged intent).** Built
on top of the new fetcher API. New scorer at
`.claude/skills/drupal-issue/scripts/resonance_search.py`:

- Layer A: `bd list --label module-<X> --format json` subprocess calls
- Layer B: `python3 scripts/lib/data/fetch_issue.py search --project <p> --keywords <k>` subprocess calls (NOT direct `drupalorg_api.py` import)
- Deterministic 7-signal scorer with 4 buckets:
  - `<40` NONE
  - `40-60` RELATED_TO
  - `60-80` SCOPE_EXPANSION_CANDIDATE
  - `>80` DUPLICATE_OF / strong SCOPE_EXPANSION_CANDIDATE
- JSON output consumed by the resonance agent

New agent at `.claude/agents/drupal-resonance-checker.md` (model: haiku):
- Dispatched by `/drupal-issue` at Step 0.5 (between fetch and classify)
- Runs the scorer
- Formats RESONANCE_REPORT text
- Writes `workflow/00-resonance.md` (disk artifact)
- Returns report to controller

Silent degrade: if Layer B fails (network error), report continues with
Layer A only plus a `"Layer B unavailable"` note. Hands-free flow preserved.

**(G) `/drupal-issue` SKILL.md integration.** Step 0.5 "Resonance Check"
section. New classification category J "fold into existing issue."
Rationalization Prevention entry for skipping resonance. Cross-reference
to the mid-work re-fetch pattern docs.

### Why this all fits in one ticket

The resonance check is the FIRST consumer of the new fetcher `search`
mode. Doing them together means:

1. We validate the mode API by using it immediately — not in some future
   ticket that never happens
2. Resonance lands with a clean call graph instead of being a sixth code
   path we'd have to migrate later
3. The mid-work re-fetch pattern has a live working example to reference
4. The whole d.o/gitlab data layer is consolidated in one atomic change
   instead of dragged out over multiple tickets

### Out of scope (explicit)

- Redesigning `fetch_issue.py`'s internal architecture beyond adding mode
  subcommands (it stays as one file, expanded)
- Rewriting `gitlab_api.py` — just move it
- Adding bd queries beyond what original 029 specified
- Changing skill flow logic except where it dispatches the fetcher
- Converting `scripts/lib/data/` into a formal Python package (stays as
  flat modules imported via sys.path, same as today's layout)
- Replacing the phar with a Python reimplementation — phar stays as-is,
  we only fix its path

### Updated acceptance criteria

Original A1–A6 still apply (see "Research update from ticket 028" section
for empty-bd-friendly substitutes), plus:

- **A7**: `python3 scripts/lib/data/fetch_issue.py <mode>` works for all 9
  modes, each returns structured JSON
- **A8**: `drupal-issue-fetcher` agent dispatched with explicit mode
  returns correct mode-specific summary
- **A9**: `drupalorg_api.py` and `gitlab_api.py` exist ONLY at
  `scripts/lib/data/` (old `.claude/skills/drupal-contribute-fix/lib/`
  path grep-clean)
- **A10**: All known consumers of the old paths updated to the new
  location
- **A11**: `scripts/drupalorg` CLI remains functional (grep-clean:
  no broken references anywhere in the workbench). Phar is used as the
  backend for `mr-status` and `mr-logs` modes in `fetch_issue.py`
- **A12**: Resonance scorer dispatches `fetch_issue.py search` subprocess
  for Layer B; does NOT import `drupalorg_api` directly
- **A13**: `CLAUDE.md` documents mid-work re-fetch pattern with ≥ 3
  concrete examples
- **A14**: Every inline fetch site found in Phase A audit is migrated to
  fetcher dispatch — no sites deferred, audit report shows 100% migration
- **A15**: `fetch_issue.py` is the single Python entry point for all 10 modes; 8 modes Python-backed, 2 modes (`mr-status`, `mr-logs`) route to phar via subprocess; caller never shell-execs phar directly

## Resolution (2026-04-09)

Ticket 029 shipped with its expanded scope (original resonance check + full
data-layer consolidation + 11-mode multi-mode fetcher + complete inline
fetch migration). All 15 acceptance criteria pass plus the end-to-end
resonance test against issue 3583760.

### What shipped across 8 phases

**Phase A — audit + shared lib foundation.** Grepped the workbench for all
inline fetch sites (10 found). Located `drupalorg.phar` at
`scripts/drupalorg.phar` (my earlier "missing phar" claim was a cwd error
during testing — the phar was never broken). Created `scripts/lib/data/`,
copied the 4 data modules there, staged temporary `importlib` re-export
shims at the old location for transition.

**Phase B1 — multi-mode `fetch_issue.py` CLI.** Refactored the existing
690-line one-shot fetcher into a 1130-line multi-mode dispatcher with
11 modes: `full`, `refresh`, `delta`, `comments`, `related`, `search`,
`issue-lookup`, `mr-diff`, `mr-status`, `mr-logs`, `raw-file`. Each mode
returns structured output; status lines go to stderr so stdout stays clean
for piping. `full` remains the default for backward compatibility. Phar
backs only `mr-status` and `mr-logs` (gaps in `gitlab_api.py`). All other
modes stay Python — the user was emphatic that Python is primary because
the phar lacks `field_changes`, `is_system_message`, `mr_references`,
`images`, and MR inline discussions with file/line positions.

**Phase B2 — `drupal-issue-fetcher` agent rewrite.** Grew from 142 to 490
lines. Documents all 11 modes with per-mode dispatch examples, enriched
summary shapes, and the mid-work re-fetch use cases. The stale `freelygive`
path reference was fixed (it now uses `./scripts/fetch-issue`). Default is
still `full` for legacy callers.

**Phase C — migrate imports + delete old locations.** Updated
`contribute_fix.py` to add `scripts/lib/data/` to its `sys.path`. Deleted
the 4 shims at `.claude/skills/drupal-contribute-fix/lib/`. Deleted the
old `.claude/skills/drupal-contribute-fix/scripts/fetch_issue.py`
(no non-doc caller referenced it by name — clean deletion, no stub
needed). Verified `contribute_fix.py`, `fetch_issue.py`, `issue_matcher.py`
all still import cleanly. Grep-clean verified.

**Phase D — migrate ALL inline fetch sites.** Every inline `curl`,
`WebFetch`, and `urllib.request` call in skill scripts and agent prose
that touched drupal.org or git.drupalcode.org was migrated:

- `drupal-issue-review/SKILL.md:195` — curl MR diff → `--mode mr-diff`
- `drupal-issue/SKILL.md:252` — same curl → `--mode mr-diff`
- `drupal-issue/SKILL.md:395` — `curl | git apply` → `--mode mr-diff --out - | git apply`
- `drupal-ddev-setup.md:65` — raw composer.json → `--mode raw-file` (new mode)
- `drupal-issue-review/SKILL.md:90` — WebFetch prose → fetch-issue modes reference
- `drupal-issue/SKILL.md:188` — WebFetch fallback → `--mode refresh`
- `contribute_fix.py:1092` — inline `urllib.request.Request` → `from raw_fetch import download_raw_file`

Added a new `scripts/lib/data/raw_fetch.py` (90 lines) with
`download_raw_file()` + `download_raw_file_bytes()` — single helper used
by both `fetch_issue.py` (via `raw-file` mode) and `contribute_fix.py`
(direct import). This made the 11th mode possible and consolidated the
one remaining code path.

Documented exceptions NOT migrated (per scope):
- `.claude/projects/.../memory/reference_gitlab_auth.md` — auto-memory file, out of scope
- `drupal-verifier.md` description — "curl smoke tests" are local DDEV tests
- `drupal-contributor.md` — deprecated agent, scheduled for deletion in ticket 037

**Phase E — resonance scorer.** New file
`.claude/skills/drupal-issue/scripts/resonance_search.py` (~620 lines).
Extracts signals from artifacts (keywords, file paths, class/function
symbols, error messages, referenced NIDs). Layer A queries bd via
`bd list` subprocess. Layer B queries d.o via
`./scripts/fetch-issue --mode search` subprocess (with **keyword-count
fallback: 3 → 2 → 1 keywords** until a non-zero result set is found, plus
explicit `--mode issue-lookup` for every referenced NID). Deterministic
scorer with 5 signals (direct cross-reference, module match, keyword
overlap, time proximity, bd desc/notes hit). 4 buckets: NONE (<40),
RELATED_TO (40-59), SCOPE_EXPANSION_CANDIDATE (60-79), DUPLICATE_OF (≥80).
Silent degrade: if Layer B fails, Layer A results still ship with a
`layer_b.status: "degraded"` marker.

**Phase F — resonance agent + SKILL.md + mid-work docs.** Created
`.claude/agents/drupal-resonance-checker.md` (197 lines, haiku model)
that dispatches the scorer, formats `RESONANCE_REPORT` text, writes
`workflow/00-resonance.md` + `00-resonance.json`. Integrated into
`/drupal-issue` SKILL.md:

- Step 0.5 "Resonance Check (MANDATORY)" inserted between Step 0 (fetch)
  and Step 1 (read)
- Category J added to the classification action table ("fold into
  existing issue")
- Rationalization Prevention row added to discourage skipping resonance

Added a new top-level "Mid-work Data Fetching" section to `CLAUDE.md`
with 7 concrete mid-work re-fetch examples (expected ≥3 per acceptance),
the 11-mode summary table, and the stdout/stderr discipline rule.

**Phase G — acceptance testing.** All A1–A15 pass live. End-to-end test:
resonance against issue 3583760 correctly surfaces drupal-3582345 as
`SCOPE_EXPANSION_CANDIDATE` with confidence 60, which matches the session
evidence where the user said *"MAYBE we can move all the stuff we are
doing here to that issue"*. Earlier test against 3581952 also surfaces
drupal-3581955 as SCOPE_EXPANSION_CANDIDATE — the cited companion issue
from a different session.

**Phase H — this note.** Ticket status + index flip.

### Side-finding fixed during acceptance: dolt.auto-push

During Phase G acceptance I discovered bd operations were hanging
indefinitely because Dolt's federation layer was running
`dolt push origin main` on every bd write, failing with
`non-fast-forward` against the workbench's github.com/AJV009 remote (a
refspec collision: Dolt's internal "main" branch getting pushed to the
git repo's "main" branch). The earlier `bd config set backup.git-push
false` I ran after ticket 028 only disabled bd's **backup**-layer git
push; Dolt's **federation** layer has a separate `dolt.auto-push`
knob that was still active.

Fix: `bd config set dolt.auto-push false` and
`bd config set dolt.auto-pull false`. Bd operations now run cleanly.
This is documented in `docs/bd-schema.md` under the "Tensions with
bd's opinions" section as a standing config requirement.

### Key architecture decisions locked in

1. **Python primary, phar filler.** 9 of 11 modes use the Python data
   layer (`drupalorg_api.py`, `drupalorg_page_parser.py`, `gitlab_api.py`
   — all at `scripts/lib/data/`). Only `mr-status` and `mr-logs` route
   to phar subprocess because `gitlab_api.py` doesn't expose pipeline
   state or job logs. This was the USER'S direction — the Python layer
   was built specifically to cover phar's gaps around `field_changes`,
   `is_system_message`, MR DiffNotes, and image extraction. Going
   phar-first would have regressed on those.

2. **Single entry point for all callers.** Every skill, every agent,
   every Python script touching d.o/gitlab data now goes through
   `./scripts/fetch-issue <mode>` (shell) or imports
   `scripts/lib/data/` modules directly (Python). Zero inline fetches
   remain in active code. The `raw-file` mode was added specifically
   to complete the migration — there are no "we'll do it later"
   deferrals.

3. **Resonance is additive and safe.** Classification still runs
   normally after Step 0.5. A DUPLICATE_OF (≥80%) verdict merely
   adds category J as a top-candidate classification option; it never
   auto-closes anything. The draft close-as-duplicate comment is a
   template that goes through `/drupal-issue-comment` like any other
   comment and lands at the push gate for user review.

4. **Empty bd degrades gracefully.** Since ticket 028 skipped backfill,
   bd starts empty. Layer A queries return zero for the first N issues
   worked after resonance ships. Layer B (d.o) carries the load until
   bd fills up organically. Both live acceptance tests (3581952,
   3583760) produced correct results purely from Layer B.

### Stats

- Files created: 5 (`scripts/lib/data/fetch_issue.py` migrated + expanded,
  `scripts/lib/data/raw_fetch.py`, `scripts/lib/data/drupalorg_api.py` +
  3 siblings moved here, `scripts/fetch-issue` wrapper,
  `.claude/skills/drupal-issue/scripts/resonance_search.py`,
  `.claude/agents/drupal-resonance-checker.md`)
- Files modified: 8 (`drupal-issue-fetcher.md`, `drupal-issue/SKILL.md`,
  `drupal-issue-review/SKILL.md`, `drupal-ddev-setup.md`,
  `contribute_fix.py`, `CLAUDE.md`, `docs/bd-schema.md`, ticket 029 itself)
- Files deleted: 5 (4 old lib shims + old fetch_issue.py)
- Lines added net: ~2,900 (most of it in `fetch_issue.py`'s mode
  implementations and the resonance scorer)

### Future work explicitly NOT in scope

- A `files.index` auto-writer mode — currently the fetcher agent writes
  it in prose instructions, not in `fetch_issue.py`. Could become a
  post-full-fetch step, but not today.
- A `related` mode that also scans referenced issues in the fetcher's
  `related-issues.json` (resonance does this work; fetcher's Step 4b
  could be consolidated further, but its current scope is correct).
- bd's `dolt.auto-push` / `auto-pull` disable should probably be in
  `.beads/config.yaml` as part of bd init, not after-the-fact. That's
  a bd upstream observation, not our ticket.

---

## Phase 2 Integrated Snapshot

See [phase-2-integrated-snapshot.md](phase-2-integrated-snapshot.md) for the
shared cross-ticket snapshot (maintained as a single file to avoid duplication).

