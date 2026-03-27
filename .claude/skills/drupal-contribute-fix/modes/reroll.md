# Mode: Reroll (Legacy Patch-Only Issues)

## When to Use

- Legacy fallback only
- Maintainers explicitly request patch workflow
- An existing patch no longer applies to the target branch
- Prefer MR workflow for all new contributions

## Process

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" reroll \
  --issue 3345678 \
  --patch-url "https://www.drupal.org/files/issues/metatag-fix-3345678-15.patch" \
  --target-ref 2.0.x \
  --out .drupal-contribute-fix
```

This:
1. Downloads the original patch
2. Attempts to apply it to the target branch
3. If it applies cleanly: reports success
4. If it fails: generates a rerolled patch with conflicts resolved

## Output

- Rerolled patch file in `diffs/`
- Report on what changed between versions
- `ISSUE_COMMENT.md` noting the reroll

## Next Step

- Upload the rerolled patch to the issue (if maintainer requested patch workflow)
- Better yet: convert to an MR (preferred workflow)
