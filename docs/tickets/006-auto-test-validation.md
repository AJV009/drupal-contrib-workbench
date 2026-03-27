# TICKET-006: Automated Test Legitimacy Validation (Stash/Unstash)

**Status:** COMPLETED
**Priority:** P1 (High)
**Affects:** `.claude/skills/drupal-contribute-fix/SKILL.md`, `.claude/agents/drupal-verifier.md`
**Type:** Enhancement

## Problem

In the #3579478 session, the user's last question before push was:

> "just want to make sure the tests are right? right? I mean we are not cheating in the tests, right?"

This is a valid concern. Tests that always pass (regardless of whether the fix is applied) provide zero value. The TDD cycle requires:

1. Write test
2. Run test -> MUST FAIL (proves test detects the bug)
3. Write fix
4. Run test -> MUST PASS (proves fix resolves the bug)

The current workflow writes tests and runs them against the fixed code. It never verifies that the tests actually fail against the unfixed code. This means tests could be:
- Testing the wrong thing entirely
- Asserting trivially true conditions
- Not actually covering the behavioral change

## Current Behavior

```
1. Write test
2. Run test against fixed code -> PASS
3. Done (no validation that test fails without fix)
```

## Desired Behavior

```
1. Write test
2. Run test against fixed code -> PASS
3. Stash the fix (git stash)
4. Run test against UNFIXED code -> MUST FAIL
5. Pop the stash (git stash pop)
6. Report: "X tests correctly fail without fix, pass with fix"
```

If step 4 passes (test passes without the fix), the test is invalid and must be rewritten.

## Implementation Plan

### 1. Add "Test Validation" phase to `drupal-contribute-fix`

After all tests pass, add a mandatory validation step:

```markdown
## Test Validation (MANDATORY)

After all tests pass against the fixed code:

1. Record which test files were added/modified:
   - `ADDED_TESTS=$(git diff --name-only --diff-filter=A -- '*/tests/*')`
   - `MODIFIED_TESTS=$(git diff --name-only --diff-filter=M -- '*/tests/*')`

2. Stash only the source code changes (not test files):
   - `git stash push -- src/ config/ *.module *.install`
   - (Adjust paths based on what was changed; keep test files unstashed)

3. Run the added/modified tests against unfixed code:
   - `ddev exec ../vendor/bin/phpunit $ADDED_TESTS $MODIFIED_TESTS`

4. Verify tests FAIL:
   - If all tests fail: VALIDATED. Tests are legitimate.
   - If some tests pass: Those tests are invalid. They don't test the fix.
   - If all tests pass: ALL tests are invalid. Complete rewrite needed.

5. Restore the fix:
   - `git stash pop`

6. Report results:
   ```
   ## Test Validation
   - Tests that correctly FAIL without fix: 22/24
   - Tests that incorrectly PASS without fix: 2/24
     - LiteLlmGuardrailTest::testDefaultConfig (trivially true assertion)
     - LiteLlmAiProviderGuardrailTest::testEmptyList (tests empty input, not fix)
   ```

7. If invalid tests found:
   - Rewrite them to actually test the behavioral change
   - Re-run validation
   - Max 2 rewrite cycles
```

### 2. Update `drupal-verifier` agent

Add a "test legitimacy check" to the verifier's responsibilities:

```markdown
## Verification Type: Test Legitimacy

When verifying test coverage:
1. Stash source changes, keep test files
2. Run tests against unfixed code
3. Confirm tests FAIL
4. Restore stash
5. Report which tests are legitimate vs trivial
```

### 3. Handle edge cases

```markdown
## Edge Cases

- **Multiple stash targets:** If fix touches both src/ and config/, stash both.
  Use explicit paths, not `git stash` (which stashes everything).

- **Test-only changes:** If the MR only adds tests (no source changes),
  skip validation. Tests for new features (not bug fixes) may legitimately
  pass without a "fix."

- **Database state changes:** Some tests depend on module installation state
  that can't be stashed. For kernel/functional tests, note this limitation
  in the report.

- **Git stash conflicts:** If `git stash pop` fails, use `git stash drop`
  and `git checkout -- src/ config/` to restore from the commit.
```

### 4. Include validation results in push gate summary

```markdown
## Push Gate Summary Addition

Under "Test Results", add:
- Tests passing (with fix): 24/24
- Tests failing (without fix): 22/24 (validated)
- Tests trivially passing: 2/24 (noted, acceptable for config defaults)
```

## Acceptance Criteria

- [ ] Every test run includes a stash/unstash validation cycle
- [ ] Tests that pass without the fix are flagged as invalid
- [ ] Invalid tests trigger automatic rewrite (max 2 cycles)
- [ ] Push gate summary includes validation results
- [ ] git stash operations are safe (no data loss)
- [ ] Edge cases (test-only changes, DB state) handled gracefully

## Files to Modify

1. `.claude/skills/drupal-contribute-fix/SKILL.md` - Add Test Validation phase
2. `.claude/agents/drupal-verifier.md` - Add test legitimacy check
