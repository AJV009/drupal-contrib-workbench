# Mode: Package (Search + Generate Artifacts)

## When to Use

- Local code changes have been made to fix a contrib/core bug
- Ready to generate contribution artifacts (diff, report, comment)
- After preflight has been run and returned exit 0

## Process

Search upstream AND generate contribution artifacts:

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" package \
  --root /path/to/drupal/site \
  --changed-path web/modules/contrib/<module> \
  --keywords "<error message>" \
  --test-steps "<step 1>" "<step 2>" "<step 3>" \
  --out .drupal-contribute-fix
```

For `docroot/` layout (Acquia/BLT):
```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" package \
  --root /path/to/drupal/site \
  --changed-path docroot/modules/contrib/<module> \
  --keywords "<error message>" \
  --test-steps "<step 1>" "<step 2>" "<step 3>" \
  --out .drupal-contribute-fix
```

**Note:** `package` always runs `preflight` first and refuses to generate artifacts
if an existing fix is found (unless `--force` is provided).

## Test Steps (MANDATORY)

Agents MUST provide specific test steps via `--test-steps`. No placeholders.

Steps should describe:
1. How to set up the environment to reproduce the bug
2. The action that triggers the bug
3. Expected behavior BEFORE the fix (the bug)
4. Expected behavior AFTER the fix

## Output

```
.drupal-contribute-fix/
  UPSTREAM_CANDIDATES.json
  {nid}-{slug}/
    REPORT.md
    ISSUE_COMMENT.md
    WORKFLOW.md
    diffs/
      project-fix-{nid}.diff
```

## Next Step

- Present completion summary to user (Push Gate)
- Use `drupalorg-cli` commands for fork/MR/pipeline execution
