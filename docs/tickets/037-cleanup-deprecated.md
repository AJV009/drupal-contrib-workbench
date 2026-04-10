# TICKET-037: Cleanup Deprecated Agents, Tickets, Stale Paths

**Status:** NOT_STARTED
**Priority:** P3
**Affects:** Multiple files (see list below)
**Type:** Cleanup

## Problem

Phase 1 left noise in the repo: agent files marked deprecated but not removed, tickets that became obsolete, and stale paths that weren't audited. Per user direction:

> "Yes add clean up of deprecated stuff, we don't want noise obviously. Remove tickets that no longer matter."

## Concrete cleanup items

### 1. Delete `.claude/agents/drupal-contributor.md`

CLAUDE.md says:
> ### `drupal-contributor`
> DEPRECATED. Use the `/drupal-issue` skill chain instead.

But the file `.claude/agents/drupal-contributor.md` still exists. Ticket 014 ("contributor-agent-dedup") is marked COMPLETED but did not remove the file.

**Action**:
1. Delete the file
2. Remove the deprecated stub from the "Available Agents" section of CLAUDE.md (or update it to note the file was removed in ticket 037)

### 2. Delete obsolete ticket 012

`docs/tickets/012-chrome-mcp-for-screenshots.md` proposes "Use Chrome MCP instead of Playwright." That ticket is marked COMPLETED, but the actual implementation went a different route entirely: per git log commit `523924c add agent-browser skill, replace Chrome MCP and Playwright across workflows`, we now use the `agent-browser` Rust binary at `~/.cargo/bin/agent-browser`. Chrome MCP is no longer used at all.

The ticket title is actively misleading.

**Action**:
1. Delete `docs/tickets/012-chrome-mcp-for-screenshots.md`
2. The "Removed in phase 2 cleanup" section of `00-INDEX.md` already references this — verify the entry is accurate after deletion
3. README.md (phase 1 index) has 012 in its tables — leave those references alone or update them with a strikethrough; the README is historical archive

### 3. Audit for any other obsolete paths

Sweep the repo for stale references. Targets:
- Any path containing `freelygive` (the old workspace location)
- Any reference to "Chrome MCP" or "Playwright" (replaced by agent-browser)
- Any reference to "playwright" or `npx playwright`
- Any reference to `~/drupal/CONTRIB_WORKBENCH/` (the symlink path) where `/mnt/data/drupal/CONTRIB_WORKBENCH/` would be more canonical

Search command:
```bash
grep -rn "freelygive\|chrome.mcp\|chrome-mcp\|playwright" \
  --include='*.md' --include='*.sh' --include='*.json' \
  .claude/ scripts/ docs/ drupal-issue.sh CLAUDE.md 2>/dev/null
```

For each match, decide: update the path, remove the reference, or leave (with justification).

### 4. Remove dead code in drupal-issue.sh

After ticket 027 lands, review `drupal-issue.sh` for any other dead branches or stale comments referencing the old workspace location.

### 5. Sweep `.claude/skills/` for references to deprecated patterns

Specifically:
- References to "chrome MCP" or "playwright" in any SKILL.md (should be "agent-browser")
- References to drupal-contributor agent in any SKILL.md
- References to the freelygive path

### 6. Audit `tui.json` for stale entries

`tui.json` has `sessions[]` arrays per issue that grow over time. Many entries (e.g., issue 3508503's `drupal-issue-2zis`, `drupal-issue-e15u`, `drupal-issue-jof3`) reference tmux sessions that no longer exist. This is mostly cosmetic but creates noise for `pause-orphaned-ddev.sh` from ticket 032.

**Action**: optional. Either leave as-is (the script handles it correctly), or write a small `prune-tui-sessions.sh` that filters out dead session names from each `sessions[]` array. This is optional polish — only do if it's <30 minutes.

## Acceptance

1. `.claude/agents/drupal-contributor.md` does not exist
2. `docs/tickets/012-chrome-mcp-for-screenshots.md` does not exist
3. `00-INDEX.md` has accurate "Removed in phase 2 cleanup" entries
4. `grep -rn "freelygive\|chrome.mcp\|chrome-mcp\|playwright" .claude/ scripts/ docs/ drupal-issue.sh CLAUDE.md` returns no unjustified matches
5. CLAUDE.md no longer mentions drupal-contributor as a current agent

## Dependencies

None. Trivial mechanical work, but should be done after 027 lands so any dead launcher code is also covered in the same sweep.

## Notes

Keep the historical record of removals in `00-INDEX.md` rather than deleting it without trace. Future readers should be able to ask "what happened to ticket 012?" and find the answer in the index.

## Resolution (2026-04-10)

Cleanup complete. All acceptance criteria pass.

### What was cleaned

1. **Deleted** `.claude/agents/drupal-contributor.md` (deprecated agent from ticket 014)
2. **Deleted** `docs/tickets/012-chrome-mcp-for-screenshots.md` (obsolete — agent-browser replaced both Chrome MCP and Playwright)
3. **Fixed 3 stale `freelygive` paths** in active code:
   - `.claude/skills/drupal-issue-review/SKILL.md:205` → updated to `/home/alphons/drupal/CONTRIB_WORKBENCH`
   - `.claude/agents/drupal-pipeline-watch.md:24` → same
   - `.claude/agents/drupal-ddev-setup.md:48` → same
4. **Removed** deprecated `drupal-contributor` stub from CLAUDE.md "Available Agents" section
5. **Verified** `00-INDEX.md` removal notes for both deleted files are accurate

### Also fixed (discovered during session)

- **Hook paths in `.claude/settings.json`** — changed from relative (`bash .claude/hooks/...`) to `$CLAUDE_PROJECT_DIR`-based paths. The relative paths failed when CWD was a subdirectory (e.g., inside a module tree). This was causing `No such file or directory` errors on every tool call in real sessions.

### Verification

`grep -rn "freelygive|playwright|chrome-mcp|drupal-contributor"` across `.claude/`, `scripts/`, `CLAUDE.md`, `drupal-issue.sh` returns zero matches in active code. Historical references in ticket docs (027, 029, 037) are left intact as documentation.
