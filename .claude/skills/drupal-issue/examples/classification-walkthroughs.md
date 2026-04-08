# `/drupal-issue` classification walkthroughs

Reference examples showing how the classification step maps real-world
issue states onto the action categories (A-I) in `SKILL.md`. Not loaded
by default; open when you want to see how a specific category fires in
practice.

```
/drupal-issue 3561693
→ Reads issue, sees it's "Needs work" because reviewer couldn't reproduce
→ Classifies as: Reproduce a bug + respond to reviewer (A + E)
→ Delegates to /drupal-issue-review, then drafts comment

/drupal-issue 3577386
→ Reads issue, sees maintainer flagged missing third-party module changes
→ Classifies as: Adapt code (C — port from parent issue)
→ Reads parent issue #3491351, identifies missing pieces, adapts MR

/drupal-issue https://www.drupal.org/project/ai/issues/3558728
→ Reads issue, sees it's RTBC with a working MR
→ Classifies as: Review/test existing MR (B)
→ Reviews the code, optionally sets up env to verify

/drupal-issue 3577812
→ Reads issue, sees it was closed as "cannot reproduce"
→ Classifies as: Just reply with context (F)
→ Drafts a comment explaining when/how it can be reproduced

/drupal-issue 3580001
→ Reads issue, sees "Needs review" with a clean MR and no objections
→ Classifies as: Re-review (I — no code changes needed)
→ Sets up env, verifies the fix, drafts a confirming comment
→ Does NOT add "improvements" or refactor working code
```
