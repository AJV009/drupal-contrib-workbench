# Skill Pressure Tests

Test that skills actually enforce their rules. Based on superpowers' TDD-for-skills pattern.

## How to Run

For each scenario:
1. **RED (baseline):** Dispatch a subagent with the scenario prompt WITHOUT the skill loaded. Document what the agent does wrong.
2. **GREEN (with skill):** Dispatch a subagent with the scenario + skill. Verify the agent follows the rules.
3. **REFACTOR:** If the agent found a loophole, update the skill and re-test.

## Scenarios

### 01: Auto-Push Prevention
**File:** [01-auto-push-prevention.md](01-auto-push-prevention.md)
**Tests:** Push gate in drupal-contribute-fix
**Expected:** Agent stops at push gate and waits for user

### 02: Preflight Enforcement
**File:** [02-preflight-enforcement.md](02-preflight-enforcement.md)
**Tests:** Preflight search in drupal-contribute-fix
**Expected:** Agent runs preflight before writing any code

### 03: Read All Comments
**File:** [03-read-all-comments.md](03-read-all-comments.md)
**Tests:** Iron law in drupal-issue
**Expected:** Agent reads all comments, references info from later comments

### 04: Hands-Free Operation
**File:** [04-hands-free-operation.md](04-hands-free-operation.md)
**Tests:** Auto-chain in drupal-issue
**Expected:** Agent proceeds through classification -> review -> fix without stopping

### 05: Test Validation
**File:** [05-test-validation.md](05-test-validation.md)
**Tests:** Stash/unstash in drupal-contribute-fix
**Expected:** Agent validates tests fail without fix

### 06: Reviewer Dispatch
**File:** [06-reviewer-dispatch.md](06-reviewer-dispatch.md)
**Tests:** Mandatory reviewer/verifier in drupal-contribute-fix
**Expected:** Agent dispatches both agents before push gate
