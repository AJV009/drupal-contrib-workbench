# Drupal Workflow Skill Conventions

Open this file when touching the Drupal workflow skills:
`drupal-issue`, `drupal-issue-review`, `drupal-contribute-fix`,
`drupal-issue-comment`. Documents the shared conventions so an update
to one skill doesn't break the chain.

## The pipeline

The four workflow skills form a pipeline invoked by `/drupal-issue`:

```
/drupal-issue {issue-id-or-url}
   ↓
drupal-issue-fetcher agent  (populates DRUPAL_ISSUES/{id}/artifacts/)
   ↓
drupal-issue  (classification; Steps 0-3)
   ↓ (delegate based on category A-I)
drupal-issue-review  (env setup, reproduction, MR freshness check)
   ↓ (auto-continue after reproduction)
drupal-contribute-fix  (TDD, tests, quality gates, push gate)
   ↓ (Step 6: draft comment)
drupal-issue-comment  (final comment HTML)
```

The pipeline is hands-free from invocation to push gate. The only stop
point is the push gate in `drupal-contribute-fix`, or the draft comment
presentation for comment-only outcomes.

## What lives in CLAUDE.md vs individual skills

Workspace-wide preamble rules live in `CLAUDE.md` and are loaded
automatically in every session. Do NOT duplicate them in individual
skills.

**In `CLAUDE.md`** (canonical location):

- Hands-Free Workflow rules (no announcing, no inter-phase confirmation,
  auto-chain, stop only at push gate)
- Pre-Work Gate behavior when `--pre-work-gate` is passed
- Workflow Tracking (lazy TaskCreate usage)
- Agent Status Protocol (DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT /
  BLOCKED / FAILED)
- SSH config convention (`git.drupal.org`, not `git.drupalcode.org`)
- Dependency rules (always `drupal/core-dev:^11`, never `phpunit/phpunit`
  standalone, never `drupal/coder` standalone)
- Directory structure rules (`DRUPAL_ISSUES/{id}/`, `TEMP/`)
- Coding standards non-negotiables
- MR workflow (rebase over merge, existing MRs only, force-with-lease)

**In individual skill files** (specific to that phase):

- Step-by-step procedures for the phase
- Phase-specific Before You Begin questions
- Phase-specific Gotchas
- Phase-specific Rationalization Prevention rows
- Templates, exit codes, classification categories

When editing a workflow skill, if you find yourself restating something
from CLAUDE.md, delete it and reference the CLAUDE.md section instead.

## Canonical location table

| Topic | Canonical location |
|---|---|
| Hands-Free workflow rules | `CLAUDE.md` |
| Workflow Tracking (lazy tasks) | `CLAUDE.md` |
| Dependency rules (core-dev, phpunit, coder) | `CLAUDE.md` |
| SSH remote convention | `CLAUDE.md` |
| Issue classification categories (A-I) | `drupal-issue` SKILL.md |
| Three-part pre-follow-up search | `drupal-issue` Q10 |
| Bug-class vs symptom rule | `drupal-issue` Q9 |
| Absence verification (false-absence claims) | `drupal-issue` Q7 + "Verify claims against source code" |
| MR Freshness Check | `drupal-issue` Step 2 + `drupal-issue-review` Gotchas |
| Static review checklist | `drupal-issue-review/references/static-review-checklist.md` |
| CI parity helper (`local_ci_mirror.sh`) | `drupal-contribute-fix` Pre-Push Quality Gate Step 0 + `drupal-contribute-fix/references/ci-parity.md` |
| Test validation stash-and-rerun procedure | `drupal-contribute-fix` Testing Step 3 |
| Input Shape Coverage (scan-surface enumeration) | `drupal-spec-reviewer.md` Section 2d + `drupal-contribute-fix` Before You Begin Q7 |
| Byte-level fidelity + `getRenderedTools()` trap | `drupal-contribute-fix` Gotchas + `reviewer-prompt.md` Content Scanning section |
| Humility rules (comment drafting) | `drupal-issue-comment` "Humility over showmanship" |
| Semantic Intent checks (word-vs-mechanism, downstream consumer view) | `drupal-contribute-fix/agents/reviewer-prompt.md` Semantic Intent section |

When adding a new rule, check this table first. If the topic already
has a canonical location, add the rule there. If it doesn't, pick the
most specific location (narrowest skill that the rule applies to).

## Incident log (rules that exist because of specific failures)

| Incident | Rule | Where enforced |
|---|---|---|
| `#3542457` | Bug fixes require tests; code-only pushes get bounced | `drupal-contribute-fix` Testing Step 2 |
| `#3560681` | Pre-follow-up search before proposing "separate follow-up" work; word-vs-mechanism and downstream-consumer checks for semantic intent | `drupal-issue` Q10; `reviewer-prompt.md` Semantic Intent |
| `#3580690` | `getRenderedTools()` double-encoding; read called APIs before calling them; input-shape enumeration for scan/guard code; rationalization of "too long" and "trade-off acceptable" | `drupal-contribute-fix` Gotchas; `drupal-contribute-fix` Before You Begin Q7; `drupal-issue` Q9; `drupal-spec-reviewer.md` 2d; `reviewer-prompt.md` Content Scanning; Rationalization Prevention rows |
| `#3581952`, `#3581955` | Cross-issue premise verification; companion issues share premises | `drupal-issue` Q8 + "Cross-reference validation for companion issues"; `drupal-spec-reviewer.md` absence verification section |

When referencing an incident in a new rule, check the incident log to
confirm you're not duplicating an existing rule, and to link the new
rule to the larger pattern.

## Shared agents (dispatched by contribute-fix)

| Agent | Purpose | Prompt template |
|---|---|---|
| `drupal-issue-fetcher` | Fetches issue + MR + discussion artifacts | Built-in |
| `drupal-ddev-setup` | Scaffolds DDEV environment | Built-in |
| `drupal-spec-reviewer` | Verifies implementation matches issue requirements + input shape coverage | `.claude/agents/drupal-spec-reviewer.md` |
| `drupal-reviewer` | Code quality + standards + byte-fidelity + semantic intent | `drupal-contribute-fix/agents/reviewer-prompt.md` |
| `drupal-verifier` | Runtime verification in DDEV environment | `drupal-contribute-fix/agents/verifier-prompt.md` |
| `drupal-pipeline-watch` | Monitors GitLab CI after push | Built-in |

Agent prompts are templates with `[BRACKETED]` context variables. Fill
them in at dispatch time; don't pre-fill in the template.

When the review/verify/spec-review agents get a new check, add it to
the agent's prompt template (`drupal-contribute-fix/agents/reviewer-prompt.md`
or `.claude/agents/drupal-spec-reviewer.md`), NOT to the skill body.
The skill body should only dispatch and consume results.

## Common "don't do this" patterns when editing workflow skills

- **Don't restate CLAUDE.md rules.** If a rule lives in CLAUDE.md,
  reference it with a one-liner, don't copy it.
- **Don't add hands-free rules to a skill.** They're workspace-wide.
- **Don't add new IRON LAWs casually.** The four in
  `drupal-contribute-fix` cover the whole pipeline. A new rule usually
  belongs in Rules at a glance or Rationalization Prevention instead.
- **Don't add a new top-level section for a rule.** Usually the rule
  belongs in an existing section (Gotchas, Rationalization Prevention,
  a Before You Begin question). Only add a new section when the topic
  genuinely doesn't fit anywhere else.
- **Don't edit CLAUDE.md as part of a skill update** without explicit
  user instruction. CLAUDE.md affects every session; changes need
  deliberate approval.
- **Don't forget to check `git status` before editing.** Workflow skills
  frequently have uncommitted intentional changes from recent sessions.
  Overwriting them is the most common session-breaking error.

## Pipeline stop points

The full pipeline has exactly these stop points (where the agent waits
for user input):

1. **Pre-Work Gate** (optional, only if `--pre-work-gate` or `--gate`
   passed): in `drupal-issue-review` Step 4.5.
2. **Push Gate** (mandatory): in `drupal-contribute-fix`. This is the
   only unconditional stop point.
3. **Draft comment presentation** (when the workflow is comment-only,
   no push): at the end of `drupal-issue-comment`.

Do NOT add any other stop points to workflow skills without explicit
user direction. "Stopping to ask for clarification" is the single most
common way a session gets derailed.
