# Pressure Test 05: Test Validation (Stash/Unstash)

## Scenario

Agent has written tests and they pass. Validate they're not trivially true.

## Setup Context

```
You just wrote 6 tests for a fix in ai_provider_litellm.
Source changes: src/LiteLLM/LiteLlmAiClient.php (removed catch-all exception handler)
Test files: tests/src/Unit/LiteLlmAiClientTest.php (6 tests, all passing)

All tests pass against the fixed code. Now validate the tests.
```

## Expected Behavior WITH Skill

Agent performs stash/unstash validation:
1. `git stash push -- src/` (stash source changes, keep tests)
2. Run tests against unfixed code
3. Verify tests FAIL (proving they detect the bug)
4. `git stash pop` (restore fix)
5. Reports: "6/6 tests correctly fail without fix"

## Expected Behavior WITHOUT Skill (Baseline)

Agent says "all tests pass" and moves on. No validation that tests
actually detect the bug.

## What to Verify

- [ ] Agent stashes source changes (not test files)
- [ ] Agent runs tests against unfixed code
- [ ] Agent verifies tests fail
- [ ] Agent restores the stash
- [ ] Agent reports validation results
- [ ] If tests pass without fix, agent rewrites them
