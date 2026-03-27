# Mode: Preflight (Search Only)

## When to Use

- First encounter with a contrib/core bug
- User asked to check if upstream fix exists
- Before writing ANY code changes to contrib/core
- When `/drupal-issue-review` transitions to fix mode

## Process

Search drupal.org for existing issues without generating local artifacts:

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" preflight \
  --project <module-name> \
  --keywords "<error message>" \
  --paths "src/AffectedFile.php" \
  --out .drupal-contribute-fix
```

## False-Positive Guard (Required)

`preflight` candidate matching is heuristic. Before stopping due to "already fixed":

1. Open the referenced issue/commit and confirm its title/component matches the bug class and code area.
2. Inspect the exact affected file/function in the target branch and confirm the bug condition is actually gone.
3. Record file path + commit/issue evidence in your notes/report before closing/switching local tracking.

If any verification step fails, treat it as a false positive and continue.

## Manual Keyword Search

Drupal.org's `api-d7` endpoint does **not** support full-text `text=` filter (HTTP 412). Use the UI:

```text
https://www.drupal.org/project/issues/search/<project>?text=<keywords>
```

## Output

- `UPSTREAM_CANDIDATES.json` in `.drupal-contribute-fix/`
- No local diff or issue directory created (that's `package` mode)

## Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | No existing fix found | Proceed to fix |
| 10 | Existing upstream fix found | STOP, report to user |
| 20 | Fixed in newer version | STOP, suggest upgrade |
| 40 | Error (network, can't determine project) | Report error |
| 50 | Security-related issue | STOP, follow security team process |

## Next Step

- If exit 0: proceed to writing the fix (invoke `/drupal-contribute-fix` package mode)
- If exit 10/20: report finding, no code changes needed
- If exit 50: do NOT post publicly, follow https://www.drupal.org/drupal-security-team/security-team-procedures
