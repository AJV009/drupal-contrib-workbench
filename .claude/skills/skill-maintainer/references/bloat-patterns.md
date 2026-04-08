# Bloat Patterns (taxonomy from the Phase 1-4 cleanup)

Observed sources of skill bloat in `.claude/skills/` during the Phase 1-4
refactor. Open this file when auditing a skill that has grown too big,
or when you catch a skill drifting toward the 500-line limit.

## Diagnostic: how to know a skill is bloated

Warning signs:

- SKILL.md is >500 lines.
- Multiple sections cover adjacent topics (e.g., Test Planning + Test
  Coverage Gate + Test Validation as three peer sections instead of one
  parent with sub-steps).
- Iron laws and MANDATORY markers appear more than 5-6 times in one file.
- The same rule is stated in two different sections with slightly
  different wording.
- A "Complete Workflow" summary + a "What This Skill Does" summary +
  an ASCII diagram all describe the same 5-step flow.
- Reference lists say "see references/foo.md for details" without a
  trigger phrase.
- Full bash command blocks (>10 lines) that duplicate what's in `modes/`
  or `scripts/`.
- Historical justifications written as paragraphs: "This gate was added
  after issue #N where Y happened. That round-trip wasted time for..."
- "This is especially important for..." callouts that repeat a rule
  already stated above.

If you see three or more of these, it's time for a cleanup pass.

## Taxonomy of bloat sources

### 1. Duplication across files

Same rule stated in multiple skills. Common examples:

- "Hands-Free Operation" section repeated in `drupal-issue`,
  `drupal-issue-review`, `drupal-contribute-fix`. Consolidated to
  `CLAUDE.md` during Phase 1, with one-line references in each skill.
- "Progress Tracking" lazy-task rule repeated in three skills. Same
  consolidation.
- Humility rules ("no 'happy to change' hedges") restated in
  `drupal-contribute-fix` Step 6 that already lived in
  `drupal-issue-comment`. Consolidated to a 3-item reference with a
  pointer to the canonical location.
- Agent dispatch instructions restated in every skill that dispatches an
  agent. Consolidated to one canonical dispatch pattern per agent.

**Fix**: pick a canonical location (usually CLAUDE.md or the most
specific skill), remove from other files, replace with a one-line
reference.

### 2. Duplication within a single file

Same rule in two sections of the same skill:

- Test enforcement in `drupal-contribute-fix` was spread across IRON LAW
  block, Test Planning from Diff, TEST COVERAGE GATE, Test Validation,
  Pre-Push Quality Gate Step 2. Five adjacent sections restating
  "kernel tests required". Consolidated to one `## Testing` parent with
  three numbered steps (Plan, TDD, Validate).
- "Complete Workflow" (7 numbered steps) + "What This Skill Does" (8
  numbered items) + "Workflow Hygiene" (2-line rule) in the same file
  were three summaries of the same thing. Kept one, deleted the others.

**Fix**: identify which location is most useful to the agent, move all
content there, delete the rest.

### 3. Historical justifications

The skill tells a story about when and why a rule was added:

> "This gate was added after issue #3542457 where code fixes were pushed
> without tests and jibran had to send the MR back to 'Needs work' for
> missing test coverage. That round-trip wasted time for everyone."

The rule is useful; the story is not. Collapse to:

> "(Gate exists because of #3542457: code-only push bounced as Needs Work.)"

The agent still sees WHY the rule exists, enough to judge edge cases.
The full story belongs in git commit messages or an incident log.

**Fix**: replace narrative paragraphs with parenthetical incident
references. Usually saves 5-15 lines per instance.

### 4. Excessive shouting

`drupal-contribute-fix` had 14 instances of
`MANDATORY` / `CRITICAL` / `NON-NEGOTIABLE` / `NEVER` / `IRON LAW` when
the session started. The genuine iron laws are the 4 at the top of the
file and the 1 at the Push Gate. The other 9 were redundant section
markers: `Pre-Push Quality Gate (MANDATORY)`, `Step 3: Validate tests (MANDATORY)`, etc. All these rules were already enforced by the top-of-file IRON LAWs and Rules at a glance list.

**Fix**: keep iron laws rare (1-4 at the top, 0-1 at the Push Gate).
Demote redundant `(MANDATORY)` and `(CRITICAL)` section tags to plain
text. The rules don't change; the caps-lock volume drops. When
everything shouts, nothing prioritizes.

### 5. Full command blocks that belong in modes/

`drupal-contribute-fix` had full bash examples for preflight, package,
test, and reroll modes in the main SKILL.md body, even though `modes/preflight.md`, `modes/package.md`, etc. existed with the same examples. ~80 lines of duplicate command reference in the loaded SKILL.md.

**Fix**: replace the inline blocks with a table pointing to the mode
files.

### 6. ASCII flow diagrams that restate section headers

`drupal-issue-review` had a 30-line box-and-arrow diagram showing `Read
Issue → Scaffold DDEV → Install Modules → Reproduce → Comment`. The
skill already had `## Step 1: Read the Issue`, `## Step 2: Scaffold the
DDEV Environment`, etc. as explicit section headings. The diagram added
nothing the headings didn't already show.

**Fix**: delete the diagram. If a diagram is useful, make sure it shows
something the section headings don't.

### 7. Generic bullet lists without triggers

Reference lists, gotchas, and pattern catalogs that are just bullet
points without context:

Bad:

```markdown
## References

- `references/api-errors.md` - API error handling
- `references/config.md` - Configuration reference
```

The agent sees these but has no reason to open them at any specific
moment.

**Fix**: add a trigger phrase to each entry. "Open when X fails". "Load
when the user asks for Y". See
`references/patterns.md#references-section-with-when-to-load-triggers`.

### 8. Menu of equal options (should be a default)

When a skill presents multiple tools as equally valid:

Bad: "You can use pypdf, pdfplumber, PyMuPDF, or pdf2image..."

**Fix**: pick a default. Mention alternatives as escape hatches only.
"Use pdfplumber for text extraction. For scanned PDFs requiring OCR, use
pdf2image with pytesseract instead."

### 9. "Called From" + "Handoffs" tables restating the same graph

Skills that document both "who calls me" AND "who I call" from opposite
directions, describing the same edges twice.

**Fix**: pick ONE direction (usually Handoffs for orchestrators,
Called From for terminal skills). Use the other format only if it
actually adds information.

### 10. Self-contained defensive fallbacks for non-existent failure modes

`drupal-contribute-fix` had a 15-line "SSH Remote Verification" section
describing how to check and fix the git remote. The only actionable
content was "use git.drupal.org not git.drupalcode.org". The rest was
narration about HTTPS remotes failing in non-interactive contexts.

**Fix**: collapse to 3 lines. Move the actionable rule to Gotchas.

### 11. Post-push user-menu narration

Hardcoded menu templates like:

```markdown
What would you like to do next?
1. Monitor pipeline - Watch GitLab CI and report results
2. Post comment - Open the issue page to post the draft comment
3. Clean up - Stop DDEV project (keeps files)
4. Next issue - Start work on a different issue
5. Done for now - Keep everything as-is
```

The agent can construct a menu from context. Hardcoding it wastes lines
for zero value.

**Fix**: replace with a short prose line. "Offer: monitor pipeline / post
comment / clean up / next issue / done."

### 12. Example walkthroughs at the bottom

End-of-file "Examples" sections showing 5 hypothetical invocations:

```markdown
/drupal-issue 3561693
→ Reads issue, sees it's "Needs work"
→ Classifies as: Reproduce a bug
→ Delegates to /drupal-issue-review
```

Useful for humans reading the skill as documentation; not useful for an
agent executing the skill.

**Fix**: move to `examples/classification-walkthroughs.md` with a
one-line pointer in SKILL.md.

### 13. Preamble restated from frontmatter

The body re-introduces the skill with the same description that's
already in the YAML frontmatter. The frontmatter description is the only
part the agent sees at discovery time; restating it in the body is
redundant.

**Fix**: if the body's intro says the same thing as the frontmatter
description, delete the body intro.

## Approach to a cleanup pass

Based on the Phase 1-4 session in this workspace. Rough process:

1. **Audit.** Read all target skills end to end. Measure: line counts,
   shouting marker count, section count, cross-file duplication.
2. **Identify bloat by pattern.** Use this taxonomy. Tag each bloat
   instance with its type.
3. **Plan by phase.** Don't try to fix everything at once:
   - **Phase 1**: dedup (pull common rules to CLAUDE.md, dedupe across
     files, collapse historical narration). Low risk, biggest line wins.
   - **Phase 2**: restructure (consolidate scattered sections into one
     parent, extract verbose reference content to `references/`, add
     Rules at a glance TL;DR for navigation). Medium risk.
   - **Phase 3**: compress judgment calls (tighten iron law count,
     extract example walkthroughs, compact category prose into tables).
     Higher risk.
   - **Phase 4**: spec-compliance polish (Gotchas sections, when-to-load
     triggers, validator pass).
4. **Present the plan.** Before any mass edits, show the user the
   surgical plan with estimated line deltas. Wait for approval.
5. **Execute phase by phase.** Validate after each phase. Report deltas.
6. **Preserve intentional additions.** Check `git status` and `git diff`
   before every session — uncommitted changes may be deliberate.

## Outcomes from the workspace's Phase 1-4 session

Baseline → final (workflow skills only, loaded in every session):

| File | Session start | Final | Δ |
|---|---|---|---|
| `drupal-contribute-fix` | 738 | 490 | −248 |
| `drupal-issue` | 535 | 417 | −118 |
| `drupal-issue-review` | 463 | 350 | −113 |
| `drupal-issue-comment` | 337 | 310 | −27 |
| **Total** | **2206** | **1677** | **−529 (−24%)** |

Additional outcomes:

- All 4 workflow skills under the 500-line spec recommendation.
- Shouting markers in `drupal-contribute-fix` cut from 14 to 7.
- 3 new reference/example files extracted out of default session load
  (`ci-parity.md`, `static-review-checklist.md`,
  `classification-walkthroughs.md`).
- Explicit `## Gotchas` sections added to all 4 workflow skills.
- References lists rewritten with when-to-load triggers.
- Test enforcement consolidated from 6 scattered sections to one
  coherent parent.

Every rule from before the refactor was preserved. The 24% cut came
almost entirely from consolidating duplication and removing
narration — not from removing rules.
