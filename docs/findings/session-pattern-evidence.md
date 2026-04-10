# Session Pattern Evidence Log

This is a **living evidence ledger** for the `skill-maintainer` skill and
future workflow tuning. Each pattern includes verbatim user quotes, session
JSONL references, the addressing ticket, and a definition of "solved."

Future sessions: if a documented pattern still occurs after its addressing
ticket is COMPLETED, flag the gap. If a NEW pattern is observed, append it
here with the same structure.

---

## Pattern A — Cross-issue scope merging

**One-line:** The user notices cross-issue connections; the workflow doesn't.

**User's framing:** "there have been instances recently where a lot of
issues got cross connected causing me to close my new ones in favour of
expanding the scope on an old one and patching stuff there instead of
hacking a new one."

### Evidence

**Session `2c83c3e7-c7aa-4e55-a2f3-5affa0787990.jsonl`** (Apr 9 2026,
issue 3583760, 113 user messages, 2.2 MB):

> "I rather have this fixed man, also thinking why stop at name, lets also
> patch that other arguments thing, look into that issue, pull its complete
> conversation and see what is being done there. **MAYBE we can move all the
> stuff we are doing here to that issue, if the conversations there make
> sense for this scope**"

> "I got push access to the existing MR in 3582345, **lets work on this
> issue complete end to end and go beyond just some particular argument**...
> **draft a comment mentioning why we expanded the scope of this issue**"

**Session `14f9b85b-2627-45a3-ba7c-955836268a1f.jsonl`** (Apr 9 2026):

> "So i previously worked on this
> https://www.drupal.org/project/ai_agents/issues/3560681 and after
> sometime I worked on this
> https://www.drupal.org/project/ai/issues/3582345... **I just need you to
> verify if anything from the ai_agents issue need to removed or refactored
> to accommodate ai issue 3582345**"

### Addressing ticket

**029** — Pre-classification cross-issue resonance check (COMPLETED).
Also: **028** (bd as shared substrate), **034** (cross-issue memory via bd).

### "Solved" looks like

A `RESONANCE_REPORT` is automatically generated for every new issue,
surfacing DUPLICATE_OF / RELATED_TO / SCOPE_EXPANSION_CANDIDATE before
classification, without user prompting. The fetcher's PRIOR KNOWLEDGE
query (034) surfaces historical context from bd.

---

## Pattern B — Shallow-to-architectural escalation

**One-line:** The workflow proposes narrow fixes; the user has to demand
"the proper way."

**User's framing:** "the workflow suggested me some fixes but when I
prompted more to give me a proper solution it actually gave me a more
detailed in depth architectural solution that better. I want the workflow
to be able to do that without having me prompt it."

### Evidence

**Session `9b75cb81-edc3-4c93-b4f1-35c3be6b957d.jsonl`** (Apr 8 2026,
issue 3581952, 4.35 MB):

> ADDITIONAL INSTRUCTIONS injected at session start: "**this is a major
> setback on our side what marcus is saying here makes sense was this issue
> worked on a wrong pretense by any chance? I need you to take a thorough
> look into the complete issue properly once again**"

> "**NO please DO NOT mock any modules or features**, Drupal development is
> always considered to be critical, install or bring in whatever modules and
> stuff as needed and **do this the PROPER way**, we are recreating the
> issue and solution using an alternative approach"

> "Now that we have verified this little issue, can you solve the problem
> the original issue creator opened this with using the docs and stuff
> marcus mentioned about? **Just to verify if we can do this without this
> MR at all**"

**Session `2c83c3e7-...`** (issue 3583760):

> "hmmm what do you think? I feel the model will ALWAYS respond with
> something right? **can there be a situation where this returns null from
> claude/openai or whatever? should we have covered it?**"

> "**can we fix this smartly? think of a way... I don't want to duplicate
> validation everywhere right? lets maybe add it into the scope of this
> issue**"

### Addressing ticket

**030** — Solution-depth gate, pre-fix (opus) + post-fix (sonnet)
(COMPLETED).

### "Solved" looks like

Every issue has a `01b-solution-depth-pre.md` with at least 2 distinct
approaches and an explicit decision. Complex issues additionally get a
`02b-solution-depth-post.md` smell-check that can fail and force a re-do
with the architectural approach.

---

## Pattern C — Workflow determinism failures

**One-line:** Steps silently skip despite prose enforcement.

**User's framing:** "I have noticed not every time it follows the stuff
properly, I mean the workflows, if we can make the flows more
deterministic from the point they get invoked from the issue sh file."

### Evidence

Audit of `DRUPAL_ISSUES/[0-9]*/workflow/00-classification.json` at the
time of phase 2 planning:

- 36 issue dirs total
- 21 missing the classification artifact
- After filtering to only issues with mtime >= Apr 8 (post-ticket-023):
  **5 still missing** (3553458, 3582345, 3583760, 3580690, 3581955)

The contract from ticket 023 is in place, but prose enforcement leaks
under load.

### Addressing tickets

**031** — Launcher sentinel + skill reinstate (COMPLETED).
**033** — Research: Agent Teams TaskCompleted hooks (COMPLETED — verdict:
ADOPT hooks only, reject Agent Teams).
**039** — Mechanical enforcement hooks: PreToolUse push gate + Stop
workflow-completion gate (COMPLETED).

### "Solved" looks like

100% of issues started after the fix have a non-PENDING
`00-classification.json` by the time any downstream skill runs. Push gate
mechanically blocks `git push` without verification artifacts. Stop hook
blocks "claiming done" mid-workflow.

---

## Pattern D — Comment quality (filler + length)

**One-line:** Drafted comments are too long and full of filler; the user
has to manually demand compression.

### Evidence

**Session `2c83c3e7-...`** (issue 3583760):

> "this is nice so far, **750 words comment no ones gonna read, remove ALL
> the obvious and fluff stuff from it**, just mention the scope expansion
> and need in like couple of lines max, and few things that are needed for
> the new reviewer to know, NOTHING ELSE matters for others bro, right?"

**Session `2fa2321f-e7a2-4f14-84dd-b40354227055.jsonl`** (Apr 9 2026,
issue 3560681):

> "**reduce/remove anything redundant because akhil and marcus are already
> aware** what goes in and out of the modules so its just junk at this
> point"

### Addressing ticket

**036** — Comment quality gate with word count limit + audience filter +
filler-pattern regex + two-version presentation (COMPLETED).

### "Solved" looks like

Drafts under 350 words by default, no flagged filler patterns from the
33-pattern blacklist, audience-aware framing, user sees both full and
compressed versions and picks one.

---

## Format guidance for skill-maintainer (future sessions)

When `skill-maintainer` runs to tune skills, it should:

1. **Read this file first** as the ground-truth evidence for what fails in
   real production usage.
2. For any pattern listed here, find the addressing ticket and check its
   status.
3. If the addressing ticket is COMPLETED but the pattern **still occurs**
   in new sessions, **flag the gap** — the implemented fix is not biting
   hard enough.
4. If a **NEW pattern** is observed in new sessions, **append it** to this
   file with the same structure: user framing, session evidence, addressing
   ticket (if any), "solved" definition.

This file is a living evidence ledger, not a frozen snapshot.
