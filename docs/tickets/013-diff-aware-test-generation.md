# TICKET-013: Diff-Aware Test Scaffolding

**Status:** COMPLETED
**Priority:** P2 (Medium)
**Affects:** `.claude/skills/drupal-contribute-fix/SKILL.md`, test generation workflow
**Type:** Enhancement

## Problem

In the #3579478 session, test writing took ~40 minutes with multiple iterations (5 -> 7 -> 5 -> 7 -> 24 tests). The process was:

1. Read entire source files
2. Manually identify what needs testing
3. Write tests
4. Run tests, find issues
5. Fix tests
6. Repeat

This is slow because the model has to understand the entire codebase to determine what the diff changed behaviorally. A smarter approach: analyze the diff first to identify exactly which methods/code paths changed, then generate targeted test stubs.

## Current Test Writing Flow

```
Read all source files (multiple files, hundreds of lines)
-> Mentally determine what changed
-> Write tests based on overall understanding
-> Iterate when tests fail or miss coverage
```

## Desired Test Writing Flow

```
Parse the diff
-> Extract: new methods, changed methods, new conditionals, new error paths
-> For each behavioral change, generate a test stub:
   - Method: testNewMethodName()
   - Setup: mock dependencies based on constructor signature
   - Assertion: verify the behavioral change
-> Fill in stubs with actual test logic
-> Run tests (fewer iterations because stubs are targeted)
```

## Example: #3579478 Diff Analysis

The MR diff for #3579478 contained 6 files. Analyzing the diff would have revealed:

| File | Change | Behavioral Test Needed |
|------|--------|----------------------|
| `LiteLlmGuardrail.php` (NEW) | New plugin class with `processInput()`, `processOutput()` | Test both methods return PassResult |
| `LiteLlmAiClient.php` | `guardrails()` method added, `chat()` method modified to inject guardrails | Test guardrails() response parsing, error cases, chat() guardrail injection |
| `LiteLlmAiConfigForm.php` | `syncGuardrails()` handler added, entity creation logic | Test entity creation, ID truncation, error handling |
| `LiteLlmAiProviderGuardrailTest.php` (NEW) | Tests for `extractLiteLlmGuardrailNames()` | Already a test file, verify coverage |
| `ai_provider_litellm.schema.yml` | New config schema for guardrail | Verify schema validates correctly |

This analysis could have been done in ~2 minutes and would have produced a clear test plan before writing any test code.

## Implementation Plan

### 1. Add "Diff Analysis" phase to test writing

Before writing any tests, analyze the diff:

```markdown
## Test Planning from Diff

Before writing test code, analyze the diff to create a test plan:

1. Parse the diff (from mr-{iid}-diff.patch or git diff):
   ```
   For each file in the diff:
     - Is it a NEW file? -> Test all public methods
     - Is it a MODIFIED file? -> Test only changed/added methods
     - Is it a config file? -> Verify schema/values
     - Is it a test file? -> Skip (it IS a test)
   ```

2. For each changed/new method, identify:
   - Input types and edge cases
   - Return type and expected values
   - Error/exception paths
   - Dependencies that need mocking
   - Interactions with other changed methods

3. Generate test plan as a checklist:
   ```
   ## Test Plan
   - [ ] LiteLlmGuardrail::processInput() returns PassResult
   - [ ] LiteLlmGuardrail::processOutput() returns PassResult
   - [ ] LiteLlmAiClient::guardrails() parses valid response
   - [ ] LiteLlmAiClient::guardrails() handles empty response
   - [ ] LiteLlmAiClient::guardrails() propagates connection error
   - [ ] LiteLlmAiClient::guardrails() propagates HTTP 500
   - [ ] LiteLlmAiClient::guardrails() propagates HTTP 401
   - [ ] syncGuardrails() creates entity with correct ID
   - [ ] syncGuardrails() truncates ID to 64 chars
   - [ ] syncGuardrails() sanitizes special characters in ID
   - [ ] syncGuardrails() updates existing entity
   - [ ] syncGuardrails() shows error on connection failure
   - [ ] extractLiteLlmGuardrailNames() extracts names correctly
   - [ ] extractLiteLlmGuardrailNames() handles duplicates
   - [ ] extractLiteLlmGuardrailNames() filters by type
   ```

4. Use the test plan to write tests methodically (one per checklist item)
```

### 2. Add to `drupal-contribute-fix` references

Create a new reference file: `references/test-planning-from-diff.md`

Content:
- How to parse diff for behavioral changes
- Common patterns: new method, modified conditional, new error path, config change
- Test stub templates for each pattern
- How to determine mock requirements from constructor signatures

### 3. Integrate with the parallel review phase (TICKET-003)

During the static code review (while DDEV sets up), generate the test plan. This way, when DDEV is ready, test writing begins immediately with a clear plan instead of ad-hoc exploration.

## Acceptance Criteria

- [ ] Every test writing session starts with a diff-based test plan
- [ ] Test plan is a checklist of specific test cases derived from the diff
- [ ] Test stubs are generated before full test code
- [ ] Fewer iteration cycles (target: max 2, down from 4-5)
- [ ] Total test writing time reduced by ~30%

## Files to Modify/Create

1. `.claude/skills/drupal-contribute-fix/SKILL.md` - Add "Test Planning from Diff" phase
2. `.claude/skills/drupal-contribute-fix/references/test-planning-from-diff.md` - NEW reference
