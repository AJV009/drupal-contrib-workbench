# TICKET-018: Two-Stage Review (Spec Compliance + Code Quality)

**Status:** COMPLETED
**Priority:** P1 (High)
**Affects:** `.claude/skills/drupal-contribute-fix/SKILL.md`, `.claude/agents/drupal-reviewer.md`
**Inspired by:** Superpowers `subagent-driven-development` skill
**Type:** Enhancement

## Pattern from Superpowers

Superpowers enforces TWO distinct review stages per task, in strict order:

1. **Spec compliance review:** Does the code do what was asked? Nothing more, nothing less.
2. **Code quality review:** Is it well-built? Clean, tested, maintainable?

The spec reviewer explicitly does NOT trust the implementer's self-report. It reads the actual code and verifies against requirements line-by-line. The code quality reviewer only runs AFTER spec compliance passes.

This separation prevents a common failure mode: code that is beautifully written but doesn't actually solve the problem, or code that solves the problem but is unmaintainable.

## What We Have Now

Our `drupal-reviewer` agent combines both concerns into a single checklist:
- Coding standards (quality)
- Security (quality)
- DI compliance (quality)
- Type safety (quality)
- Test coverage (spec)
- API compatibility (spec)
- Documentation (quality)

There is no spec compliance check. Nobody verifies: "Did this fix actually address the issue? Does it match what the maintainer asked for? Does it cover ALL the scenarios described in the issue comments?"

## The Problem This Solves

In the #3579478 session, we wrote fixes for entity ID truncation and error propagation. But nobody verified:
- Did the fix match what nikro (the maintainer) described in comment #5?
- Did we miss any of the testing steps nikro listed?
- Did we add anything beyond what was requested (scope creep)?
- Does our fix align with the module's architectural direction?

## Implementation Plan

### 1. Create a spec compliance reviewer agent

New file: `.claude/agents/drupal-spec-reviewer.md`

```markdown
---
model: opus
tools: [Read, Grep, Glob]
---

# Drupal Spec Compliance Reviewer

You are reviewing code changes for spec compliance. Your job is to verify
that the implementation matches what was requested, nothing more and
nothing less.

## Input
- Issue requirements (from issue.json + comments)
- MR description or commit message
- List of changed files
- What the implementer claims they did

## Review Checklist

1. **Requirement Mapping:**
   For each requirement in the issue:
   - Is it addressed by the code? (file:line reference)
   - Is it addressed CORRECTLY? (not just present, but correct)
   - Is it tested?

2. **Scope Check:**
   For each code change:
   - Does it map to a requirement? If not, is it scope creep?
   - Is the change minimal for the requirement?

3. **Missing Requirements:**
   - Are there requirements from the issue that are NOT addressed?
   - Are there edge cases mentioned in comments that aren't handled?
   - Are there maintainer instructions that weren't followed?

4. **Maintainer Alignment:**
   - Does the implementation match the maintainer's stated approach?
   - If the maintainer suggested a specific pattern, was it used?

## Report Format

SPEC_COMPLIANT:
- All N requirements addressed
- No scope creep detected
- Maintainer alignment: YES

SPEC_GAPS:
- Requirement "X" not addressed (from comment #3 by nikro)
- Extra change in file.php:42 not related to any requirement
- Maintainer asked for approach A, implementation uses approach B

## CRITICAL: Do NOT Trust the Implementer

Do NOT read the implementer's description of what they did. Read the
ACTUAL CODE and verify against the ACTUAL REQUIREMENTS. Implementers
sometimes:
- Forget to implement something they said they did
- Implement something slightly different from what was asked
- Add extra features not requested
- Miss edge cases from comments
```

### 2. Update the review flow in `drupal-contribute-fix`

Replace the single review step with two sequential stages:

```markdown
## Pre-Push Quality Gate (MANDATORY)

### Stage 1: Spec Compliance (MUST pass before Stage 2)

Dispatch `drupal-spec-reviewer` agent with:
- Issue requirements extracted from artifacts
- List of changed files
- Implementer's claimed changes

If SPEC_GAPS: fix gaps, re-dispatch. Max 2 iterations.

### Stage 2: Code Quality (ONLY after Stage 1 passes)

Dispatch `drupal-reviewer` agent with:
- Changed files
- PHPCS results
- Module path

If NEEDS_WORK: fix issues, re-dispatch. Max 2 iterations.

### Both must pass before push gate.
```

### 3. Order matters

From superpowers:

> Start code quality review BEFORE spec compliance = VIOLATION

The reasoning: fixing code quality issues on code that doesn't meet spec is wasted effort. If the spec reviewer says "this method shouldn't exist," making it beautifully formatted is pointless.

## Acceptance Criteria

- [ ] Spec compliance reviewer agent created
- [ ] Two-stage review enforced: spec first, quality second
- [ ] Spec reviewer verifies against actual issue requirements
- [ ] Spec reviewer does NOT trust implementer's claims
- [ ] Quality review only runs after spec compliance passes
- [ ] Both stages must pass before push gate

## Files to Create/Modify

1. `.claude/agents/drupal-spec-reviewer.md` - NEW
2. `.claude/skills/drupal-contribute-fix/SKILL.md` - Two-stage review flow
3. `.claude/agents/drupal-reviewer.md` - Remove spec concerns (now handled by spec reviewer)
