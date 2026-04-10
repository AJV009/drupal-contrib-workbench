# Ticket 036 — Comment Quality Gate (Anti-Filler) — Design Spec

**Status:** SPEC
**Priority:** P2
**Type:** Enhancement

## Goal

Add 4 mechanical filters to `/drupal-issue-comment` that enforce comment
brevity: word-count limits by type, audience-awareness prompt, filler-pattern
regex check, and a two-version presentation (full vs compressed) for user choice.

## Files

### Created (1)
| Path | Lines | Purpose |
|---|---|---|
| `.claude/skills/drupal-issue-comment/references/filler-patterns.txt` | ~25 | One pattern per line, loaded by the skill for grep checking |

### Modified (2)
| Path | Change |
|---|---|
| `.claude/skills/drupal-issue-comment/SKILL.md` | New "Comment Quality Gate" section with 4 filters, inserted before "Output" |
| `docs/tickets/036-comment-quality-gate.md` + `00-INDEX.md` | Status flip + resolution |

## Filter 1: Word count limits

| Comment type | Max words | Selected when |
|---|---|---|
| Follow-up to maintainer | 200 | Default |
| Scope expansion explanation | 350 | Category E (feedback-loop) or explicit scope change |
| "Confirming this works" | 80 | MR verified, working correctly |
| Initial issue reply | 250 | First comment on the issue from us |

If draft exceeds the limit: compress or fail. The skill MUST NOT present
a draft that exceeds the limit to the user.

## Filter 2: Audience filter prompt

Injected at the start of the comment-drafting context as a mandatory preamble:

> The maintainers reading this comment already know how this module works.
> They have read the issue and the MR diff. They do NOT need: module
> explanations, issue restatements, MR diff summaries, or congratulatory
> framing. They DO need: what changed since last review, the specific
> decision point requiring input, and new evidence they don't already have.

## Filter 3: Filler-pattern check

Load `references/filler-patterns.txt`. Grep draft against each pattern
(case-insensitive). Every match must be rewritten or removed before
presenting. Log violations.

## Filter 4: Two-version presentation

After all filters pass, present the draft to the user with TWO versions:

```
=== FULL VERSION (N words) ===
[the filtered draft]

=== COMPRESSED VERSION (M words) ===
[first 100 words + bullet points only]

Pick: [k]eep full | [c]ompressed | [e]dit
```

User picks one. The chosen version goes to the `.html` output file.

## Acceptance

| # | Criterion | Test |
|---|---|---|
| 1 | Draft for a scope-expansion case ≤ 350 words with no filler | Wiring review |
| 2 | Inserting "as you can see" triggers filler flag | Wiring review |
| 3 | Word count configurable per type via the table | Code review |
| 4 | filler-patterns.txt exists with ≥ 22 patterns | File check |
| 5 | Two-version presentation shows full + compressed | Wiring review |
