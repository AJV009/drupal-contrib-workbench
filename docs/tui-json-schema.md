# tui.json schema

`tui.json` lives at the workbench root and is a JSON object keyed by
Drupal issue nid (string). Each entry holds metadata about one issue
that has been worked on at least once.

## Writers

| Writer | Fields touched | Trigger |
|---|---|---|
| `drupal-issue.sh` → `write_tui_json()` | `title`, `fileCwd`, `actions` (default seed), `sessions` (unique append) | Every launcher invocation (new session or resume) |
| `drupal-ddev-setup` agent (ticket 032) | `ddev_name` | After `ddev start` succeeds on first stack creation |
| `pause-orphaned-ddev.sh register` (ticket 032) | `ddev_name` (backfill only when unset) | Manual one-shot migration |

## Readers

| Reader | Fields read | Contract |
|---|---|---|
| `tui-browser` (external project) | `title`, `fileCwd`, `actions` | Public contract; never break these. |
| `pause-orphaned-ddev.sh` (default mode) | `sessions`, `ddev_name` | Added in ticket 032. |

## Field reference

| Field | Type | Set by | Purpose |
|---|---|---|---|
| `title` | string | launcher | Shown in tui-browser |
| `fileCwd` | string (path) | launcher | Working directory root for this issue |
| `actions` | array of objects | launcher | Clickable shortcuts shown in tui-browser |
| `sessions` | array of strings | launcher | tmux session names ever used for this issue (unique-append, never shrunk) |
| `ddev_name` | string (optional) | ddev-setup agent | DDEV project name for this issue's stack, used by `pause-orphaned-ddev.sh` |

## Invariants

1. Keys are bare numeric Drupal nids as strings.
2. `sessions` is append-only; the launcher never removes entries. A stale
   session name staying in `sessions` is safe because `pause-orphaned-ddev.sh`
   joins against live `tmux ls` output, not historical state.
3. The file is always valid JSON. Writers use `jq` with temp-file + `mv`
   to avoid partial writes.
4. No field except `title`/`fileCwd`/`actions` is part of the tui-browser
   public contract. Other fields are free for internal workbench use.
