# Pressure Test 04: Hands-Free Operation

## Scenario

User invokes `/drupal-issue` and the skill should auto-chain through all phases.

## Setup Context

```
/drupal-issue https://www.drupal.org/project/token/issues/6666666
```

Issue #6666666: Bug in token module, "Needs review" status, MR !5 exists with
passing pipeline. 3 comments, last by maintainer asking for code review.

## Expected Behavior WITH Skill

Agent proceeds through the entire workflow without stopping to ask the user:
1. Dispatches fetcher agent immediately (no "I'm using the drupal-issue skill...")
2. Uses enriched summary from fetcher (no re-reading artifacts)
3. Classifies as "review existing MR" automatically
4. Invokes `/drupal-issue-review` without asking "should I proceed?"
5. DDEV setup in background, static diff review in parallel
6. After DDEV ready, runs tests
7. If issues found, invokes `/drupal-contribute-fix`
8. ONLY stops at push gate

## Expected Behavior WITHOUT Skill (Baseline)

Agent announces what it will do. Presents classification. Asks "should I set up
an environment?" Waits between each phase for user confirmation.

## What to Verify

- [ ] No "I'm using the X skill" announcements
- [ ] No "Should I proceed?" questions
- [ ] Classification happens without user input
- [ ] Skill transitions happen automatically
- [ ] Only stop is the push gate (or comment draft if no code changes)
- [ ] Tasks created lazily (not 6 upfront)
