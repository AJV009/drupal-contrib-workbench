# Pressure Test 03: Read All Comments

## Scenario

Issue with 10 comments where critical info is in comment #7.

## Setup Context

```
Issue #7777777 for the paragraphs module.
- Comment #1: Bug report (vague)
- Comments #2-6: Various users confirming, adding details
- Comment #7: Maintainer says "Do NOT change the entity storage handler.
  Use the presave hook instead. The storage handler is being refactored in #7777000."
- Comments #8-10: More user reports

Classify this issue and take action.
```

## Expected Behavior WITH Skill

Agent reads ALL 10 comments chronologically. References the maintainer's
instruction from comment #7. Uses presave hook approach, not storage handler.

## Expected Behavior WITHOUT Skill (Baseline)

Agent reads first few comments, possibly the last comment. Misses comment #7.
May attempt to modify the storage handler (exactly what maintainer said not to do).

## What to Verify

- [ ] Agent explicitly reads all comments
- [ ] Agent references comment #7 content
- [ ] Agent follows maintainer instruction (presave hook, not storage handler)
- [ ] Agent references the related issue #7777000
