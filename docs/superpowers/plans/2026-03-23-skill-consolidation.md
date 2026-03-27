# Drupal Skills Consolidation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate 13 Drupal skills down to ~8 by merging overlapping skills, deduplicating content, and removing the custom-drupal-module skill.

**Architecture:** Five consolidation actions: (1) merge two coding-standards skills into one, (2) merge two docs skills into one, (3) merge three dev-pattern skills into one, (4) move testing docs into drupal-contribute-fix and remove drupal-testing as standalone, (5) delete custom-drupal-module. Update CLAUDE.md trigger table and drupal-issue companion references to match.

**Skill directory:** `/home/alphons/project/freelygive/drupal/CONTRIB_WORKBENCH/.claude/skills/`

---

## File Structure

After consolidation, the skills directory should contain:

```
skills/
  drupal-coding-standards/    # MERGED (was -rt), renamed back to plain name
    SKILL.md                  # RT content + quick-reference from old non-RT
    standards-index.md        # Moved from -rt
    assets/standards/         # Moved from -rt (all 27+ files)
  drupal-docs/                # NEW (merged docs-explorer + at-your-fingertips)
    SKILL.md                  # Merged skill
    references/
      drupal-docs-urls.md     # From docs-explorer (expanded with d9book URLs)
  drupal-dev-patterns/        # NEW (merged hooks + DI + security)
    SKILL.md                  # Combined content
  drupal-contribute-fix/      # MODIFIED (absorbs test coverage gate + testing refs)
    SKILL.md                  # Updated with test coverage section
    references/
      core-testing.md         # Existing
      hack-patterns.md        # Existing
      issue-status-codes.md   # Existing
      patch-conventions.md    # Existing
      testing-patterns.md     # NEW (from drupal-testing)
      smoke-testing.md        # NEW (from drupal-testing)
  drupal-issue/               # MODIFIED (remove test gate, update companion refs)
    SKILL.md
  drupal-issue-review/        # UNCHANGED
    SKILL.md
  drupal-issue-comment/       # UNCHANGED
    SKILL.md

DELETED:
  drupal-coding-standards-rt/ # Content moved to drupal-coding-standards
  drupal-at-your-fingertips/  # Content moved to drupal-docs
  drupal-docs-explorer/       # Content moved to drupal-docs
  drupal-hook-patterns/       # Content moved to drupal-dev-patterns
  drupal-service-di/          # Content moved to drupal-dev-patterns
  drupal-security-patterns/   # Content moved to drupal-dev-patterns
  drupal-testing/             # Content moved to drupal-contribute-fix
  custom-drupal-module/       # Deleted entirely
```

---

### Task 1: Merge coding standards skills (2 into 1)

Keep `drupal-coding-standards-rt` content as the base (it has 27+ standards files and dynamic discovery). Fold in the quick-reference content from `drupal-coding-standards` (naming tables, validation commands, anti-patterns, PHPDoc, module structure). Drop the `-rt` suffix.

**Files:**
- Create: `skills/drupal-coding-standards/SKILL.md` (new merged version)
- Move: `skills/drupal-coding-standards-rt/standards-index.md` to `skills/drupal-coding-standards/`
- Move: `skills/drupal-coding-standards-rt/assets/` to `skills/drupal-coding-standards/`
- Delete: `skills/drupal-coding-standards-rt/` (entire directory)

- [ ] **Step 1: Read both SKILL.md files to confirm merge content**

Source A (quick-ref): `skills/drupal-coding-standards/SKILL.md`
Source B (RT/detailed): `skills/drupal-coding-standards-rt/SKILL.md`

- [ ] **Step 2: Write the merged SKILL.md**

The new `skills/drupal-coding-standards/SKILL.md` should contain:
1. Frontmatter: name `drupal-coding-standards`, description covering both quick checks and detailed reviews
2. The RT dynamic-discovery workflow (identify file type, consult routing table, load standards)
3. A new "Quick Reference" section with the old skill's content:
   - Validation commands (phpcs, phpcbf, phpstan, drupal-check, composer audit)
   - Required code patterns (file headers, class declaration, constructor)
   - Naming conventions table
   - Anti-patterns table
   - PHPDoc standards
   - Module structure
4. Keep the standards-index.md reference and assets/ directory paths

- [ ] **Step 3: Move assets and index from -rt to the merged directory**

```bash
cp skills/drupal-coding-standards-rt/standards-index.md skills/drupal-coding-standards/
cp -r skills/drupal-coding-standards-rt/assets skills/drupal-coding-standards/
```

- [ ] **Step 4: Delete the old -rt directory**

```bash
rm -rf skills/drupal-coding-standards-rt
```

- [ ] **Step 5: Verify the merged skill directory is complete**

```bash
ls skills/drupal-coding-standards/SKILL.md
ls skills/drupal-coding-standards/standards-index.md
ls skills/drupal-coding-standards/assets/standards/php/coding.md
```

---

### Task 2: Merge documentation skills (2 into 1)

Merge `drupal-docs-explorer` and `drupal-at-your-fingertips` into a single `drupal-docs` skill. The docs-explorer has the URL catalog + fetch workflow. The at-your-fingertips has 50+ stub references pointing to drupalatyourfingertips.com. Merge by adding the d9book URLs to the docs-explorer URL catalog.

**Files:**
- Create: `skills/drupal-docs/SKILL.md` (based on docs-explorer workflow)
- Create: `skills/drupal-docs/references/drupal-docs-urls.md` (expanded catalog)
- Delete: `skills/drupal-at-your-fingertips/` (entire directory)
- Delete: `skills/drupal-docs-explorer/` (entire directory)

- [ ] **Step 1: Read the existing URL catalog**

Read `skills/drupal-docs-explorer/references/drupal-docs-urls.md` to see the current catalog structure.

- [ ] **Step 2: Extract all d9book URLs from at-your-fingertips references**

Read each file in `skills/drupal-at-your-fingertips/references/` and collect all the URLs. These are all in the format `https://drupalatyourfingertips.com/<topic>`.

- [ ] **Step 3: Create the merged skill directory**

```bash
mkdir -p skills/drupal-docs/references
```

- [ ] **Step 4: Write the expanded URL catalog**

Take the existing `drupal-docs-urls.md` content and add a new "Community Reference (drupalatyourfingertips.com)" section with all the d9book URLs and their topic descriptions.

- [ ] **Step 5: Write the merged SKILL.md**

Based on the docs-explorer SKILL.md workflow (load catalog, match URLs, fetch pages, return results). Update:
- Name: `drupal-docs`
- Description: mention both drupal.org and drupalatyourfingertips.com sources
- Keep the same 4-step workflow (load catalog, match, fetch, return)
- Update tips to mention the broader catalog

- [ ] **Step 6: Delete old skill directories**

```bash
rm -rf skills/drupal-at-your-fingertips
rm -rf skills/drupal-docs-explorer
```

- [ ] **Step 7: Verify**

```bash
ls skills/drupal-docs/SKILL.md
ls skills/drupal-docs/references/drupal-docs-urls.md
```

---

### Task 3: Merge dev pattern skills (3 into 1)

Merge `drupal-hook-patterns`, `drupal-service-di`, and `drupal-security-patterns` into a single `drupal-dev-patterns` skill. Each becomes a section. No content loss.

**Files:**
- Create: `skills/drupal-dev-patterns/SKILL.md`
- Delete: `skills/drupal-hook-patterns/` (entire directory)
- Delete: `skills/drupal-service-di/` (entire directory)
- Delete: `skills/drupal-security-patterns/` (entire directory)

- [ ] **Step 1: Read all three source SKILL.md files**

Confirm content from each:
- `skills/drupal-hook-patterns/SKILL.md` (hooks, form alters, entity hooks, event subscribers, install/update hooks)
- `skills/drupal-service-di/SKILL.md` (service definitions, constructor DI, interface design, plugin DI, common services)
- `skills/drupal-security-patterns/SKILL.md` (SQL injection, XSS, access control, CSRF, file validation, checklist)

- [ ] **Step 2: Create the merged skill directory**

```bash
mkdir -p skills/drupal-dev-patterns
```

- [ ] **Step 3: Write the merged SKILL.md**

Structure:
```
---
name: drupal-dev-patterns
description: Hook implementations, service/DI patterns, and security patterns for Drupal 10/11. Use when implementing hooks, creating services, working with dependency injection, or reviewing code for security.
---

# Drupal Development Patterns

[Brief intro: this skill covers three areas...]

## Hook Patterns
[Full content from drupal-hook-patterns/SKILL.md, minus frontmatter]

## Service & Dependency Injection
[Full content from drupal-service-di/SKILL.md, minus frontmatter]

## Security Patterns
[Full content from drupal-security-patterns/SKILL.md, minus frontmatter]
```

Deduplicate any overlapping content (e.g., both hooks and DI mention `\Drupal::` anti-pattern; keep it in DI section only, reference from hooks section).

- [ ] **Step 4: Delete old skill directories**

```bash
rm -rf skills/drupal-hook-patterns
rm -rf skills/drupal-service-di
rm -rf skills/drupal-security-patterns
```

- [ ] **Step 5: Verify**

```bash
ls skills/drupal-dev-patterns/SKILL.md
# Confirm file contains all three sections
```

---

### Task 4: Move testing into drupal-contribute-fix, delete drupal-testing

The `drupal-testing` skill covers smoke testing (curl, drush eval, test scripts). Move its content into `drupal-contribute-fix` as reference docs. Also deduplicate the TEST COVERAGE GATE (currently in both `drupal-issue` and `drupal-contribute-fix`; keep only in `drupal-contribute-fix`).

**Files:**
- Create: `skills/drupal-contribute-fix/references/smoke-testing.md` (from drupal-testing SKILL.md main patterns)
- Create: `skills/drupal-contribute-fix/references/testing-patterns.md` (from drupal-testing/references/test-patterns.md)
- Modify: `skills/drupal-contribute-fix/SKILL.md` (add testing reference section, absorb test coverage gate)
- Modify: `skills/drupal-issue/SKILL.md:159-174` (remove TEST COVERAGE GATE section, add one-line reference to drupal-contribute-fix)
- Move: `skills/drupal-testing/references/common-checks.md` to `skills/drupal-contribute-fix/references/`
- Delete: `skills/drupal-testing/` (entire directory)

- [ ] **Step 1: Read drupal-contribute-fix SKILL.md fully**

Identify where to add the testing reference section (after the existing references section or at the end).

- [ ] **Step 2: Create smoke-testing.md reference doc**

Extract from `skills/drupal-testing/SKILL.md`:
- Curl smoke test patterns (patterns 1, 2, 3, reusable template)
- DDEV shell gotchas
- Drush eval patterns (service verification, module check, entity field check, config check, permission check, route check)
- Test script creation conventions
- Common verification scenarios table
- Role-based access testing

Save to: `skills/drupal-contribute-fix/references/smoke-testing.md`

- [ ] **Step 3: Copy existing test reference files**

```bash
cp skills/drupal-testing/references/test-patterns.md skills/drupal-contribute-fix/references/testing-patterns.md
cp skills/drupal-testing/references/common-checks.md skills/drupal-contribute-fix/references/common-checks.md
```

- [ ] **Step 4: Update drupal-contribute-fix SKILL.md**

Add a section (before or after the existing references section):

```markdown
## Testing & Verification References

Every fix MUST include tests. The following reference docs are bundled:

- `references/smoke-testing.md` - Curl smoke tests, drush eval patterns, DDEV gotchas
- `references/testing-patterns.md` - PHPUnit test patterns for Drupal
- `references/common-checks.md` - Common verification scenarios
- `references/core-testing.md` - Core testing patterns

### TEST COVERAGE GATE (NON-NEGOTIABLE)

**Every code fix pushed to an MR MUST include kernel tests.** This applies to
both core AND contrib modules in this workspace. Do not push code-only commits
and assume tests can come later. Reviewers WILL send it back.

Before marking any fix work as complete:
1. Write kernel tests that cover each behavioral change
2. Verify the tests FAIL against the pre-fix code
3. Verify the tests PASS against the fixed code
4. Run the full module test suite to confirm no regressions
5. Run PHPCS on all new/modified files
```

- [ ] **Step 5: Remove TEST COVERAGE GATE from drupal-issue**

In `skills/drupal-issue/SKILL.md`, replace lines 159-174 (the full TEST COVERAGE GATE section) with a one-liner:

```markdown
**Test coverage is enforced by `/drupal-contribute-fix`.** See that skill for the full test gate requirements.
```

Also update the companion skills table (line 157) to reference `/drupal-coding-standards` (not the old name).

- [ ] **Step 6: Delete drupal-testing directory**

```bash
rm -rf skills/drupal-testing
```

- [ ] **Step 7: Verify**

```bash
ls skills/drupal-contribute-fix/references/smoke-testing.md
ls skills/drupal-contribute-fix/references/testing-patterns.md
ls skills/drupal-contribute-fix/references/common-checks.md
# Confirm drupal-issue no longer has TEST COVERAGE GATE section
grep -c "TEST COVERAGE GATE" skills/drupal-issue/SKILL.md  # should be 0
grep -c "TEST COVERAGE GATE" skills/drupal-contribute-fix/SKILL.md  # should be 1
```

---

### Task 5: Delete custom-drupal-module

Not needed in this contribution workspace. Remove entirely.

**Files:**
- Delete: `skills/custom-drupal-module/` (entire directory including references/)

- [ ] **Step 1: Delete the directory**

```bash
rm -rf skills/custom-drupal-module
```

- [ ] **Step 2: Verify it's gone**

```bash
ls skills/custom-drupal-module 2>&1  # should error
```

---

### Task 6: Update CLAUDE.md trigger table

Update the skill auto-invoke tables in `.claude/CLAUDE.md` to reflect the new skill names.

**Files:**
- Modify: `.claude/CLAUDE.md` (the Skills Auto-Invoke Rules section)

- [ ] **Step 1: Read the current trigger tables**

Read `.claude/CLAUDE.md` and find the "Skills Auto-Invoke Rules" section with both tables.

- [ ] **Step 2: Replace "Code Quality & Standards" table**

Old:
```markdown
| `/drupal-coding-standards` | Quick check on a Drupal coding convention |
| `/drupal-coding-standards-rt` | Reviewing code against Drupal standards (detailed, per file type) |
| `/drupal-testing` | Writing or running Drupal tests |
| `/drupal-security-patterns` | Reviewing code for security issues or implementing access control |
```

New:
```markdown
| `/drupal-coding-standards` | Checking or reviewing code against Drupal coding standards (any file type) |
```

- [ ] **Step 3: Replace "Development Patterns" table**

Old:
```markdown
| `/drupal-hook-patterns` | Implementing hooks, form alters, or event subscribers |
| `/drupal-service-di` | Creating services or working with dependency injection |
| `/drupal-at-your-fingertips` | Need Drupal API reference for entities, caching, forms, etc. |
| `/custom-drupal-module` | Creating a new Drupal module from scratch |
| `/drupal-docs-explorer` | Need authoritative drupal.org documentation |
```

New:
```markdown
| `/drupal-dev-patterns` | Implementing hooks, creating services, DI, or security patterns |
| `/drupal-docs` | Need Drupal documentation or API reference |
```

- [ ] **Step 4: Verify no stale skill references remain**

```bash
grep -n "drupal-coding-standards-rt\|drupal-at-your-fingertips\|drupal-docs-explorer\|drupal-hook-patterns\|drupal-service-di\|drupal-security-patterns\|drupal-testing\|custom-drupal-module" .claude/CLAUDE.md
# Should return 0 matches
```

---

### Task 7: Update drupal-issue companion skill references

The `drupal-issue` SKILL.md references companion skills by name. Update any stale references.

**Files:**
- Modify: `skills/drupal-issue/SKILL.md`

- [ ] **Step 1: Find and update stale references**

In `skills/drupal-issue/SKILL.md`:
- Line 157: change `/drupal-coding-standards` to `/drupal-coding-standards` (this one stays the same since we renamed -rt back)
- Any reference to `/drupal-testing` should become a reference to the testing docs in `/drupal-contribute-fix`

- [ ] **Step 2: Verify no stale skill names remain**

```bash
grep -n "drupal-coding-standards-rt\|drupal-at-your-fingertips\|drupal-docs-explorer\|drupal-hook-patterns\|drupal-service-di\|drupal-security-patterns\|drupal-testing\|custom-drupal-module" skills/drupal-issue/SKILL.md
# Should return 0 matches
```

---

### Task 8: Final verification

- [ ] **Step 1: List all remaining skill directories**

```bash
ls -d skills/*/
```

Expected (8 directories):
```
skills/drupal-coding-standards/
skills/drupal-contribute-fix/
skills/drupal-dev-patterns/
skills/drupal-docs/
skills/drupal-issue/
skills/drupal-issue-comment/
skills/drupal-issue-review/
```

That's 7, not 8. The `drupal-issue-comment` and `drupal-issue-review` are unchanged, giving us 7 total skills (down from 13).

- [ ] **Step 2: Verify no broken cross-references**

```bash
# Check all SKILL.md files for references to deleted skills
grep -rn "drupal-coding-standards-rt\|drupal-at-your-fingertips\|drupal-docs-explorer\|drupal-hook-patterns\|drupal-service-di\|drupal-security-patterns\|drupal-testing\|custom-drupal-module" skills/*/SKILL.md
# Should return 0 matches (except possibly in historical context like "was merged from")
```

- [ ] **Step 3: Verify each skill has valid frontmatter**

Read each SKILL.md and confirm:
- Has `---` frontmatter with `name` and `description`
- Name matches the directory name
- Description is accurate for the merged content
