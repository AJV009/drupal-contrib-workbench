# TICKET-036: Comment Quality Gate (Anti-Filler)

**Status:** NOT_STARTED
**Priority:** P2
**Affects:** `.claude/skills/drupal-issue-comment/SKILL.md`, new file `.claude/skills/drupal-issue-comment/references/filler-patterns.txt`
**Type:** Enhancement

## Problem (with evidence)

Across multiple sessions the user complains about comment fluff. The existing IRON LAWS in `/drupal-issue-comment` ("NO SELF-CONGRATULATORY FILLER", "NO EM DASHES") don't bite hard enough.

**Session `2c83c3e7-c7aa-4e55-a2f3-5affa0787990.jsonl`** (Apr 9 2026, issue 3583760):
> "this is nice so far, **750 words comment no ones gonna read, remove ALL the obvious and fluff stuff from it**, just mention the scope expansion and need in like couple of lines max, and few things that are needed for the new reviewer to know, NOTHING ELSE matters for others bro, right?"

**Session `2fa2321f-e7a2-4f14-84dd-b40354227055.jsonl`** (Apr 9 2026, issue 3560681):
> "**reduce/remove anything redundant because akhil and marcus are already aware** what goes in and out of the modules so its just junk at this point"

The pattern is consistent across multiple recent sessions: workflow drafts a thorough but bloated comment, user has to demand compression.

## Solution: Three mechanical filters added to `/drupal-issue-comment`

### Filter 1: Word count limit by comment type

| Comment type             | Default limit | When to use            |
|--------------------------|---------------|------------------------|
| Follow-up to maintainer  | 200 words     | Default                |
| Scope expansion explanation | 350 words  | Comment explains why scope grew |
| "Confirming this works"  | 80 words      | Just acknowledging a fix is good |
| Initial issue reply      | 250 words     | First response on a new issue |

If the draft exceeds the limit, the skill MUST justify (in a `<thinking>` block invisible to user) why each paragraph cannot be removed, then either compress or fail with the message "comment exceeds X words; rewrite shorter."

The comment type is selected by the controller based on classification category (mapping documented in SKILL.md).

### Filter 2: Audience filter prompt

Prepend to the comment-drafting context:

> "The maintainers reading this comment (akhil, marcus, cadence96, kristen pol, etc.) already know how this module works internally. They have read the issue and the MR. They do NOT need: explanations of what the module does, restatements of the issue, summaries of the MR diff they already have, or congratulatory framing about how thorough the work was. They DO need: what changed since their last review, the specific decision point that needs their input, and any new evidence they don't already have."

### Filter 3: Filler-pattern regex check

Before presenting the draft, grep for these patterns. Each match must be removed or the paragraph rewritten. Patterns kept in `.claude/skills/drupal-issue-comment/references/filler-patterns.txt`:

```
as you can see
this fix carefully
I have completed
we have now successfully
this implementation
I would like to
in this comment
to summarize
in conclusion
it is important to note
please find attached
hopefully this helps
let me know
feel free to
just to clarify
as mentioned above
as previously stated
in essence
in other words
basically
essentially
fundamentally
```

The skill loads this file and runs grep against the draft. Each match logs a violation; the skill must fix all violations before presenting.

### Filter 4 (optional bonus): Push gate two-version diff

When presenting the final draft to the user, also show a "compressed" version: first 100 words + bullet points only. User can pick `[k]eep | [c]ompress | [e]dit` before push.

## Acceptance

1. Re-running the comment phase for issue 3583760 (a recent scope-expansion case) produces a comment ≤ 350 words with no flagged filler patterns
2. Manually inserting "as you can see" into a draft causes the gate to flag it
3. Word count limit is configurable per-comment-type via the SKILL.md table
4. `.claude/skills/drupal-issue-comment/references/filler-patterns.txt` exists with at least the 22 patterns above

## Dependencies

None.

## Notes

This is small (probably 1-2 hours of skill editing). It's P2 because it doesn't block anything else and the existing IRON LAWS already partially address it — this just makes the enforcement mechanical instead of prose.

The filler-patterns.txt file should be easy to extend. As new bad patterns emerge from session evidence (logged in ticket 038), append them here.

## Resolution (2026-04-10)

Shipped all 4 filters as a mandatory "Comment Quality Gate" section
in `/drupal-issue-comment` SKILL.md, inserted before the Output section.

### What shipped

- `references/filler-patterns.txt` (33 patterns, 11 more than the 22 minimum)
- **Filter 1:** Word count limits by comment type (80/200/250/350 words)
- **Filter 2:** Audience filter prompt (maintainers already know the module)
- **Filter 3:** Filler-pattern regex check (grep against 33 patterns, zero violations required)
- **Filter 4:** Two-version presentation (full + compressed, user picks k/c/e)
- **Rationalization prevention table** (4 rows)

### Acceptance

| # | Criterion | Result |
|---|---|---|
| 1 | Scope-expansion draft ≤ 350 words, no filler | WIRING — filter enforces mechanically |
| 2 | "as you can see" triggers flag | WIRING — pattern is in filler-patterns.txt line 1 |
| 3 | Word count configurable per type | PASS — table in SKILL.md |
| 4 | filler-patterns.txt ≥ 22 patterns | PASS — 33 patterns |
| 5 | Two-version presentation | WIRING — Filter 4 prose in SKILL.md |
