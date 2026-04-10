# Fetcher Modes Reference (modes 2-11)

> Extracted from `drupal-issue-fetcher.md` for readability.
> The `full` mode (primary, always-read) stays in the main agent file.

## Mode: `refresh`

Same as `full` but with `--no-cache` implied. Use when the caller explicitly
says "re-fetch, don't trust cache".

```bash
./scripts/fetch-issue --mode refresh \
  --issue {ISSUE_URL_OR_ID} \
  --out {OUTPUT_DIR} \
  --gitlab-token-file git.drupalcode.org.key
```

Return the same enriched summary as `full`. Mention in the summary that caches
were bypassed.

---

## Mode: `delta`

"What changed since timestamp X?" Runs a full fetch internally, then filters
`comments.json` and MR discussions to only items created/updated after `--since`.

```bash
./scripts/fetch-issue --mode delta \
  --issue {ISSUE_URL_OR_ID} \
  --since {ISO8601_TIMESTAMP} \
  --out {OUTPUT_DIR} \
  --gitlab-token-file git.drupalcode.org.key
```

Example `--since` values:
- `2026-04-09T12:00:00Z` (specific UTC time)
- `2026-04-09T00:00:00+05:30` (specific time in IST)

Return a compact delta summary:

```
COMPLETE (delta since {timestamp}):
- New comments: {n} (cite numbers + authors)
- New discussion notes: {n} (cite which MR + file:line if DiffNote)
- MR state change: yes/no (old → new)
- Pipeline state change: yes/no

If 0 changes: "No changes since {timestamp}."

**Also run Step 4c** (query bd for prior knowledge) in delta mode. bd
data may have been written since the last fetch, so always refresh.
```

---

## Mode: `comments`

Lighter than `full`. Only fetches `issue.json` + `comments.json` + `fetch-log.json`.
Use for mid-work polls where MR state hasn't changed but comments might have.

```bash
./scripts/fetch-issue --mode comments \
  --issue {ISSUE_URL_OR_ID} \
  --out {OUTPUT_DIR}
```

Return a compact comment-diff summary comparing to any existing `comments.json`
in `{OUTPUT_DIR}`:

```
COMPLETE: {total_count} comments.
- New since last fetch: {n} (list authors + comment numbers)
- Most recent: comment #{N} by {author} on {date}
- Status changes recorded: {list from field_changes}
```

---

## Mode: `related`

Fetches recent issues in the same project. Writes `related-issues.json` to
`--out` directory.

```bash
./scripts/fetch-issue --mode related \
  --issue {ISSUE_ID} --project {PROJECT} \
  --max-issues 30 \
  --out {OUTPUT_DIR}
```

Return summary:

```
COMPLETE: {total} recent issues in {project}.
- {first 5-10 with nid + short title + status}
- Full list in related-issues.json
```

---

## Mode: `search`

Keyword search against a project's recent issues. Results match issue titles
(AND across all keywords, case-insensitive).

```bash
./scripts/fetch-issue --mode search \
  --project {PROJECT} \
  --keywords "entity" "access" "bypass" \
  --max-issues 200 \
  --out -
```

`--out -` emits JSON to stdout. `--out <file>` writes to a file.

Return summary (if emitting to the controller):

```
COMPLETE: Searched {total_scanned} issues in {project}, {match_count} matches.
- Top matches: {nid + title + status for each, up to 10}
- Full JSON: [paste the stdout JSON]
```

---

## Mode: `issue-lookup`

Lightest mode: just issue metadata (title, status, version, component, author,
author UID, body). NO comments, NO MRs. Use when you need to know "what's this
referenced issue about?" without a full fetch.

```bash
./scripts/fetch-issue --mode issue-lookup \
  --issue {ISSUE_URL_OR_ID} \
  --out -
```

Returns the JSON directly to stdout. For the controller's summary, extract the
key fields:

```
COMPLETE: drupal-{nid} "{title}"
- Status: {status}
- Version: {version}
- Component: {component}
- Author: {author}
- Created: {date}
```

---

## Mode: `mr-diff`

Fetches a single MR's plain unified diff. Outputs to stdout or a file.

```bash
./scripts/fetch-issue --mode mr-diff \
  --issue {ISSUE_URL_OR_ID} \
  --mr-iid {MR_IID} \
  --out - \
  --gitlab-token-file git.drupalcode.org.key
```

`--issue` is still required (to derive the project). Return a compact summary:

```
COMPLETE: MR !{iid} diff: {N} files changed, {+added}/{-removed} lines.
- {list of top 5 files with change counts}
[Diff content follows via stdout OR saved to {out_path}]
```

---

## Mode: `mr-status` (phar-backed)

Pipeline state + mergeability for a single MR. Backed by phar because
`gitlab_api.py` doesn't currently expose a `get_pipeline_status` method.

```bash
./scripts/fetch-issue --mode mr-status \
  --issue {ISSUE_URL_OR_ID} \
  --mr-iid {MR_IID} \
  --out -
```

Returns phar's JSON output directly. Extract for the summary:

```
COMPLETE: MR !{iid} pipeline
- Pipeline: {id}, status: {passed/failed/running}
- URL: {pipeline_url}
```

---

## Mode: `mr-logs` (phar-backed)

Failing job logs for an MR's latest pipeline. Returns 404 on PASSING pipelines
(phar's behavior — there are no failing jobs to list). That's **expected**
and NOT an error on your side.

```bash
./scripts/fetch-issue --mode mr-logs \
  --issue {ISSUE_URL_OR_ID} \
  --mr-iid {MR_IID} \
  --out -
```

If phar returns 404:
```
INFO: MR !{iid} pipeline has no failing jobs to show (pipeline likely passed
or is still running). Use mr-status to confirm current pipeline state.
```

If phar returns logs, include the key stack trace or error line in the summary,
and save the full logs to `{OUTPUT_DIR}/mr-{iid}-logs.txt` if the caller
provided a directory.

---

## Mode: `raw-file`

Download an arbitrary URL — for content the API clients don't cover. The
two real use cases right now:

1. **`composer.json` from a project branch** (ddev-setup agent uses this to
   discover external PHP dependencies):
   ```bash
   ./scripts/fetch-issue --mode raw-file \
     --url "https://git.drupalcode.org/project/{module}/-/raw/{branch}/composer.json" \
     --out -
   ```

2. **`.patch` file download for reroll** (contribute_fix.py uses this
   internally via `from raw_fetch import download_raw_file`):
   ```bash
   ./scripts/fetch-issue --mode raw-file \
     --url "https://www.drupal.org/files/issues/YYYY-MM-DD/some-patch.patch" \
     --out /tmp/original.patch
   ```

No caching, no rate limiting, no retry — these are one-off downloads of
specific files where the caller wants the latest content.

Return a compact summary:

```
COMPLETE: raw-file {url} ({N} bytes)
[Content follows via stdout OR saved to {out_path}]
```

---

## Mid-work re-fetch quick reference

When a controller mid-workflow asks "can you go check X?", here are the modes
to use:

| "Can you ..." | Mode dispatch |
|---|---|
| "... see if the maintainer commented since I started DDEV?" | `--mode comments --issue X --project Y --out {OUTPUT_DIR}` then diff against previous |
| "... see if there's an existing issue about 'entity access bypass'?" | `--mode search --project Y --keywords "entity" "access" "bypass" --out -` |
| "... quickly check what issue #3582345 is about?" | `--mode issue-lookup --issue 3582345 --project Y --out -` |
| "... check if the pipeline passed after we pushed?" | `--mode mr-status --issue X --mr-iid Z --out -` |
| "... show me why the pipeline failed?" | `--mode mr-logs --issue X --mr-iid Z --out -` (then read the logs for error lines) |
| "... fetch that parent issue's full context?" | `--mode full --issue {parent_id} --out DRUPAL_ISSUES/{parent_id}/artifacts` |
| "... compare the stale MR diff against the current target branch diff?" | `--mode mr-diff --issue X --mr-iid Z --out /tmp/stale.diff ...` |
| "... refresh everything, caches are stale?" | `--mode refresh --issue X --out {OUTPUT_DIR}` |
| "... see only what changed in the last hour?" | `--mode delta --issue X --since {now-1h-iso} --out {OUTPUT_DIR}` |
| "... fetch a composer.json / raw file from git.drupalcode.org?" | `--mode raw-file --url <raw-url> --out -` |

For each, return a compact summary scoped to the question asked. Do NOT dump
the full enriched `full`-mode summary — the controller asked a specific question.

