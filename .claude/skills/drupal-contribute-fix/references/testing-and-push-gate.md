# Testing, Pre-Push Quality Gate, and Post-Fix Depth Gate

> This file is extracted from SKILL.md for readability.
> It covers Testing Steps 1-3, the Pre-Push Quality Gate (Step 0 CI parity,
> Step 2.5 post-fix depth gate), and the conditional failure/circuit-breaker paths.

## Testing

Every fix MUST include kernel tests that fail against pre-fix code and pass
against fixed code. Non-negotiable. See IRON LAWs above. Gate exists because
of #3542457 (code-only push bounced as Needs Work).

Reference docs (open when needed, not by default):
- `references/testing-patterns.md` - PHPUnit patterns for Drupal
- `references/smoke-testing.md` - Curl tests, drush eval, DDEV gotchas
- `references/common-checks.md` - Common verification scenarios
- `references/core-testing.md` - Core-specific patterns

### Step 1: Plan from the diff (before writing test code)

First, discover project test infrastructure:
```bash
find web/modules/contrib/{module} -name "*TestBase*" -o -name "*Base*Test*" | head -10
find web/modules/contrib/{module} -path "*/tests/*" -name "*.php" | head -20
```
Look for base classes that provide screenshot/video capture, pre-configured
modules, helper traits, or mock providers. Use project base classes when
they exist rather than building from `KernelTestBase`/`WebDriverTestBase`
directly. (E.g. the AI module provides `BaseClassFunctionalJavascriptTests`.)

For each file in the diff: NEW file tests all public methods; MODIFIED file
tests only changed/added methods; config file verifies schema/values; test
file itself is skipped.

For each changed/new method, identify: input types and edge cases,
error/exception paths, dependencies needing mocks. Write the plan as a
checklist first with specific assertions ("handles empty input", "propagates
ConnectionException"), never vague placeholders ("test error handling").

### Step 2: Write the tests, then the fix (TDD)

Write the test, watch it fail, write the minimal fix, watch it pass. Then
run the full module test suite to confirm no regressions, and PHPCS on all
new/modified files.

### Step 3: Validate tests are not trivially true

After tests pass against fixed code, prove they actually test the behavioral
change:

```bash
# 1. Stash source changes, keep tests in place
git stash push -- src/ config/ *.module *.install

# 2. Run new/modified tests against unfixed code
ddev exec ../vendor/bin/phpunit [new_test_files]

# 3. Verify FAILURE (expected). Then restore.
git stash pop
```

Results interpretation: all new tests fail = validated, tests are legitimate.
Some pass without fix = those are trivially true (test setup, not behavioral
change), rewrite them. All pass without fix = rewrite all. Max 2 rewrite
cycles. Report in push gate summary: `Test Validation: N/M correctly fail
without fix, K trivially passing`.

Edge cases: test-only changes skip validation; config-only changes stash
config files specifically; if `git stash pop` fails, `git checkout -- src/ config/`
to restore from last commit.

### Pre-Push Quality Gate

Before pushing to the issue fork, ALL of these must pass:

**Step 0: CI parity discovery (run first)**

Mirror every CI job that will run on the module's pipeline. PHPCS + PHPUnit
alone is not enough; modern Drupal modules enforce PHPStan, cspell,
stylelint, and eslint too, and each skipped job is a potential CI
round-trip.

```bash
/mnt/data/drupal/CONTRIB_WORKBENCH/scripts/local_ci_mirror.sh \
  web/modules/contrib/<module_name>
```

Required: exit code 0 (zero failed jobs). Do NOT proceed to Steps 1-2
below until Step 0 passes. See `references/ci-parity.md` for the full
flag list (`--fast`, `--tests-only`, `--only`, `--skip`, `--json`),
gotcha handling (PHPCS warnings, cspell dictionaries, eslint configs,
`allow_failure` jobs), and failure triage (pre-existing vs caused by
your changes).

Steps 1-2 below are per-tool fallbacks for debugging a single job in
isolation when the helper is unavailable.

**Step 1: PHPCS (automatic, fallback)**
```bash
ddev exec phpcs --standard=Drupal,DrupalPractice --runtime-set ignore_warnings_on_exit 1 [changed_files]
```
Required: 0 errors. Warnings are reported but do not block.

**Step 2: Tests (automatic, fallback)**
```bash
ddev exec phpunit [module_test_path]
```
Required: 0 failures, 0 errors. If tests fail, fix and re-run.

**Step 2.5: Post-fix solution-depth gate (conditional)**

After phpunit passes and BEFORE the spec/code/verifier agents run, decide
whether the post-fix solution-depth gate should run.

### Compute patch stats

```bash
ISSUE_ID={issue_id}
MODULE_PATH=web/modules/contrib/{module}
WORKFLOW_DIR="$CLAUDE_PROJECT_DIR/DRUPAL_ISSUES/$ISSUE_ID/workflow"
mkdir -p "$WORKFLOW_DIR"
python3 .claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py \
  compute-stats \
  --module-path "$MODULE_PATH" \
  --out "$WORKFLOW_DIR/02a-patch-stats.json"
```

### Decide whether to run

```bash
RUN_DECISION=$(python3 .claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py \
  should-run \
  --pre-fix-json "$WORKFLOW_DIR/01b-solution-depth-pre.json" \
  --patch-stats "$WORKFLOW_DIR/02a-patch-stats.json" \
  --issue-id "$ISSUE_ID" \
  --workflow-dir "$WORKFLOW_DIR")
echo "Post-fix gate decision: $RUN_DECISION"
```

`RUN_DECISION` will be `RUN` or `SKIP`. The full reasoning is logged in
`$WORKFLOW_DIR/02a-trigger-decision.json` for auditability.

### If RUN: dispatch the post-fix gate agent

```
Dispatch: drupal-solution-depth-gate-post
Inputs:
  issue_id = {issue_id}
  module_path = web/modules/contrib/{module}
  pre_analysis_path = $CLAUDE_PROJECT_DIR/DRUPAL_ISSUES/{issue_id}/workflow/01b-solution-depth-pre.json
  patch_stats_path = $CLAUDE_PROJECT_DIR/DRUPAL_ISSUES/{issue_id}/workflow/02a-patch-stats.json
```

Wait for `SOLUTION_DEPTH_POST: decision={approved-as-is|approved-with-recommendation|failed-revert} score={N}`.

Branching:
- **approved-as-is** (score 1): Continue to Step 3 (spec reviewer). No action.
- **approved-with-recommendation** (score 2-3): Continue to Step 3, BUT stash
  the `recommendation_for_comment` from `02b-solution-depth-post.json` for
  inclusion in the draft comment at Step 6.
- **failed-revert** (score ≥4): RUN THE FAILURE PATH BELOW. Do NOT continue
  to Step 3.

### If SKIP: continue directly to Step 3 (spec reviewer)

No dispatch, no action beyond the trigger-decision log.

### Failure path (when post-fix gate returns failed-revert)

The post-fix gate has returned `decision: failed-revert`. You now:

**A. Write the recovery brief.** Read `workflow/01b-solution-depth-pre.md`
and `workflow/02b-solution-depth-post.md`, then synthesize into
`workflow/02c-recovery-brief.md`:

```bash
cat > "$WORKFLOW_DIR/02c-recovery-brief.md" <<'BRIEF'
# Recovery Brief — Issue #{issue_id}
