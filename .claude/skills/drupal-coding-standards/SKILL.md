---
name: drupal-coding-standards
description: Drupal coding standards for quick checks and detailed file-type reviews. Covers PHPCS, PHPStan, naming conventions, code style enforcement, and comprehensive per-file-type standards for PHP, JavaScript, CSS, Twig, YAML, SQL, and markup in Drupal 10/11 projects.
metadata:
  author: ajv009, ronaldtebrake
  version: "1.0"
---

# Drupal Coding Standards

**Announce at start:** "I'm using the drupal-coding-standards skill to review [file type] code."

> **IRON LAW:** ALWAYS RUN PHPCS BEFORE COMMITTING. Never skip static analysis.

Always run PHPCS before committing. Never skip static analysis. Use `declare(strict_types=1)` in every PHP file. Prefer `final` classes unless explicitly designed for extension. Avoid deep nesting; use guard clauses and early returns.

## When to Use

Activate this skill when:
- Checking a quick coding convention or pattern
- Reviewing code in Drupal projects (modules, themes, profiles)
- Checking code for compliance with Drupal coding standards
- Performing code reviews on PHP, JavaScript, CSS, Twig, YAML, or SQL files
- Ensuring code follows Drupal best practices and conventions

## Detailed Review Workflow (Dynamic Context Discovery)

This skill uses **dynamic context discovery** to load only the relevant standards based on the file type being reviewed:

1. **Identify the file type** being reviewed (`.php`, `.js`, `.css`, `.twig`, `.yml`, etc.)
2. **Consult the routing table** in `standards-index.md` to find the corresponding standard file
3. **Load the specific standard** from `assets/standards/[category]/[file].md`
4. **Apply the standards** to review the code
5. **Provide specific, actionable feedback** referencing the relevant sections of the standards

For the full routing table mapping file extensions to standard files, see `standards-index.md` in this skill directory.

### General Concerns (all file types)
- **Accessibility**: `assets/standards/accessibility/accessibility.md` (applies to all frontend code)
- **Spelling**: `assets/standards/spelling/spelling.md` (applies to all documentation and user-facing strings)

## Quick Reference

For validation commands, naming conventions, required code patterns, anti-patterns, and module structure: see `references/quick-reference.md`
