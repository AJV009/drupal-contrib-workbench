---
name: skill-maintainer
description: >
  Update, refactor, audit, or create Claude Code skills in this workspace.
  Use when the user says "update the X skill", "add a gotcha to Y",
  "refactor skill Z", "create a new skill for W", "my skills are getting
  bloated", "audit my skills against the spec", or when a session has
  produced rules, patterns, or incidents that should be codified into
  existing skills. Covers agentskills.io spec compliance (name,
  description, line limits), progressive disclosure, Gotchas sections,
  Rationalization Prevention tables, file layout conventions, and the
  bloat patterns learned from maintaining this workspace's Drupal skills.
license: GPL-2.0-or-later
metadata:
  author: ajv009
  version: "1.0.0"
---

# skill-maintainer

Meta-skill for curating the skills in `.claude/skills/`. Use it when rules
from the current session should be codified, when a skill has drifted
into bloat, when a new skill is needed, or when you want a spec-compliance
audit.

> **IRON LAW:** NEVER INVENT RULES OR FACTS. A skill is only useful if its content is grounded in real experience. Generic "best practices" from LLM training are noise. Every rule you add MUST trace to a concrete incident, a spec requirement, an observable pattern in the current codebase, or explicit user direction.

> **IRON LAW:** PRESERVE LOAD-BEARING CONTENT. Before deleting anything, verify it is not the only place a rule is stated. Duplication is OK to cut. The only canonical location is not.

> **IRON LAW:** VALIDATE AFTER EVERY NON-TRIVIAL EDIT. Run `scripts/validate.py` and confirm name/description/lines are spec-compliant. Do NOT claim the skill is fixed until validation passes.

## When to invoke

Trigger on any of these:

- User says "update the {skill-name} skill" / "add a gotcha to Y" / "refactor skill Z" / "clean up skill W"
- User says "create a new skill for X"
- User says "my skills are getting bloated" / "my skills grew too big" / "audit my skills against the spec"
- User says "codify this session's findings into the skills" / "pull learnings from this session into the right skill"
- After a session that produced a concrete incident, rule, pattern, or gotcha that belongs in one of the existing skills but hasn't been written down yet
- User asks for a spec-compliance check ("run the validator", "do my skills pass the spec rules")

Do NOT invoke for:
- Editing non-skill files (skill-maintainer only touches `.claude/skills/` and `.claude/agents/`)
- Trivial typo fixes (just use Edit directly)
- Discussions about skill design that don't involve touching files

## Rules at a glance

1. **Start from real experience.** Every rule added must trace to an incident, a spec requirement, or a verifiable pattern. No generic "best practices" from training knowledge.
2. **Read the full current state first.** `cat` the target SKILL.md end to end. Check `git log` and `git diff` for recent intentional changes you must not revert.
3. **Surgical edits over rewrites.** Prefer `Edit` over `Write`. Quote exact `old_string` from a recent `Read` — do not edit from memory.
4. **Spec compliance is non-negotiable.** Hard rules: `name` ≤64 chars lowercase + hyphens, matches directory. `description` ≤1024 chars. SKILL.md ≤500 lines (spec recommendation, treat as target).
5. **Progressive disclosure.** If content is >30 lines of reference material, it belongs in `references/` with a one-line pointer in SKILL.md. Tell the agent *when* to load each reference (`open X when Y`), not just that it exists.
6. **Gotchas go in `## Gotchas`.** Environment-specific facts that defy reasonable assumptions. NOT general best practices. NOT things a competent agent would get right without being told.
7. **Rules go in `## Rules at a glance` or IRON LAWs.** Keep IRON LAWs to 1-4 per skill. Rules TL;DR to ≤10 numbered items.
8. **Rationalizations go in `### Rationalization Prevention`.** Quoted thought → concrete reality check. Reference the concrete incident when there is one.
9. **Historical justifications are parentheticals, not paragraphs.** `(Gate exists because of #NNNNNN: code-only push bounced.)` not a three-sentence story.
10. **Validate + report.** After every change, run the validator, then report files touched and line delta. Never commit without explicit user approval.

## Gotchas

- **Adding content always feels easier than restructuring.** When adding a new gotcha, rule, or section, check if the rule already exists somewhere else in the skill FIRST. If it does, consolidate (move to the canonical section, remove from the original location). Do not duplicate. Duplicates are how skills grew bloated in the first place.
- **Line counts are not quality.** A 490-line skill with 10 coherent sections beats a 200-line skill where every rule is cryptic. Don't trim to hit a number; trim to remove noise. Most trims come from consolidating duplication, not shortening individual rules.
- **"Just add this rule" is how skills go crazy.** The Phase 1-4 refactor of this workspace cut 24% of total workflow-skill lines while ADDING new content (Gotchas sections, Rules at a glance). The win came from consolidating scattered mentions, not from cutting rule content.
- **Iron laws should be rare.** When everything shouts `MANDATORY`/`CRITICAL`/`NON-NEGOTIABLE`, nothing prioritizes. Keep the 4 genuine IRON LAWs at the top; demote redundant "MANDATORY" section markers to plain text. The rules are unchanged; only the caps-lock volume drops.
- **Progressive disclosure requires trigger phrases.** `see references/foo.md for details` is worse than `open references/foo.md when the CI pipeline fails`. The agentskills.io spec is explicit: tell the agent *when* to load each file, not just that the file exists.
- **YAML frontmatter folded vs literal.** Multi-line descriptions use `description: >` (folded, newlines become spaces). `description: |` (literal, preserves newlines) is wrong for descriptions. Most of this workspace's skills use folded form. Match existing style.
- **File reference depth: one level from SKILL.md.** `references/foo.md` is fine. `references/sub/foo.md` is generally discouraged unless the taxonomy is load-bearing (like `drupal-coding-standards/assets/standards/php/coding.md` where the category is a conceptual axis). Don't nest reference chains.
- **Never edit CLAUDE.md as part of a skill update** without explicit user instruction. CLAUDE.md is the workspace-wide preamble and its content affects every session. Skill updates stay inside `.claude/skills/` and `.claude/agents/`.
- **Uncommitted changes may be intentional.** Always check `git status` and `git diff` before editing. This workspace leaves skills uncommitted for extended refinement; overwriting recent intentional additions is the most common session-breaking mistake.
- **The spec's 500-line recommendation is a recommendation.** Tool reference skills like `agent-browser` legitimately exceed it (CLI surface area). Workflow skills should stay under. Know the category before cutting for line count alone.

## Process

### Step 1: Clarify the scope

Before touching any file, confirm:

- **Which skill(s)?** If the user says "update my skills" without naming one, either inspect the current session for context (what did they just work on?) or ask. Never guess.
- **What kind of change?** New rule/gotcha? Bloat cleanup? Spec compliance pass? Full refactor? New skill from scratch?
- **Why?** Session incident? Spec violation? User's explicit complaint about bloat? The *why* determines which section the change belongs in.

If the user's request is ambiguous, present a short scope proposal and wait for confirmation before editing.

### Step 2: Read the full current state

For each target skill:

```bash
# Full contents
cat .claude/skills/{name}/SKILL.md

# What files exist in the skill
ls -R .claude/skills/{name}/

# Recent intentional changes (may be uncommitted)
git status .claude/skills/{name}/
git diff HEAD .claude/skills/{name}/
git log --oneline -10 -- .claude/skills/{name}/
```

Read SKILL.md end to end, not just the relevant section. Refactor decisions depend on the full structure. Do NOT edit from memory — even if you "just updated" the skill in the previous session.

### Step 3: Plan the change

For small additions (one gotcha, one rationalization row, one new bullet), just do it and summarize after.

For anything larger (new section, refactor pass, multi-file change, new skill from scratch), present a surgical plan with:

- Which files to touch
- Which sections to add / remove / rewrite
- Estimated line delta
- Any duplication you found that you'll consolidate
- Any content you'll relocate to `references/`

Wait for user approval before mass edits. This is the single most important step in avoiding "the skills got worse after an agent touched them" situations.

### Step 4: Make the edits

Use `Edit` tool with exact `old_string` from a recent `Read`. Preserve indentation. Prefer multiple small edits over one large rewrite — each Edit is auditable.

When adding rules:

| New content type | Goes in |
|---|---|
| New gotcha | `## Gotchas` (consolidate from scattered mentions, don't duplicate) |
| New rationalization | `### Rationalization Prevention` table row |
| New hard rule | `## Rules at a glance` numbered list (keep ≤10) |
| New iron law | IRON LAW block at top (keep ≤4) |
| New procedural step | The relevant existing procedure section, not a new top-level section |
| New reference material (>30 lines) | `references/{name}.md` + one-line pointer in SKILL.md |
| New incident reference | Parenthetical `(#NNNNNN)` at the end of the relevant rule, not a full story |

When removing content:

- Grep for a distinctive phrase to confirm the rule is stated elsewhere.
- If it's the only location, either keep it or move it to a reference file. Do NOT delete the rule itself, only the duplication.
- Historical narration can collapse to `(Reason: #NNNNNN)` style.

### Step 5: Validate

Run the validator:

```bash
python3 .claude/skills/skill-maintainer/scripts/validate.py
```

It checks every skill in `.claude/skills/` for:

- Frontmatter parses as YAML
- `name` format valid (lowercase, hyphens, matches directory, ≤64 chars)
- `description` 1-1024 chars, non-empty
- SKILL.md ≤500 lines (warning for workflow skills, accepted for tool reference skills)
- Other frontmatter fields well-formed if present

Fix any errors and re-run. If a warning fires (e.g., 505 lines), either trim to clear it or explicitly accept it for tool-reference skills.

### Step 6: Report

Summarize:

- Files touched (SKILL.md, references/, scripts/, etc.)
- Line delta per file (before → after)
- New sections added, sections consolidated, sections removed
- Validator output
- What's preserved that might look unusual (for uncommitted intentional changes)

Do NOT commit. The user commits when they're ready. Skill refactors often sit uncommitted for multiple sessions while they're refined by real use.

## References

Load on demand, not by default. Each entry is "open when X":

- `references/spec.md` — open when checking frontmatter field rules, line limits, or file-layout conventions. Mirrors the agentskills.io spec.
- `references/best-practices.md` — open when deciding whether a rule belongs in the skill body or a reference file, or when choosing between prescriptive vs flexible instruction styles.
- `references/patterns.md` — open when adding a new IRON LAW, Rules at a glance item, Rationalization row, Gotchas entry, or Before You Begin question. Contains exact formatting templates.
- `references/bloat-patterns.md` — open when asked to clean up, refactor, or audit a bloated skill. Contains the taxonomy of bloat sources identified during the Phase 1-4 cleanup of this workspace.
- `references/workflow-skill-conventions.md` — open when touching the Drupal workflow skills in this workspace (`drupal-contribute-fix`, `drupal-issue`, `drupal-issue-review`, `drupal-issue-comment`). Documents the shared pipeline conventions and which rules live in CLAUDE.md vs individual skills.
- `scripts/validate.py` — run after every change.
- `examples/session-refactor-walkthrough.md` — open when doing a multi-phase cleanup pass and you want a template for the work breakdown (the Phases 1-4 approach used on this workspace).

## Handoffs

This skill is self-contained. After a skill update, there is no auto-invoked
next skill. Present the validator output + file summary and wait for the
user's next instruction (commit, continue refining, move on).
