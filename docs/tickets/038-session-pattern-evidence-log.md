# TICKET-038: Session Pattern Evidence Log (For Future Skill Tuning)

**Status:** NOT_STARTED
**Priority:** P3
**Affects:** New file `docs/findings/session-pattern-evidence.md`
**Type:** Knowledge / Reference

## Purpose

Per user direction: "**log them into a ticket file for improving the skills later using the skill improvement skill thing. And also for tuning our next workflow version.**"

This ticket creates a permanent reference log of the **four recurring failure patterns** observed in real session JSONLs from April 2026. The log is not actionable on its own — it is the raw evidence that drove tickets 029, 030, 031, 036 in phase 2, and will be the input data for the `skill-maintainer` skill when it tunes skills in future iterations.

Future Claude sessions running `skill-maintainer` should read this file as ground-truth evidence for what is failing in real production usage, NOT as "ideas to maybe consider."

## What this ticket does

Create the file `docs/findings/session-pattern-evidence.md` with the four patterns documented below. Each pattern includes:
- The pattern name and one-line description
- The user's own framing (verbatim quote from their request)
- Concrete session JSONL evidence (session id, date, issue id, direct quotes)
- Which phase 2 ticket addresses it
- What "fully solved" looks like

## Patterns to document

### Pattern A — Cross-issue scope merging (the user notices, not the workflow)

**User's framing**: "there have been instances recently where a lot of issues got cross connected causing me to close my new ones in favour of expanding the scope on an old one and patching stuff there instead of hacking a new one."

**Evidence**:

Session `2c83c3e7-c7aa-4e55-a2f3-5affa0787990.jsonl` on issue 3583760, Apr 9 2026, 113 user messages, 2.2 MB:
- "I rather have this fixed man, also thinking why stop at name, lets also patch that other arguments thing, look into that issue, pull its complete conversation and see what is being done there. **MAYBE we can move all the stuff we are doing here to that issue, if the conversations there make sense for this scope**"
- "I got push access to the existing MR in 3582345, **lets work on this issue complete end to end and go beyond just some particular argument**... **draft a comment mentioning why we expanded the scope of this issue**"

Session `14f9b85b-2627-45a3-ba7c-955836268a1f.jsonl`, Apr 9 2026:
- "So i previously worked on this https://www.drupal.org/project/ai_agents/issues/3560681 and after sometime I worked on this https://www.drupal.org/project/ai/issues/3582345... **I just need you to verify if anything from the ai_agents issue need to removed or refactored to accommodate ai issue 3582345**"

**Addressed by**: ticket 029 (pre-classification cross-issue resonance check) + ticket 028 (bd as the shared substrate)

**"Solved" looks like**: a `RESONANCE_REPORT` is automatically generated for every new issue, surfacing DUPLICATE_OF / RELATED_TO / SCOPE_EXPANSION_CANDIDATE before classification, without user prompting.

### Pattern B — Shallow → architectural escalation (the user demands "the proper way")

**User's framing**: "the workflow suggested me some fixes but when I prompted more to give me a proper solution it actually gave me a more detailed in depth architectural solution that better. I want the workflow to be able to do that without having me prompt it."

**Evidence**:

Session `9b75cb81-edc3-4c93-b4f1-35c3be6b957d.jsonl` on issue 3581952, Apr 8 2026, 4.35 MB:
- ADDITIONAL INSTRUCTIONS injected at session start: "**this is a major setback on our side what marcus is saying here makes sense was this issue worked on a wrong pretense by any chance? I need you to take a thorough look into the complete issue properly once again**"
- Mid-session: "**NO please DO NOT mock any modules or features**, Drupal development is always considered to be critical, install or bring in whatever modules and stuff as needed and **do this the PROPER way**, we are recreating the issue and solution using an alternative approach"
- "Now that we have verified this little issue, can you solve the problem the original issue creator opened this with using the docs and stuff marcus mentioned about? **Just to verify if we can do this without this MR at all**"

Session `2c83c3e7-...` on issue 3583760:
- "hmmm what do you think? I feel the model will ALWAYS respond with something right? **can there be a situation where this returns null from claude/openai or whatever? should we have covered it?**"
- "**can we fix this smartly? think of a way... I don't want to duplicate validation everywhere right? lets maybe add it into the scope of this issue**"

**Addressed by**: ticket 030 (solution-depth gate, both pre-fix and post-fix, complexity-driven)

**"Solved" looks like**: every issue has a `01b-solution-depth-pre.md` with at least 2 distinct approaches and an explicit decision; complex issues additionally get a `02b-solution-depth-post.md` smell-check that can fail and force a re-do.

### Pattern C — Workflow determinism failures (steps silently skipped)

**User's framing**: "I have noticed not every time it follows the stuff properly, I mean the workflows, if we can make the flows more deterministic from the point they get invoked from the issue sh file."

**Evidence**: Audit of `DRUPAL_ISSUES/[0-9]*/workflow/00-classification.json` files at the time of phase 2 planning:
- 36 issue dirs total
- 21 missing the classification artifact
- Filtering to only issues with mtime ≥ Apr 8 (post-ticket-023 finalization), **5 still missing**:
  - 3553458 (active session 11 min old at audit time)
  - 3582345 (active DDEV stack)
  - 3583760 (recent active work)
  - 3580690 (active DDEV stack)
  - 3581955 (recent companion-issue work)

The contract from ticket 023 is in place, but prose enforcement leaks under load.

**Addressed by**: ticket 031 (launcher sentinel + skill reinstate, NOT abort) + ticket 033 (Agent Teams TaskCompleted hooks, if research validates)

**"Solved" looks like**: 100% of issues started after the fix have a non-PENDING `00-classification.json` by the time any companion skill runs.

### Pattern D — Comment quality (filler + length complaints)

**Evidence**:

Session `2c83c3e7-...`:
- "this is nice so far, **750 words comment no ones gonna read, remove ALL the obvious and fluff stuff from it**, just mention the scope expansion and need in like couple of lines max"

Session `2fa2321f-e7a2-4f14-84dd-b40354227055.jsonl`, Apr 9 2026:
- "**reduce/remove anything redundant because akhil and marcus are already aware** what goes in and out of the modules so its just junk at this point"

**Addressed by**: ticket 036 (comment quality gate with word count limit + audience filter + filler regex)

**"Solved" looks like**: drafts under 350 words by default, no flagged filler patterns, audience-aware framing.

## Format guidance for skill-maintainer (future sessions)

When `skill-maintainer` runs to tune skills, it should:
1. Read this file first as the ground-truth evidence
2. For any pattern listed here, find the addressing ticket and check its status
3. If the addressing ticket is COMPLETED but the pattern still occurs in new sessions, flag the gap (this means the implemented fix is not biting hard enough)
4. If a NEW pattern is observed in new sessions, append it to this file with the same structure (user framing, session evidence, addressing ticket if any, "solved" definition)

This file is therefore a **living evidence ledger**, not a frozen snapshot.

## Acceptance

1. The file `docs/findings/session-pattern-evidence.md` exists with all 4 patterns documented per the structure above
2. Each pattern has: user framing, ≥1 verbatim session quote, the addressing ticket number, and a "solved looks like" definition
3. The file references the actual session JSONL filenames so future inspections can find them
4. The "Format guidance for skill-maintainer" section exists at the bottom

## Dependencies

None. This is documentation of evidence that already exists in the session JSONLs.

## Notes

This ticket is unusual: it produces reference material, not a code change. It's marked NOT_STARTED but its "completion" is just creating the file. After this lands, future tickets that address new patterns should ALSO append to this file as part of their work.

The file lives in `docs/findings/` (a new directory) rather than `docs/tickets/` to keep the distinction clear: tickets are work to do, findings are evidence informing the work.

## Resolution (2026-04-10)

Created `docs/findings/session-pattern-evidence.md` (201 lines) with all
4 patterns documented per the ticket spec.

Each pattern has: user framing (verbatim quotes), session JSONL references,
addressing ticket number + status, and a "solved looks like" definition.
The "Format guidance for skill-maintainer" section is at the bottom.

All 4 addressing tickets are now COMPLETED:
- Pattern A (scope merging) → 029 + 028 + 034
- Pattern B (shallow→architectural) → 030
- Pattern C (workflow determinism) → 031 + 033 + 039
- Pattern D (comment quality) → 036
