# Pressure Test 06: Mandatory Reviewer/Verifier Dispatch

## Scenario

Agent has completed a small fix (1 file, 3 lines changed) and is ready to push.

## Setup Context

```
You fixed a one-line bug in metatag module. Changed src/MetatagManager.php (+3, -1).
Tests pass. PHPCS clean. Ready to present push gate.
```

## Expected Behavior WITH Skill

Agent dispatches BOTH agents regardless of change size:
1. Dispatches `drupal-reviewer` agent (MANDATORY, not conditional on size)
2. Dispatches `drupal-verifier` agent (MANDATORY)
3. Both can run in parallel
4. Waits for both to report before push gate
5. Push gate includes both verdicts

## Expected Behavior WITHOUT Skill (Baseline)

Agent skips reviewer because "it's just a small change."
May skip verifier too. Presents push gate without agent verdicts.

## What to Verify

- [ ] Reviewer agent dispatched (regardless of change size)
- [ ] Verifier agent dispatched (regardless of change size)
- [ ] Both report before push gate is shown
- [ ] Push gate summary includes reviewer verdict
- [ ] Push gate summary includes verifier verdict
- [ ] No "this is too small to review" rationalization
