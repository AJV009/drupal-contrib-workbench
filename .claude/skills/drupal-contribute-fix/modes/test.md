# Mode: Test (Generate RTBC Comment)

## When to Use

- Testing someone else's MR for RTBC (Reviewed & Tested by the Community)
- Confirming a fix works in your environment
- Writing a tested-by comment for an existing issue

## Process

Generate a Tested-by/RTBC comment:

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" test \
  --issue 3345678 \
  --tested-on "Drupal 10.2, PHP 8.2" \
  --result pass \
  --out .drupal-contribute-fix
```

## Options

| Option | Values | Description |
|--------|--------|-------------|
| `--result` | `pass`, `fail`, `partial` | Test outcome |
| `--mr` | MR IID | Which MR was tested |
| `--patch` | URL | Which patch was tested |
| `--tested-on` | String | Environment description |

## Output

- `ISSUE_COMMENT.md` with paste-ready tested-by comment
- Formatted for drupal.org issue queue

## Next Step

- Post the comment on the drupal.org issue
- If result is `pass`: suggest setting status to RTBC
- If result is `fail`: describe what failed
