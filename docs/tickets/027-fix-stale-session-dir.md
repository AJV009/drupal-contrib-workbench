# TICKET-027: Fix Stale SESSION_DIR Path in drupal-issue.sh

**Status:** COMPLETED
**Priority:** P0 (Critical, trivial)
**Affects:** `drupal-issue.sh` line 6
**Type:** Bug Fix

## Problem

Line 6 of `drupal-issue.sh` hardcodes a stale workspace path:

```bash
SESSION_DIR="$HOME/.claude/projects/-home-alphons-project-freelygive-drupal-CONTRIB-WORKBENCH"
```

The real workbench location is `/mnt/data/drupal/CONTRIB_WORKBENCH` (with `~/drupal/CONTRIB_WORKBENCH` as a symlink). Claude Code stores session JSONLs at `~/.claude/projects/-mnt-data-drupal-CONTRIB-WORKBENCH/`. The `freelygive` slug references an older workspace location and was never updated when the workbench moved.

## Effect today

The "resume existing session" branch at the bottom of the script (`if [[ -f "$SESSION_DIR/$SESSION_ID.jsonl" ]]; then resume_session; fi`) **never fires**. Every invocation where `session-map.json` already has an entry hits `remove_stale_session` → starts a brand new claude session with a brand new UUID, throwing away the prior session-id.

This means:
- Resume of a long-running issue does not actually resume — it starts fresh with no prior context
- The `session-map.json` updates are misleading (they record a session id but the on-disk session it points to never gets reused)
- The "Refresh issue #X" prompt in `resume_session()` is dead code

## Fix

Compute the session directory dynamically from `$SCRIPT_DIR`. Claude Code's projects-dir convention replaces `/` with `-` in the absolute path.

```bash
# Replace line 6 with:
SESSION_DIR="$HOME/.claude/projects/$(echo "$SCRIPT_DIR" | sed 's|/|-|g')"
```

This continues to work if the workbench is moved again, since `$SCRIPT_DIR` is computed from `BASH_SOURCE` at the top of the script.

**Note on symlinks**: `$SCRIPT_DIR` already uses `cd "$(dirname "${BASH_SOURCE[0]}")" && pwd` which resolves to the canonical path (`/mnt/data/...`), not the symlink (`/home/alphons/drupal/...`). This matches what Claude Code uses for the projects directory key, so the encoding will be correct.

## Acceptance

1. Run `./drupal-issue.sh 3577173` for an issue that already has a session-map.json entry pointing to a real on-disk JSONL.
2. Verify the script runs `claude --resume <existing-uuid>` (not `--session-id <new-uuid>`).
3. Verify the session JSONL file's mtime updates (proving claude opened the existing file).
4. Run a second time on the same issue — same UUID should still be used.
5. Verify `ps aux | grep claude` shows the resumed command line, not a fresh `--session-id`.

## Dependencies

None. Purely mechanical.

## Notes

After this fix, ticket 031 (sentinel + reinstate) becomes meaningful — it depends on the launcher being able to write files into the right place reliably. Ticket 028 (bd lifecycle) also adds code to this same script, so doing 027 first avoids merge conflicts.

## Resolution (2026-04-09)

Fix applied to `drupal-issue.sh` line 6.

**Correction to the proposed fix**: the ticket originally suggested `sed 's|/|-|g'`, but this workbench lives at `/mnt/data/drupal/CONTRIB_WORKBENCH` — the `_` in `CONTRIB_WORKBENCH` also gets rewritten to `-` by Claude Code's projects-dir encoding. The `/` only rule would have produced `-mnt-data-drupal-CONTRIB_WORKBENCH` (wrong) instead of `-mnt-data-drupal-CONTRIB-WORKBENCH` (correct).

Actual fix shipped:

```bash
SESSION_DIR="$HOME/.claude/projects/$(echo "$SCRIPT_DIR" | sed 's|[/_.]|-|g')"
```

The `[/_.]` character class covers `/`, `_`, and `.` — the three characters Claude Code rewrites to `-` when building the projects directory key. Verified against all 3 real entries under `~/.claude/projects/` on this host.

**Verification performed**:
1. `bash -n` syntax check on the edited script — PASS
2. Computed `SESSION_DIR` resolves to `/home/alphons/.claude/projects/-mnt-data-drupal-CONTRIB-WORKBENCH`, which exists
3. Routing condition evaluated against 5 live `session-map.json` entries (3574857, 3572774, 3508503, 3580677, 3582367) — all 5 now route to `resume_session`; before the fix, all 5 would have hit `remove_stale_session → launch_new_session`
4. Old stale path `-home-alphons-project-freelygive-drupal-CONTRIB-WORKBENCH` confirmed absent on disk

**Acceptance items 1-5 from the ticket** require an interactive tmux run (since the script `exec`s into `claude` as an interactive TUI) and should be confirmed by the user the next time they pick up an issue that already has a session-map entry.

## Second correction (2026-04-09, discovered during live testing)

The first fix (line 6 encoding) was correct but incomplete. When the user tested resume against issue 3580677, the script still hit `launch_new_session`. Root cause turned out to be line 4, not line 6:

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # BEFORE: logical path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)" # AFTER: physical path
```

`/home/alphons/drupal/CONTRIB_WORKBENCH` resolves (via a parent-chain indirection) to `/mnt/data/drupal/CONTRIB_WORKBENCH`. When the user runs `./drupal-issue.sh` from the `/home/alphons/...` path, plain `pwd` returns the logical path. Line 6's encoding then produced `-home-alphons-drupal-CONTRIB-WORKBENCH` — a directory that does NOT exist under `~/.claude/projects/`, because Claude Code itself resolves to the physical path when it creates its project-dir key. The `-f` check failed, resume was skipped, and a new UUID (`bee783cd-...`) overwrote the session-map entry for 3580677.

**Why my earlier verification missed this**: the verification was run with `cd /mnt/data/drupal/CONTRIB_WORKBENCH` manually — the physical path — so `pwd` and `pwd -P` returned the same thing. The bug only surfaces when the script is invoked from the logical path, which is how the user actually invokes it.

**Collateral damage and recovery**: session-map entry for 3580677 was overwritten with the failed `bee783cd-...` id; the original `e3150984-...` JSONL (1.4M of real Mar-30 context) was untouched on disk. Session-map was manually restored to point back to `e3150984-...` with a refreshed `last_accessed` timestamp. The stray `bee783cd-...` claude process had already exited; its 33K orphan JSONL was left in place (harmless).

**Lesson for future launcher edits**: any path math in `drupal-issue.sh` must use `pwd -P` (or equivalent) to stay consistent with Claude Code's physical-path convention. This is now a standing constraint on tickets 028, 031, and any future launcher work.

---

## Phase 2 Integrated Snapshot

See [phase-2-integrated-snapshot.md](phase-2-integrated-snapshot.md) for the
shared cross-ticket snapshot (maintained as a single file to avoid duplication).

