# Drupal Skills Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply Anthropic's superpowers patterns (progressive disclosure, explicit handoffs, announcements, iron laws, question gates, status reporting, review loops, agent prompt templates, TaskCreate enforcement) to all 7 Drupal skills.

**Architecture:** Define shared patterns once, then apply per skill. Content-heavy skills get progressive disclosure first (move bulk to references/). Workflow skills get governance patterns (iron laws, handoffs, question gates). Agent prompt templates and CLAUDE.md updates come last.

**Skill directory:** `/home/alphons/project/freelygive/drupal/CONTRIB_WORKBENCH/.claude/skills/`

---

## Shared Patterns (Reference for All Tasks)

Every restructured SKILL.md must follow these conventions:

### Frontmatter
```yaml
---
name: skill-name
description: >
  [What it does AND when to trigger it. This is the ONLY thing loaded
  before the skill activates. Make it count.]
---
```

### Announcement (Required, first line after frontmatter heading)
```markdown
**Announce at start:** "I'm using the [skill-name] skill to [purpose]."
```

### Iron Laws (where applicable)
Format as a callout block near the top:
```markdown
> **IRON LAW:** [ALL-CAPS RULE STATEMENT]
```

### Self-Exploratory Question Gate (workflow skills)
```markdown
## Before You Begin
Before taking action, answer these questions internally:
1. [Question about context]
2. [Question about prerequisites]
3. [Question about existing work]
If any answer is unclear, read more context before proceeding.
```

### Explicit Handoffs
```markdown
## Handoff
**REQUIRED NEXT SKILL:** `/skill-name` for [purpose].
Invoke via the Skill tool. Do NOT inline the companion skill's behavior.
```

### TaskCreate Integration
```markdown
## Progress Tracking
Create a TaskCreate entry for each major step in this workflow.
Mark in_progress when starting, completed when done.
```

### Progressive Disclosure Structure
```
SKILL.md           (<200 lines) - Navigation, workflow, governance
references/*.md    (unlimited)  - Detailed patterns, examples, tables
agents/*.md        (if needed)  - Subagent dispatch prompt templates
```

---

### Task 1: Progressive disclosure for drupal-dev-patterns

The current SKILL.md is ~450 lines with three full pattern sections (hooks, DI, security). Move each to a reference file. SKILL.md becomes a lean router.

**Files:**
- Modify: `skills/drupal-dev-patterns/SKILL.md` (rewrite to ~80 lines)
- Create: `skills/drupal-dev-patterns/references/hook-patterns.md`
- Create: `skills/drupal-dev-patterns/references/service-di-patterns.md`
- Create: `skills/drupal-dev-patterns/references/security-patterns.md`

- [ ] **Step 1: Read the current SKILL.md**

Read `skills/drupal-dev-patterns/SKILL.md` fully. Identify where each of the three sections starts and ends.

- [ ] **Step 2: Create references directory and extract hook patterns**

Create `skills/drupal-dev-patterns/references/hook-patterns.md` with the FULL content of the "Hook Patterns" section from SKILL.md (everything from the OOP Hooks heading through the Hook Implementation Checklist). Add a title header `# Hook Patterns` at the top.

- [ ] **Step 3: Extract service/DI patterns**

Create `skills/drupal-dev-patterns/references/service-di-patterns.md` with the FULL "Service & Dependency Injection" section. Add title header.

- [ ] **Step 4: Extract security patterns**

Create `skills/drupal-dev-patterns/references/security-patterns.md` with the FULL "Security Patterns" section. Add title header.

- [ ] **Step 5: Rewrite SKILL.md as navigation layer**

Replace SKILL.md with a lean version (~80 lines):

```markdown
---
name: drupal-dev-patterns
description: >
  Hook implementations, service/DI patterns, and security patterns for
  Drupal 10/11. Use when implementing hooks, form alters, event subscribers,
  creating services, working with dependency injection, or reviewing code
  for security issues.
---

# Drupal Development Patterns

**Announce at start:** "I'm using the drupal-dev-patterns skill for [hooks/DI/security] guidance."

> **IRON LAW:** NO `\Drupal::` STATIC CALLS IN SERVICE CLASSES. Use constructor injection.

This skill covers three domains. Load only the reference you need:

## Hook Patterns
OOP hooks with `#[Hook]` attribute (Drupal 11+), legacy bridges, form alters,
entity hooks, theme hooks, event subscribers, install/update hooks.

**Full reference:** `references/hook-patterns.md`

**Quick decision:**
- Drupal 11+? Use `#[Hook]` attribute in a Hook class
- Need Drupal 10 compat? Add `#[LegacyHook]` bridge in .module
- Business logic? Delegate to an injectable service, not the hook class

## Service & Dependency Injection
Service definitions, constructor property promotion, interface design,
plugin DI, common Drupal services table, service name discovery.

**Full reference:** `references/service-di-patterns.md`

**Quick decision:**
- Creating a service? Define in `*.services.yml`, use autowire where possible
- Injecting into a plugin? Implement `ContainerFactoryPluginInterface`
- Finding a service name? Read the module's `*.services.yml` directly

## Security Patterns
SQL injection prevention, XSS protection, access control (route + entity),
CSRF protection, file upload validation, security checklist.

**Full reference:** `references/security-patterns.md`

**Quick decision:**
- Database query? Use Entity API (best) or parameterized queries
- User output? Twig auto-escapes. For PHP: `Html::escape()` or `Xss::filter()`
- Route access? Stack `_permission`, `_entity_access`, custom checkers in routing.yml
```

- [ ] **Step 6: Verify references are complete**

```bash
wc -l skills/drupal-dev-patterns/references/*.md
wc -l skills/drupal-dev-patterns/SKILL.md
# SKILL.md should be <100 lines, references should contain all original content
```

---

### Task 2: Progressive disclosure for drupal-coding-standards

The quick-reference section (~90 lines of tables and code blocks) should move to a reference file. The RT discovery workflow stays in SKILL.md.

**Files:**
- Modify: `skills/drupal-coding-standards/SKILL.md` (trim to ~60 lines)
- Create: `skills/drupal-coding-standards/references/quick-reference.md`

- [ ] **Step 1: Read the current SKILL.md**

Read `skills/drupal-coding-standards/SKILL.md`. Identify the "Quick Reference" section.

- [ ] **Step 2: Extract quick reference to a reference file**

Create `skills/drupal-coding-standards/references/quick-reference.md` with the full Quick Reference content (validation commands, required code patterns, naming conventions, anti-patterns, PHPDoc, module structure).

- [ ] **Step 3: Rewrite SKILL.md**

Keep the frontmatter, add announcement and iron law, keep the RT discovery workflow, replace Quick Reference section with a pointer:

```markdown
**Announce at start:** "I'm using the drupal-coding-standards skill to review [file type] code."

> **IRON LAW:** ALWAYS RUN PHPCS BEFORE COMMITTING. Never skip static analysis.

## Quick Reference
For validation commands, naming conventions, required code patterns, anti-patterns,
and module structure: see `references/quick-reference.md`
```

- [ ] **Step 4: Verify**

```bash
wc -l skills/drupal-coding-standards/SKILL.md  # should be <70 lines
ls skills/drupal-coding-standards/references/quick-reference.md
```

---

### Task 3: Restructure drupal-issue (the router skill)

Add announcement, iron law, self-exploratory question gate, explicit handoffs, TaskCreate enforcement. This skill is already well-structured; it just needs governance patterns.

**Files:**
- Modify: `skills/drupal-issue/SKILL.md`

- [ ] **Step 1: Read the current SKILL.md**

Read `skills/drupal-issue/SKILL.md` fully.

- [ ] **Step 2: Add governance patterns**

Add these elements to the existing SKILL.md (do not remove existing content):

**After the title, before "What this skill does":**
```markdown
**Announce at start:** "I'm using the drupal-issue skill to analyze issue #[number]."

> **IRON LAW:** NO ACTION WITHOUT READING EVERY COMMENT. Skipping comments leads to duplicate work, wrong classifications, and wasted reviewer time.
```

**Replace "Step 1: Read the issue" intro with a self-exploratory question gate:**
```markdown
## Before You Begin

Before classifying or taking action, answer these questions internally:
1. Have I read EVERY comment chronologically (not just the last one)?
2. Do I know the CURRENT status (not what it was when filed)?
3. Are there MRs? Have I read their diffs?
4. Did any maintainer comment? What did they say?
5. Are there related/parent/blocking issues referenced? Have I read those?
6. What branch/version is this targeting?

If any answer is "no," go read more before proceeding.
```

**After the companion skills table, add:**
```markdown
## Progress Tracking

Create a TaskCreate entry for each major phase:
1. Read and classify the issue
2. [Action-specific steps based on classification]
3. Final output (comment, MR, review)

Mark in_progress when starting each phase, completed when done.
```

**Update the companion skills table** to use explicit handoff language:
```markdown
### Companion Skills (Explicit Handoffs)

| When | REQUIRED NEXT SKILL | Purpose |
|------|---------------------|---------|
| Need to reproduce/test | `/drupal-issue-review` | Set up env, reproduce bug, test MR |
| Need to write/package a fix | `/drupal-contribute-fix` | Fix code, add tests, package for MR |
| Need to write a d.o comment | `/drupal-issue-comment` | Draft conversational HTML comment |
| Need code review | `drupal-reviewer` agent | Review before submitting |
| Need to verify a fix | `drupal-verifier` agent | Verify with drush eval, curl tests |
| Need coding standards check | `/drupal-coding-standards` | PHPCS, PHPStan, file-type review |

**CRITICAL:** Invoke companion skills via the Skill tool. Never inline their behavior from memory.
```

- [ ] **Step 3: Verify**

```bash
grep -c "IRON LAW" skills/drupal-issue/SKILL.md           # should be 1
grep -c "Before You Begin" skills/drupal-issue/SKILL.md    # should be 1
grep -c "REQUIRED NEXT SKILL" skills/drupal-issue/SKILL.md # should be >= 1
grep -c "TaskCreate" skills/drupal-issue/SKILL.md          # should be >= 1
grep -c "Announce at start" skills/drupal-issue/SKILL.md   # should be 1
```

---

### Task 4: Restructure drupal-contribute-fix

Add announcement, iron laws (including adopted Anthropic iron laws for TDD, debugging, verification), self-exploratory question gate, review loop, explicit handoffs, TaskCreate enforcement.

**Files:**
- Modify: `skills/drupal-contribute-fix/SKILL.md`

- [ ] **Step 1: Read the current SKILL.md fully**

Read `skills/drupal-contribute-fix/SKILL.md`. Note its structure (it's the largest skill with Python scripts).

- [ ] **Step 2: Add governance patterns at the top**

After the title and before "Preferred Companion Skill", add:

```markdown
**Announce at start:** "I'm using the drupal-contribute-fix skill to [triage/fix/package] the issue."

> **IRON LAW:** NO CODE PUSHED WITHOUT KERNEL TESTS.
> Every fix MUST include tests that fail against pre-fix code and pass against fixed code.

> **IRON LAW (TDD):** NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST.
> Write the test, watch it fail, write the minimal fix, watch it pass. In that order.

> **IRON LAW (DEBUGGING):** NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST.
> Read the error message. Reproduce consistently. Check recent changes. Then fix.

> **IRON LAW (VERIFICATION):** NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.
> Run PHPCS. Run tests. See them pass. Only then say "done."
```

- [ ] **Step 3: Add self-exploratory question gate**

After the iron laws, before the workflow sections:

```markdown
## Before You Begin

Before writing code or running preflight, answer these questions internally:
1. Is this a contrib/core bug (not a custom module issue)?
2. Have I checked if an upstream fix already exists?
3. Do I know the exact module, version, and branch?
4. Are there existing MRs on the issue I should build on (not duplicate)?
5. Do I have reproduction steps clear enough to write a test?
6. Is there a DDEV environment ready, or do I need `/drupal-issue-review` first?

If answers 1-3 are unclear, run preflight first. If 4-6 are unclear, read the issue more carefully.
```

- [ ] **Step 4: Add review loop section**

After the testing references section, add:

```markdown
## Pre-Push Review Loop

Before pushing to the issue fork:
1. Run PHPCS on all changed files: `ddev exec phpcs --standard=Drupal,DrupalPractice [files]`
2. Run the module's test suite: `ddev exec phpunit [test-path]`
3. For large changes (>3 files or >100 lines): dispatch the `drupal-reviewer` agent
4. If reviewer finds issues: fix and re-run review (max 2 iterations)
5. If still failing after 2 rounds: ask the user

Only push after all checks pass.
```

- [ ] **Step 5: Add explicit handoffs and TaskCreate**

Add at the end:

```markdown
## Handoffs

| After this phase | REQUIRED NEXT SKILL | Purpose |
|-----------------|---------------------|---------|
| Fix is ready to push | (self: push to fork) | Git push to issue fork branch |
| Need to draft a d.o comment | `/drupal-issue-comment` | Write up findings for the issue |
| Need environment setup first | `/drupal-issue-review` | Scaffold DDEV, reproduce, verify |

## Progress Tracking

Create a TaskCreate entry for each phase:
1. Preflight search on drupal.org
2. Triage and classify candidate issues
3. Write the fix (TDD cycle)
4. Write kernel tests
5. Run PHPCS + full test suite
6. Pre-push review
7. Push to issue fork
8. Draft d.o comment (via `/drupal-issue-comment`)
```

- [ ] **Step 6: Verify**

```bash
grep -c "IRON LAW" skills/drupal-contribute-fix/SKILL.md        # should be 4
grep -c "Before You Begin" skills/drupal-contribute-fix/SKILL.md # should be 1
grep -c "Review Loop" skills/drupal-contribute-fix/SKILL.md      # should be 1
grep -c "TaskCreate" skills/drupal-contribute-fix/SKILL.md       # should be >= 1
```

---

### Task 5: Restructure drupal-issue-review

Add announcement, iron law, self-exploratory question gate, explicit handoffs, TaskCreate.

**Files:**
- Modify: `skills/drupal-issue-review/SKILL.md`

- [ ] **Step 1: Read the current SKILL.md**

Read `skills/drupal-issue-review/SKILL.md` fully.

- [ ] **Step 2: Add governance patterns**

After the title, add:

```markdown
**Announce at start:** "I'm using the drupal-issue-review skill to reproduce issue #[number]."

> **IRON LAW:** NO ENVIRONMENT SETUP WITHOUT CLEAR REPRODUCTION STEPS.
> If the issue doesn't have clear steps, read comments until you find them or ask the user.

> **IRON LAW (VERIFICATION):** NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.
> Don't say "reproduced" without showing the error. Don't say "verified" without test output.
```

- [ ] **Step 3: Add self-exploratory question gate**

After the iron laws:

```markdown
## Before You Begin

Before scaffolding a DDEV environment, answer these questions internally:
1. What Drupal core version does this issue target?
2. What module version/branch is needed?
3. Are there specific contrib modules that need to be installed?
4. Are there existing MRs I should apply to test with/without the fix?
5. Does the issue have concrete reproduction steps, or do I need to derive them?
6. Is there already a DDEV environment for this issue number in DRUPAL_ISSUES/?

If answers are unclear, go re-read the issue. Do NOT start `ddev config` until you can answer all 6.
```

- [ ] **Step 4: Add handoffs and TaskCreate**

Add at the end:

```markdown
## Handoffs

| After this phase | REQUIRED NEXT SKILL | Purpose |
|-----------------|---------------------|---------|
| Bug reproduced, need a fix | `/drupal-contribute-fix` | Write the fix + tests |
| Bug reproduced, need to comment | `/drupal-issue-comment` | Draft d.o comment with findings |
| MR tested, need code review | `drupal-reviewer` agent | Review MR quality |

## Progress Tracking

Create a TaskCreate entry for each step:
1. Read and extract issue requirements
2. Scaffold DDEV environment
3. Install required modules
4. Reproduce the bug (or verify the MR fix)
5. Capture evidence (screenshots, error logs)
6. Hand off to next skill
```

- [ ] **Step 5: Verify**

```bash
grep -c "IRON LAW" skills/drupal-issue-review/SKILL.md        # should be 2
grep -c "Before You Begin" skills/drupal-issue-review/SKILL.md # should be 1
grep -c "REQUIRED NEXT SKILL" skills/drupal-issue-review/SKILL.md  # should be >= 1
```

---

### Task 6: Restructure drupal-issue-comment

Add announcement, iron law, explicit "called from" pattern. This skill is a terminal node (no handoff to next skill).

**Files:**
- Modify: `skills/drupal-issue-comment/SKILL.md`

- [ ] **Step 1: Read the current SKILL.md**

Read `skills/drupal-issue-comment/SKILL.md` fully.

- [ ] **Step 2: Add governance patterns**

After the title, before "When to use":

```markdown
**Announce at start:** "I'm using the drupal-issue-comment skill to draft the d.o comment."

> **IRON LAW:** NO SELF-CONGRATULATORY FILLER IN COMMENTS.
> Never mention passing tests, PHPCS results, or how clean your code is. Let the MR speak for itself.

> **IRON LAW:** NO EM DASHES, EN DASHES, OR DOUBLE HYPHENS.
> They look AI-generated. Use commas, colons, semicolons, or periods instead.
```

- [ ] **Step 3: Add "called from" context**

After the iron laws:

```markdown
## Called From

This skill is invoked as the final step by:
- `/drupal-issue` (category F: reply with context, category I: re-review)
- `/drupal-issue-review` (step 5: draft a comment)
- `/drupal-contribute-fix` (after pushing, to document changes)

It is a terminal skill with no handoff to a next skill. Its output is the `.html` comment file.
```

- [ ] **Step 4: Verify**

```bash
grep -c "IRON LAW" skills/drupal-issue-comment/SKILL.md     # should be 2
grep -c "Announce at start" skills/drupal-issue-comment/SKILL.md  # should be 1
grep -c "Called From" skills/drupal-issue-comment/SKILL.md   # should be 1
```

---

### Task 7: Create agent prompt templates

Create structured prompt templates for the drupal-reviewer and drupal-verifier agents, following Anthropic's pattern (context variables, before-you-begin gate, structured report format).

**Files:**
- Create: `skills/drupal-contribute-fix/agents/reviewer-prompt.md`
- Create: `skills/drupal-contribute-fix/agents/verifier-prompt.md`

- [ ] **Step 1: Create agents directory**

```bash
mkdir -p skills/drupal-contribute-fix/agents
```

- [ ] **Step 2: Write reviewer-prompt.md**

Create `skills/drupal-contribute-fix/agents/reviewer-prompt.md`:

```markdown
# Drupal Code Reviewer

You are reviewing Drupal code changes before they are pushed to a drupal.org merge request.

## Context
- **Issue:** [ISSUE_NUMBER] - [ISSUE_TITLE]
- **Module:** [MODULE_NAME]
- **Branch:** [BRANCH_NAME]
- **Changed files:** [LIST_OF_FILES]

## Before You Begin
Read all changed files. Do NOT review from memory or the dispatch summary.

## Review Checklist

### Drupal Standards (Critical)
- [ ] `declare(strict_types=1)` in every PHP file
- [ ] PSR-4 autoloading correct
- [ ] Constructor injection (no `\Drupal::` in classes)
- [ ] PHPDoc on all public methods
- [ ] `$this->t()` for user-facing strings
- [ ] 2-space indentation

### Security
- [ ] No SQL injection (Entity API or parameterized queries)
- [ ] XSS protection (Twig auto-escape, Html::escape)
- [ ] Access control on routes and entities
- [ ] CSRF protection via Form API

### Testing
- [ ] Kernel tests exist for behavioral changes
- [ ] Tests cover the fix scenario specifically
- [ ] No tests for trivial getters/setters (only meaningful behavior)

### Logic
- [ ] Fix addresses the root cause (not symptoms)
- [ ] No unnecessary changes beyond the fix scope
- [ ] Error handling is appropriate
- [ ] Edge cases considered

## Report Format

Report one of:

**APPROVED:** No issues found. Ready to push.

**NEEDS_WORK:** Issues found.
- [SEVERITY: Critical/Important/Minor] [file:line] Description of issue
- [SEVERITY] [file:line] Description

**CONCERNS:** Code is acceptable but has observations.
- [observation 1]
- [observation 2]
```

- [ ] **Step 3: Write verifier-prompt.md**

Create `skills/drupal-contribute-fix/agents/verifier-prompt.md`:

```markdown
# Drupal Fix Verifier

You verify that a Drupal fix actually works by running concrete checks.

## Context
- **Issue:** [ISSUE_NUMBER] - [ISSUE_TITLE]
- **Module:** [MODULE_NAME]
- **DDEV project:** [DDEV_PROJECT_NAME]
- **What the fix should do:** [DESCRIPTION]
- **Reproduction steps:** [STEPS]

## Before You Begin
Verify the DDEV environment is running and the module is enabled.

## Verification Steps

1. **Module enabled:** `ddev drush eval 'print Drupal::moduleHandler()->moduleExists("[MODULE]") ? "yes" : "no";'`
2. **Run the reproduction steps** as described in the issue
3. **Check error logs:** `ddev drush watchdog:show --count=10 --severity=3`
4. **Run module tests:** `ddev exec phpunit [TEST_PATH]`
5. **Run PHPCS:** `ddev exec phpcs --standard=Drupal,DrupalPractice [CHANGED_FILES]`

## Report Format

Report one of:

**VERIFIED:** Fix works.
- Reproduction steps: [what happened - should show the bug is gone]
- Tests: [N/N pass]
- PHPCS: [clean / N issues]
- Evidence: [specific output proving it works]

**FAILED:** Fix does not work.
- What still fails: [description]
- Error output: [paste]
- Suggestion: [what to investigate]

**BLOCKED:** Cannot verify.
- Reason: [environment issue, missing dependency, unclear steps]
- What's needed: [specific ask]
```

- [ ] **Step 4: Reference templates from SKILL.md**

Add to `drupal-contribute-fix/SKILL.md` (in the review loop section):

```markdown
### Agent Prompt Templates

When dispatching review/verification agents, use the prompt templates:
- `agents/reviewer-prompt.md` - Code review before pushing
- `agents/verifier-prompt.md` - Verify fix works in DDEV environment

Fill in the `[BRACKETED]` context variables before dispatching.
```

- [ ] **Step 5: Verify**

```bash
ls skills/drupal-contribute-fix/agents/reviewer-prompt.md
ls skills/drupal-contribute-fix/agents/verifier-prompt.md
```

---

### Task 8: Update CLAUDE.md with status reporting and agent definitions

Update the agent definitions and add TaskCreate enforcement guidance.

**Files:**
- Modify: `.claude/CLAUDE.md`

- [ ] **Step 1: Read the current Available Agents section**

Read `.claude/CLAUDE.md` and find the "Available Agents" section.

- [ ] **Step 2: Update agent definitions with status reporting**

Replace the existing agent definitions with structured versions:

```markdown
## Available Agents

### `drupal-reviewer`
Code review before submitting to drupal.org. Uses `skills/drupal-contribute-fix/agents/reviewer-prompt.md` template.

**Reports:** APPROVED | NEEDS_WORK (with file:line issues) | CONCERNS (with observations)

### `drupal-verifier`
Verify fixes work in DDEV environment. Uses `skills/drupal-contribute-fix/agents/verifier-prompt.md` template.

**Reports:** VERIFIED (with evidence) | FAILED (with error output) | BLOCKED (with reason)

### `drupal-contributor`
Full contribution workflow orchestrator. Coordinates issue reading, reproduction, fixing, and commenting.
```

- [ ] **Step 3: Add TaskCreate enforcement note**

Add after the agents section:

```markdown
## Workflow Tracking

All workflow skills (`/drupal-issue`, `/drupal-issue-review`, `/drupal-contribute-fix`) use TaskCreate for progress tracking. When invoking these skills, expect task entries to appear tracking each phase of work.
```

- [ ] **Step 4: Verify**

```bash
grep -c "drupal-reviewer" .claude/CLAUDE.md    # should be >= 1
grep -c "APPROVED" .claude/CLAUDE.md            # should be >= 1
grep -c "TaskCreate" .claude/CLAUDE.md          # should be >= 1
```

---

### Task 9: Add announcement to drupal-docs

Minor update: add announcement pattern to the docs skill.

**Files:**
- Modify: `skills/drupal-docs/SKILL.md`

- [ ] **Step 1: Read and update**

Read `skills/drupal-docs/SKILL.md`. After the title, add:

```markdown
**Announce at start:** "I'm using the drupal-docs skill to find documentation on [topic]."
```

- [ ] **Step 2: Verify**

```bash
grep -c "Announce at start" skills/drupal-docs/SKILL.md  # should be 1
```

---

### Task 10: Final verification

- [ ] **Step 1: Verify all skills have announcements**

```bash
for skill in skills/*/SKILL.md; do
  name=$(basename $(dirname "$skill"))
  has=$(grep -c "Announce at start" "$skill")
  echo "$name: $has announcement(s)"
done
# All 7 should have at least 1
```

- [ ] **Step 2: Verify iron laws exist where expected**

```bash
for skill in skills/*/SKILL.md; do
  name=$(basename $(dirname "$skill"))
  count=$(grep -c "IRON LAW" "$skill")
  echo "$name: $count iron law(s)"
done
# Expected: coding-standards(1), contribute-fix(4), dev-patterns(1), docs(0), issue(1), issue-comment(2), issue-review(2)
```

- [ ] **Step 3: Verify progressive disclosure (large skills have references)**

```bash
wc -l skills/drupal-dev-patterns/SKILL.md    # should be <100
wc -l skills/drupal-coding-standards/SKILL.md # should be <80
ls skills/drupal-dev-patterns/references/     # should have 3 files
ls skills/drupal-coding-standards/references/ # should have quick-reference.md
```

- [ ] **Step 4: Verify agent templates exist**

```bash
ls skills/drupal-contribute-fix/agents/reviewer-prompt.md
ls skills/drupal-contribute-fix/agents/verifier-prompt.md
```

- [ ] **Step 5: Verify no stale patterns**

```bash
# Check no skill still has "delegate to" without explicit handoff table
grep -rn "Delegate to\|delegate to" skills/*/SKILL.md | grep -v "REQUIRED"
# Should return 0 or only contextual mentions (not handoff instructions)
```
