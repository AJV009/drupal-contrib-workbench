# CI Parity (Pre-Push Gate Step 0)

Mirror every CI job that will run on the module's pipeline BEFORE pushing.
Running just PHPCS and PHPUnit is not enough: modern Drupal modules enforce
PHPStan, cspell, stylelint, and eslint, and each skipped job is a potential
CI round-trip.

## Invocation

```bash
# From anywhere inside the DDEV project:
/mnt/data/drupal/CONTRIB_WORKBENCH/scripts/local_ci_mirror.sh \
  web/modules/contrib/<module_name>
```

The helper walks up from the current directory to find the DDEV project,
detects which jobs are applicable (phpstan.neon present? composer.json
present? modern eslint.config.js present?), and runs them in order.

Exit code is the number of failed jobs. Required: **0 failures across all
scoped jobs.**

## Options

| Flag | Purpose |
|------|---------|
| `--fast` | Skip the phpunit job (only static analysis, fast feedback) |
| `--tests-only` | Run only phpunit (use when iterating on tests) |
| `--only phpcs,phpstan` | Run only the named jobs |
| `--skip eslint,stylelint` | Skip the named jobs (e.g. pre-existing failures) |
| `--json` | Emit a JSON summary line after the normal output |

## Gotchas the helper handles

- **PHPCS warnings vs errors.** Drupal CI runs phpcs with
  `ignore_warnings_on_exit=1`, so warnings are reported but do not fail the
  job. The helper matches this. It also constrains `--extensions` to
  PHP-style files (`.php`, `.module`, `.install`, `.inc`, etc.) so JS and
  CSS are handled by eslint/stylelint, not phpcs.
- **cspell dictionary loading.** The Drupal CI template ships a base
  dictionary (`langcode`, `vid`, etc.) that local `npx cspell` cannot
  replicate. To avoid false positives on pre-existing terminology, the
  helper runs cspell only against files with uncommitted changes plus
  commits ahead of upstream. New unknown words from current work are
  caught; unchanged files are left to CI. The project's
  `.cspell-project-words.txt` is loaded as a dictionary with an absolute
  path (cspell resolves dictionary paths relative to the config file, not
  the CWD).
- **stylelint and eslint configs.** Both tools inherit config from the CI
  template on d.o. Locally, the helper only runs them if the module ships
  its own modern config (`stylelint.config.js`, `eslint.config.js`, etc.).
  Legacy `.eslintrc.*` files are NOT considered runnable because
  `npx eslint` defaults to v9+ which requires the flat-config format.
  Skipping is preferred over false-positive failures.
- **`allow_failure: true` and `SKIP_<TOOL>` variables.** Parsed from the
  module's `.gitlab-ci.yml`. Any job with `allow_failure: true` or a
  `SKIP_<TOOL>: 1` variable is treated as informational and skipped.

## Failure handling

1. **Pre-existing failure** (file in failing job NOT in your diff): note
   it in the push gate summary but do not block the push. Verify
   pre-existing by running
   `git diff --name-only upstream/<branch>..HEAD` and cross-checking the
   failing files. Re-run with `--skip <job>` to get a clean summary.
2. **Failure caused by your changes:** fix and re-run the helper. Repeat
   until every scoped job passes.

## Fallback

If the helper is unavailable or you need to debug a single job in
isolation, the individual per-tool commands are in the main SKILL.md
(Pre-Push Quality Gate Steps 1 and 2). The helper is preferred because it
mirrors the full CI job list, not just the two most common tools.
