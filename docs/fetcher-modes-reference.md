# Mid-work Data Fetching Reference

> Extracted from CLAUDE.md for readability. This is the full mode
> table with dispatch examples for all 12 fetcher modes.

## Mid-work Data Fetching (drupal-issue-fetcher multi-mode)

The `drupal-issue-fetcher` agent is the single entry point for **all** data
acquisition from drupal.org and git.drupalcode.org. It supports 11 modes
under one dispatch contract (12 with the `post-note` write mode). Any skill at
any phase can dispatch it for fresh data — not just at the start of an issue.

Invoke from the workbench root:

```bash
./scripts/fetch-issue --mode <MODE> [mode-specific args]
```

Or directly via Python for programmatic consumption:

```bash
python3 scripts/lib/data/fetch_issue.py --mode <MODE> [args]
```

### The 12 modes at a glance

| Mode           | Purpose                                             |
|----------------|-----------------------------------------------------|
| `full`         | First-time bulk fetch (default if no mode given)    |
| `refresh`      | Re-fetch everything, bypass caches                  |
| `delta`        | Changes since a given timestamp                     |
| `comments`     | Issue metadata + comments only (lighter than full)  |
| `related`      | Project's recent issues into related-issues.json    |
| `search`       | Keyword search across project issue titles          |
| `issue-lookup` | Lightweight metadata only, JSON to stdout           |
| `mr-diff`      | Plain unified diff for one MR                       |
| `mr-status`    | Pipeline state + mergeability (phar-backed)         |
| `mr-logs`      | Failing job logs for an MR (phar-backed)            |
| `raw-file`     | Arbitrary raw URL (composer.json, patch files)      |
| `post-note`    | Post a GitLab issue Note (write mode)               |

### Source resolution (`--source`)

drupal.org is migrating issues from the legacy issue queue to GitLab
work-items. A global `--source auto|do|gitlab` flag (default `auto`) controls
how the fetcher resolves an issue:

- `auto` (default): probe the bare number; a redirect to GitLab work-items
  means the issue migrated (`source=gitlab`), otherwise it is legacy
  (`source=do`)
- `do`: force the legacy drupal.org issue queue
- `gitlab`: force GitLab work-items

`--source` is accepted by the data-layer modes: `full`, `refresh`, `delta`,
`comments`, `related`, `issue-lookup`. (Phar-backed `mr-status` / `mr-logs`,
`mr-diff`, and `raw-file` do not take it.)

Accepted identifier forms for `--issue`:

- bare number (legacy and migrated issues, resolved via redirect)
- full work_items URL: `https://git.drupalcode.org/project/<name>/-/work_items/<iid>`
- `project#iid` shorthand (required for NEW GitLab-native issues, whose small
  per-project IIDs are not globally unique)

### Mid-work re-fetch examples

Whenever a skill needs fresh data mid-workflow, dispatch the appropriate mode
instead of hitting drupal.org directly with curl or WebFetch.

**1. "Did the maintainer comment while I was running tests?"**
```bash
./scripts/fetch-issue --mode comments \
  --issue {issue_id} --project {project} \
  --out DRUPAL_ISSUES/{issue_id}/artifacts
```
Then diff the new `comments.json` against the previous state to see what is
new. Lighter than re-running `full`.

**2. "Did the pipeline pass after I pushed?"**
```bash
./scripts/fetch-issue --mode mr-status \
  --issue {issue_id} --mr-iid {mr_iid} \
  --out -
```
Returns JSON with `pipeline_id`, `status`, `pipeline_url`. Parse and decide.

**3. "Is there an existing d.o issue about 'entity access bypass'?"**
```bash
./scripts/fetch-issue --mode search \
  --project {project} --keywords "entity" "access" \
  --max-issues 200 --out -
```
`search` is **dual-source**: it queries both the legacy d.o issue queue and
GitLab issues (the named project plus a global search), and returns the merged
match list. Useful mid-fix to catch "oh wait this is a duplicate of #NNNN".

**4. "What does that referenced parent issue look like? I just need the title and status."**
```bash
./scripts/fetch-issue --mode issue-lookup \
  --issue {parent_id} --project {project} --out -
```
Lightweight — no comments, no MRs. Good for quick context checks.

**5. "Fetch the raw composer.json for this module branch so I can see its deps."**
```bash
./scripts/fetch-issue --mode raw-file \
  --url "https://git.drupalcode.org/project/{module}/-/raw/{branch}/composer.json" \
  --out -
```
Used by `drupal-ddev-setup` agent and other skills that need raw non-API
content.

**6. "I already fetched this issue an hour ago — just give me what is new."**
```bash
./scripts/fetch-issue --mode delta \
  --issue {issue_id} --project {project} \
  --since "2026-04-09T10:00:00Z" \
  --out DRUPAL_ISSUES/{issue_id}/artifacts \
  --gitlab-token-file git.drupalcode.org.key
```
Filters comments and discussions to items created/updated after `--since`.

**7. "The cache is stale, force a fresh pull of everything."**
```bash
./scripts/fetch-issue --mode refresh \
  --issue {issue_id} --project {project} \
  --out DRUPAL_ISSUES/{issue_id}/artifacts \
  --gitlab-token-file git.drupalcode.org.key
```
Equivalent to `full` with cache bypassed.

**8. "Post my drafted reply as a Note on this GitLab issue."**
```bash
./scripts/fetch-issue --mode post-note \
  --issue {iid} --project project/{name} \
  --body-file {path/to/note.md} \
  --gitlab-token-file git.drupalcode.org.key
```
Write mode (GitLab issues only). Required flags: `--issue <iid>`,
`--project project/<name>`, `--body-file <path>`, `--gitlab-token-file
git.drupalcode.org.key`. If the token is missing or read-only, it prints
`PARTIAL: ...; post the note manually at <url>` and exits 1, so the draft is
never lost.

### Stdout vs stderr discipline

All modes emit their structured output (JSON, diff text, comment data) to
**stdout**. Status lines (`COMPLETE: mode=X requests=N errors=M`) go to
**stderr**. This separation is load-bearing when piping through `jq`, `git
apply`, or similar — do NOT merge streams with `2>&1` unless you are
deliberately capturing both for debugging.

### The "no inline curl" rule

Do NOT use inline `curl` or `WebFetch` to hit drupal.org or
git.drupalcode.org from skills. Every capability in the old inline-fetch
world is now a fetcher mode. If you find yourself reaching for curl,
STOP — either an existing mode covers it or adding a new mode to
`scripts/lib/data/fetch_issue.py` is the right move. This consolidation is
the foundation that ticket 029 Phase D completed; keeping it clean matters.

### Architecture note

The fetcher routes internally:
- **Python data layer** (`scripts/lib/data/drupalorg_api.py`,
  `drupalorg_page_parser.py`, `gitlab_api.py`) handles 9 modes including
  all the ones that need `field_changes`, MR inline discussions, and image
  extraction from comment HTML — capabilities the phar does not provide.
- **Phar backend** (`scripts/drupalorg.phar` via the `scripts/drupalorg`
  wrapper) handles `mr-status` and `mr-logs` because Python's
  `gitlab_api.py` does not currently expose pipeline status / job log
  methods. Phar fills those two gaps cleanly.

You don't need to know which backend handles which mode — the fetcher
abstracts it. But if a mode behaves unexpectedly and you're debugging,
check `scripts/lib/data/fetch_issue.py` to see the dispatch.


