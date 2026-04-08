# Skill Writing Best Practices (mirror + workspace additions)

Source: https://agentskills.io/skill-creation/best-practices (fetched 2026-04)

## Core principle: start from real expertise

Generic LLM training knowledge produces generic skills ("handle errors
appropriately", "follow best practices for authentication"). Effective
skills are grounded in real experience: the specific API patterns, edge
cases, and project conventions that a competent agent would NOT get
right without being told.

Two ways to source real expertise:

1. **Extract from a hands-on task.** Complete a real task in conversation
   with an agent, providing context and corrections. Then extract the
   reusable pattern. Pay attention to:
   - Steps that worked (the sequence that led to success)
   - Corrections you made ("use library X instead of Y", "check for edge case Z")
   - Input/output formats (what the data looked like going in/out)
   - Context you provided (project-specific facts the agent didn't know)

2. **Synthesize from existing project artifacts.** Feed in runbooks,
   incident reports, code review comments, commit history, and failure
   cases. A data-pipeline skill synthesized from YOUR team's actual
   incident reports outperforms one generated from "data engineering
   best practices" articles.

## Refine with real execution

The first draft of a skill usually needs refinement. Run it against real
tasks, then feed the results back. Ask:

- What triggered false positives?
- What was missed?
- What could be cut?
- Did the agent waste time on unproductive steps? (Usually means vague
  instructions or too many options without a clear default.)

Even a single execute-then-revise pass noticeably improves quality.

## Spending context wisely

Once a skill activates, the full SKILL.md body loads into the agent's
context window alongside conversation history, system context, and other
active skills. Every token competes for attention.

### Add what the agent lacks, omit what it knows

Focus on what the agent WOULDN'T know without your skill: project-specific
conventions, domain-specific procedures, non-obvious edge cases, the
particular tools or APIs to use. Do NOT explain what a PDF is, how HTTP
works, or what a database migration does.

Bad (the agent already knows this):

```markdown
## Extract PDF text

PDF (Portable Document Format) files are a common file format that
contains text, images, and other content. To extract text from a PDF,
you'll need to use a library.
```

Good (jumps to what the agent wouldn't know):

```markdown
## Extract PDF text

Use pdfplumber for text extraction. For scanned documents, fall back
to pdf2image with pytesseract.
```

Ask yourself about each piece of content: "Would the agent get this
wrong without this instruction?" If no, cut it. If unsure, test it.

### Design coherent units

Deciding what a skill should cover is like deciding what a function
should do: encapsulate a coherent unit of work that composes with other
skills.

- Too narrow → multiple skills have to load for one task, risking
  overhead and conflicting instructions.
- Too broad → hard to activate precisely; description becomes vague.

Example: "query a database and format the results" is one coherent unit.
"Query a database, format results, AND cover database administration"
is trying to do too much.

### Aim for moderate detail

Overly comprehensive skills hurt more than they help. Agents struggle to
extract what's relevant and may pursue unproductive paths triggered by
instructions that don't apply. Concise stepwise guidance with a working
example outperforms exhaustive documentation.

When you find yourself covering every edge case, consider whether most
are better handled by the agent's own judgment.

### Structure large skills with progressive disclosure

Keep SKILL.md under 500 lines and ~5,000 tokens — just the core
instructions the agent needs on every run. When a skill legitimately
needs more content, move detailed reference material to
`references/{file}.md`.

**The key is telling the agent WHEN to load each reference.** Compare:

Bad: `See references/api-errors.md for details.`

Good: `Read references/api-errors.md if the API returns a non-200 status code.`

The good version lets the agent load context on demand. The bad version
either loads eagerly (defeating the point of the reference file) or
never loads at all (defeating the point of writing it).

## Calibrating control

Not every part of a skill needs the same level of prescriptiveness.

### Match specificity to fragility

**Give the agent freedom** when multiple approaches are valid and the
task tolerates variation. Explain WHY instead of HOW — an agent that
understands the purpose makes better context-dependent decisions.

```markdown
## Code review process

1. Check all database queries for SQL injection (use parameterized queries)
2. Verify authentication checks on every endpoint
3. Look for race conditions in concurrent code paths
4. Confirm error messages don't leak internal details
```

**Be prescriptive** when operations are fragile, consistency matters, or
a specific sequence must be followed:

```markdown
## Database migration

Run exactly this sequence:

    python scripts/migrate.py --verify --backup

Do not modify the command or add additional flags.
```

Most skills have a mix. Calibrate each part independently.

### Provide defaults, not menus

When multiple tools could work, pick a default and mention alternatives
briefly. Do NOT present options as equal.

Bad: `You can use pypdf, pdfplumber, PyMuPDF, or pdf2image...`

Good:

```markdown
Use pdfplumber for text extraction. For scanned PDFs requiring OCR, use
pdf2image with pytesseract instead.
```

### Favor procedures over declarations

A skill should teach HOW to approach a class of problems, not WHAT to
produce for a specific instance.

Bad (only useful for this exact task):

```markdown
Join the `orders` table to `customers` on `customer_id`, filter where
`region = 'EMEA'`, and sum the `amount` column.
```

Good (works for any analytical query):

```markdown
1. Read the schema from references/schema.yaml to find relevant tables
2. Join tables using the `_id` foreign key convention
3. Apply filters from the user's request as WHERE clauses
4. Aggregate numeric columns and format as a markdown table
```

Skills can still include specific details (templates, constraints,
tool-specific instructions). The APPROACH should generalize; the
individual details can be specific.

## Patterns for effective instructions

### Gotchas sections (highest-value content in many skills)

A list of environment-specific facts that defy reasonable assumptions.
These are concrete corrections to mistakes the agent will make without
being told otherwise. NOT general advice.

Bad (general advice):

```markdown
## Gotchas

- Handle errors appropriately
- Consider edge cases
- Follow best practices
```

Good (concrete environment facts):

```markdown
## Gotchas

- The `users` table uses soft deletes. Queries must include
  `WHERE deleted_at IS NULL` or results include deactivated accounts.
- The user ID is `user_id` in the database, `uid` in the auth service,
  and `accountId` in the billing API. All three refer to the same value.
- The `/health` endpoint returns 200 as long as the web server is
  running, even if the database connection is down. Use `/ready` to
  check full service health.
```

Keep gotchas in SKILL.md (not a reference file) so the agent reads them
BEFORE encountering the situation. A separate reference file works if
you tell the agent when to load it, but for non-obvious issues the
agent may not recognize the trigger.

**When an agent makes a mistake you correct, add the correction to
Gotchas.** This is the most direct way to improve a skill iteratively.

### Templates for output format

When you need the agent to produce output in a specific format, provide
a template. More reliable than describing the format in prose, because
agents pattern-match well against concrete structures.

Short templates live inline in SKILL.md. Longer templates go in
`assets/` and load on demand.

### Checklists for multi-step workflows

An explicit checklist helps the agent track progress and avoid skipping
steps, especially when steps have dependencies or validation gates.

```markdown
## Form processing workflow

Progress:
- [ ] Step 1: Analyze the form (run `scripts/analyze_form.py`)
- [ ] Step 2: Create field mapping (edit `fields.json`)
- [ ] Step 3: Validate mapping (run `scripts/validate_fields.py`)
- [ ] Step 4: Fill the form (run `scripts/fill_form.py`)
- [ ] Step 5: Verify output (run `scripts/verify_output.py`)
```

### Validation loops

Instruct the agent to validate its own work before moving on. Pattern:
do the work → run a validator → fix issues → repeat until passes.

```markdown
## Editing workflow

1. Make your edits
2. Run validation: `python scripts/validate.py output/`
3. If validation fails:
   - Review the error message
   - Fix the issues
   - Run validation again
4. Only proceed when validation passes
```

### Plan-validate-execute

For batch or destructive operations, have the agent create a structured
plan, validate it against a source of truth, and only then execute.

```markdown
## PDF form filling

1. Extract form fields: `python scripts/analyze_form.py input.pdf` → `form_fields.json`
2. Create `field_values.json` mapping each field to its intended value
3. Validate: `python scripts/validate_fields.py form_fields.json field_values.json`
4. If validation fails, revise `field_values.json` and re-validate
5. Fill the form: `python scripts/fill_form.py input.pdf field_values.json output.pdf`
```

The key is step 3: a validator that checks the plan against a source of
truth. Errors like `Field 'signature_date' not found — available: customer_name, order_total, signature_date_signed` give the agent enough information to self-correct.

### Bundling reusable scripts

If the agent is independently reinventing the same logic each run
(building charts, parsing a format, validating output), write the
logic once and bundle it in `scripts/`. One tested script beats ten
improvised implementations.

## Workspace additions (lessons from maintaining this repo)

### Rationalization Prevention tables

This workspace's convention: a two-column table of quoted
rationalizations ("what the agent might think") mapped to the reality
check. Concrete incident references where they exist.

```markdown
### Rationalization Prevention

| Thought | Reality |
|---|---|
| "This is just a small fix, no test needed" | Every fix needs a test. Small fixes break in surprising ways. |
| "The proper implementation is ~N lines, this 3-line shortcut is good enough" | Write the proper version before calling it too long. #3580690: the walker was rationalized as "about 50 lines with two helpers"; actually 20 lines with one. |
```

Add a row when you see yourself (or an agent) fall into a rationalization
the skill doesn't already cover.

### Rules at a glance (workspace convention)

A 10-item numbered list near the top of a workflow skill that summarizes
the non-negotiables, with pointers to the deeper sections. Used in
`drupal-contribute-fix` and `skill-maintainer`. Helps the agent
prioritize before reading the full body.

```markdown
## Rules at a glance

1. **Preflight first.** Run `preflight` mode before editing any contrib/core code.
2. **Read called APIs before calling them** in scanning/validation/transformation code.
...
```

Keep to ≤10 items. More and the list loses its "scan before reading"
value.

### Historical justifications: parentheticals, not paragraphs

When a rule exists because of a specific incident, reference the incident
as a parenthetical, not a story:

Bad: `This gate was added after issue #3542457 where code fixes were pushed without tests and jibran had to send the MR back to "Needs work" for missing test coverage. That round-trip wasted time for everyone.`

Good: `(Gate exists because of #3542457: code-only push bounced as Needs Work.)`

The story belongs in the incident tracker or commit message. The skill
body only needs enough to tell the agent WHY the rule exists so it can
judge edge cases.
