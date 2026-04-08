# Static Review Checklist (parallel to DDEV setup)

Use this while the `drupal-ddev-setup` agent runs in the background (~3-4
minutes). No running environment required — you're reading the diff from
`artifacts/mr-{iid}-diff.patch`.

## 1. Coding standards (per file in diff)

- `declare(strict_types=1)` present in new PHP files?
- No `\Drupal::` static calls in services/controllers (constructor injection instead)?
- PHPDoc on all public methods?
- `$this->t()` for user-facing strings?
- Proper exception handling (not swallowing errors)?
- Entity ID constraints respected (64 char max for config entities)?
- Input validation at system boundaries?

## 2. Test coverage gap analysis

- Identify new/changed methods that need tests.
- Does the MR include any test files? If a bug fix MR has zero tests,
  flag it. A missing test is a bigger gap than a missing PHPDoc.
- **Discover project test infrastructure.** Scan the module's `tests/`
  and the parent project's `tests/` for base classes: `*TestBase.php`,
  `*TestCase.php`, `Base*Test*.php`. Note what they provide (screenshot
  capture, video recording, pre-configured modules, trait helpers). For
  example, the AI module provides `BaseClassFunctionalJavascriptTests`
  with built-in `takeScreenshot()` and `videoRecording` support. Use
  project base classes when they exist rather than building from
  `KernelTestBase`/`WebDriverTestBase` directly.

## 3. Premise and architectural check (do this BEFORE deep code review)

- Does the issue claim something does NOT exist (no event, no hook, no
  extension point)? Grep the parent module to verify the absence.
- Does the MR add a new event, hook, or service? Check whether the parent
  framework already provides a generic one that covers the use case.
  (Example: a submodule-specific pre-request event is unnecessary if the
  parent module's `ProviderProxy` already dispatches one for all calls.)
- If the premise is false, flag it immediately. Do not invest further
  review effort on code built on a wrong foundation.

## 4. MR freshness check

Compare file paths and context lines in the diff against the current
target branch:

- File paths in the diff that don't exist on target (renamed upstream)
- Context lines in the diff that don't match current file content
- Upstream commits touching the same files after the MR's last update
  (`git log` on the target branch for the diff's files)

If freshness is suspect, flag it before investing further review effort.

## 5. Record findings

Save bullet-point findings to pass to the verifier/reviewer agents after
DDEV is ready.
