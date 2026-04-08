# Workspace Skill Patterns

Formatting templates for the conventions used across this workspace's
skills. Copy the template that matches what you're adding, then fill in
the specifics.

## IRON LAW block

Used for the 1-4 top-priority warnings at the very top of a workflow
skill, right after the `# skill-name` heading.

```markdown
> **IRON LAW:** <SHORT CAPS-LOCK IMPERATIVE>. <One sentence of detail on what this rule prevents.>

> **IRON LAW (<SUBCATEGORY>):** <SHORT IMPERATIVE>. <Detail.>
```

Rules:

- Max 4 per skill. When everything shouts, nothing prioritizes.
- First sentence ALL CAPS imperative. Detail in normal case.
- Subcategory in parentheses after `IRON LAW` (e.g., `IRON LAW (TDD)`,
  `IRON LAW (VERIFICATION)`).
- Use `>` blockquote syntax — visually distinct from regular bullets.

Examples from existing skills:

```markdown
> **IRON LAW:** NO CODE PUSHED WITHOUT KERNEL TESTS. Every fix MUST include tests that fail against pre-fix code and pass against fixed code.

> **IRON LAW (TDD):** NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST. Write the test, watch it fail, write the minimal fix, watch it pass. In that order.
```

When adding a 5th IRON LAW, STOP. Either demote one of the existing four
to a regular rule, or put the new rule in the Rules at a glance list.

## Rules at a glance

A 10-item numbered list near the top of a workflow skill that gives the
agent a scannable priority list before the full body. Used in
`drupal-contribute-fix` and `skill-maintainer`.

```markdown
## Rules at a glance

Read before every session. Details for each rule live further down.

1. **<Short rule name>.** <One sentence + optional pointer to deeper section.>
2. **<Short rule name>.** <Detail.>
...
10. **<Short rule name>.** <Detail.>
```

Rules:

- ≤10 items, numbered.
- Each item bold lead-in + sentence of detail.
- Reference the deeper section when one exists: `(Rationalization Prevention #4)`, `(Testing Step 3)`, `(see Before You Begin Q7)`.
- Add here when a rule is critical enough that the agent should see it
  before reading the full file body.

## Gotchas

The "highest-value content in many skills" per the agentskills.io best
practices. Environment-specific facts that defy reasonable assumptions.

```markdown
## Gotchas

Environment-specific traps. Most of these have burned us at least once.

- **<Short name of the trap>.** <Detail of what the trap is and the correct
  behavior.> <Optional incident reference: (#NNNNNN)>
- **<Next trap>.** <Detail.>
```

Rules:

- Bullet list, bold lead-in.
- Each entry is a CONCRETE environment fact, not general advice.
- "Handle errors appropriately" is NOT a gotcha. "The `/health` endpoint
  returns 200 even if the DB is down" IS a gotcha.
- Reference the incident that caused the rule where one exists. Keep the
  reference short: `(#NNNNNN)`, not a story.
- Keep gotchas in SKILL.md, not a reference file. The agent needs to see
  them BEFORE encountering the situation, and reference files only load
  on demand.
- Placement: right after the IRON LAWs / Rules at a glance, BEFORE
  `Before You Begin` or any procedural sections.

Test for whether a rule belongs in Gotchas:

> Would a competent agent with general knowledge of the domain get this
> wrong without being told explicitly?

If yes, it's a gotcha. If no, it's not — it belongs in general procedure,
or it doesn't need to be in the skill at all.

## Rationalization Prevention table

Two-column table: quoted thought → concrete reality check. Used when the
rule is a correction to a common agent rationalization (shortcut
justifications, "small fix no test needed", etc.).

```markdown
### Rationalization Prevention

| Thought | Reality |
|---------|---------|
| "<What the agent might think>" | <Concrete reality check. Reference incident if applicable.> |
| "<Next thought>" | <Reality check.> |
```

Rules:

- Placement: after IRON LAWs, before or alongside Gotchas.
- First column is a QUOTED thought, not a statement. Format: `"thought..."`.
- Second column is a plain imperative correction. Reference incident
  where applicable.
- Add a row when you catch yourself or an agent making a specific
  rationalization the skill doesn't already cover.
- This is different from Gotchas: Gotchas are environment facts;
  rationalizations are thinking failures.

Example rows from existing skills:

```markdown
| "This is just a small fix, no test needed" | Every fix needs a test. Small fixes break in surprising ways. |
| "The proper implementation is ~N lines, this 3-line shortcut is good enough" | Write the proper version before calling it too long. #3580690: the walker was rationalized as "about 50 lines with two helpers"; actually 20 lines with one. |
```

## Before You Begin questions

A numbered list of pre-work checks at the top of the procedural section.
Used in `drupal-issue`, `drupal-contribute-fix`, `drupal-issue-review`.

```markdown
## Before You Begin

Before <action>, answer these questions internally:

1. <Yes/no question about state or knowledge>?
2. <Next question>?
...
N. <Final question>?

If any answer is "no," <what to do to resolve it>.
```

Rules:

- Ordered list, questions phrased as yes/no or "Have I done X?".
- Each question is a hard pre-work gate. If the answer is no, the agent
  should resolve it before proceeding.
- Cheap questions first (issue state), expensive questions later (grep
  the source to verify a claim).
- Reference the incident that led to each hard gate where one exists.
- The final instruction should say what to do when a check fails.

## References section (with when-to-load triggers)

Mandatory format for reference lists per the agentskills.io spec.

```markdown
## References

Load on demand, not by default. Each entry is "open when X":

- `references/<file>.md` — open when <specific trigger condition>.
- `references/<file>.md` — open when <trigger>.
```

Rules:

- Each entry MUST have a trigger phrase: "open when X", "load when Y",
  "fetch when Z".
- Never use generic "see references/ for details".
- Order by likely frequency (most-triggered first).
- Includes agents/, modes/, examples/ as well as references/ — anything
  not loaded by default.

Bad:

```markdown
## References

- `references/api-errors.md` - API error handling
- `references/config.md` - Configuration reference
```

Good:

```markdown
## References

- `references/api-errors.md` — open when the API returns a non-200 status code.
- `references/config.md` — open when the user asks to reconfigure an existing setup.
```

## Incident reference format

When citing an incident:

- Short form in body text: `(#NNNNNN)` or `(see #NNNNNN)`.
- When the incident caused a rule's existence: `(Gate exists because of #NNNNNN: short context.)`.
- Never: paragraph-length stories. Those belong in git commit messages
  or a separate incident log.

## Handoffs table

For skills that chain to other skills (orchestrators, pipeline steps).

```markdown
## Handoffs

| When | Skill | Purpose |
|------|-------|---------|
| <Trigger condition> | <`/skill-name`> | <One-line description> |
```

Alternative: "Companion Skills (Auto-Invoked)" if handoffs are automatic,
or "Called From" if the skill is terminal and only documents who invokes
it. Pick the heading that matches the actual flow direction.

## Frontmatter (workspace house style)

```yaml
---
name: skill-name
description: >
  <What the skill does and when to use it. Multi-line folded style. Include
  specific keywords the agent will match against user requests: "update X",
  "refactor Y", "add a Z".>
license: GPL-2.0-or-later
metadata:
  author: ajv009
  version: "1.0.0"
---
```

Bump `metadata.version` when you make a non-trivial change (new section,
refactor pass, rule additions). Skip the bump for typos.
