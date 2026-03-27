# Drupal Issue Session Resume

**Date:** 2026-03-26
**Status:** Approved

## Problem

When working on a drupal.org issue across multiple sessions, each new `/drupal-issue` invocation starts a fresh Claude Code session with zero context. The artifacts (issue.json, comments.json, diffs) carry structured data forward, but the reasoning, decisions, failed attempts, and analysis from the previous session are lost. This is especially painful when reviews come in days later and you need to re-engage with full context.

## Solution

A wrapper shell script (`drupal-issue.sh`) that sits outside Claude Code and manages session continuity. It maintains a JSON mapping of issue IDs to Claude Code session UUIDs. On first use for an issue, it generates a UUID via `uuidgen`, records it, and launches Claude Code with `--session-id`. On subsequent use, it resumes the prior session with `--resume` and an automatic prompt to refresh the issue state.

## Verified Behavior

All flag combinations tested against Claude Code CLI (v2.1.83):

| Scenario | Command | Result |
|----------|---------|--------|
| New session with controlled UUID | `claude --session-id $UUID "prompt"` | Session created at known UUID |
| Resume with follow-up prompt | `claude --resume $ID "prompt"` | Resumes with full prior context |
| Non-existent session resume | `claude --resume $FAKE_UUID` | Clean error: "No conversation found with session ID: ..." |
| Named sessions | `claude --name "issue-NNNNNNN"` | Name shown in `/resume` picker and terminal title |
| Interactive mode with initial prompt | Both flags + positional prompt | Works, session is interactive |

## Architecture

```
drupal-issue.sh <issue_id_or_url> [objective]
       |
       v
  Parse issue ID (strip URL prefix if needed)
       |
       v
  Read DRUPAL_ISSUES/session-map.json
       |
       +-- Found session ID
       |       |
       |       v
       |   Validate session exists on disk
       |       |
       |       +-- Exists --> exec claude --resume $SESSION_ID
       |       |               --name "issue-$ISSUE_ID"
       |       |               "Refresh issue #$ID: fetch latest comments/MR status,
       |       |                summarize changes since last session. $OBJECTIVE"
       |       |
       |       +-- Missing --> Remove stale entry, fall through to new session
       |
       +-- No session found
               |
               v
           UUID=$(uuidgen)
           Write mapping to session-map.json
           exec claude --session-id $UUID
                --name "issue-$ISSUE_ID"
                "/drupal-issue https://www.drupal.org/i/$ISSUE_ID $OBJECTIVE"
```

## Components

### 1. `drupal-issue.sh` (wrapper script)

**Location:** `CONTRIB_WORKBENCH/drupal-issue.sh` (workspace root, executable)

**Usage:**
```bash
./drupal-issue.sh <issue_id_or_url> [objective]
```

**Examples:**
```bash
./drupal-issue.sh 3579079
./drupal-issue.sh 3579079 "address review comments on the MR"
./drupal-issue.sh https://www.drupal.org/project/ai/issues/3579079
./drupal-issue.sh https://www.drupal.org/i/3579079 "rebase and fix merge conflict"
```

**Issue ID extraction:** Regex handles these URL formats:
- Raw numeric ID: `3579079`
- Short URL: `https://www.drupal.org/i/3579079`
- Full URL: `https://www.drupal.org/project/ai/issues/3579079`
- With or without `www.`

**Dependencies:** `jq`, `uuidgen` (both confirmed available on this system).

**Process replacement:** Uses `exec claude ...` so the script's shell process is replaced by Claude Code. No orphaned processes, fully interactive, clean signal handling.

### 2. `DRUPAL_ISSUES/session-map.json` (mapping file)

**Format:**
```json
{
  "3579079": {
    "session_id": "67c4de85-3445-4de0-bdfd-bb59829298e7",
    "last_accessed": "2026-03-26T13:45:00+05:30",
    "url": "https://www.drupal.org/i/3579079"
  },
  "3561693": {
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "last_accessed": "2026-03-24T10:00:00+05:30",
    "url": "https://www.drupal.org/i/3561693"
  }
}
```

**Update strategy:** Always most-recent-wins. On new session, insert entry. On resume, update `last_accessed`. On stale session detected, delete entry and create new.

### 3. Session validation

Before resuming, check that the session JSONL file exists on disk:
```
~/.claude/projects/-home-alphons-project-freelygive-drupal-CONTRIB-WORKBENCH/$SESSION_ID.jsonl
```

If missing (e.g., user ran `claude sessions clear`, or data was pruned), remove the stale mapping entry and fall through to new-session flow.

## Resume Prompt

When resuming, the positional prompt sent to Claude Code:

**With objective:**
> Refresh issue #3579079: use the drupal-issue-fetcher agent to pull latest comments and MR status into DRUPAL_ISSUES/3579079/artifacts/, summarize what changed since our last session, then: address review comments on the MR

**Without objective:**
> Refresh issue #3579079: use the drupal-issue-fetcher agent to pull latest comments and MR status into DRUPAL_ISSUES/3579079/artifacts/, summarize what changed since our last session.

## Script Behavior Summary

1. Validate arguments (issue ID required, print usage if missing)
2. Extract numeric issue ID from argument (handle URL or raw number)
3. Ensure `DRUPAL_ISSUES/session-map.json` exists (create `{}` if not)
4. Look up issue ID in map
5. If found: validate session file on disk, resume or clean up stale entry
6. If not found: generate UUID, write mapping, launch new session
7. `exec` into Claude Code (script process replaced, fully interactive)

## What This Does NOT Do

- Does not modify any skills (drupal-issue, drupal-issue-fetcher, etc.)
- Does not run inside Claude Code (runs before it)
- Does not manage multiple sessions per issue (always most recent)
- Does not auto-push, auto-commit, or take any destructive action
