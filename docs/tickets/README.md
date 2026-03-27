# Skill & Agent Improvement Tickets

Improvements identified from analysis of the #3579478 session (ai_provider_litellm guardrails review) and comparison with the superpowers plugin orchestration system.

## P0: Critical (Do First)

| # | Title | Scope | Est. Impact |
|---|-------|-------|-------------|
| [001](001-hands-free-orchestration.md) | Make /drupal-issue hands-free until push gate | drupal-issue, drupal-issue-review, drupal-contribute-fix | Eliminates all mid-workflow user stops |
| [002](002-enriched-agent-return-values.md) | Enriched agent return values | drupal-issue-fetcher, drupal-ddev-setup | Eliminates ~30s of redundant re-reading per session |

## P1: High (Core Workflow Improvements)

| # | Title | Source | Scope | Est. Impact |
|---|-------|--------|-------|-------------|
| [003](003-parallel-ddev-and-code-review.md) | Parallel DDEV setup + static code review | Session | drupal-issue-review | Saves 3-4 min per session |
| [004](004-auto-dispatch-reviewer-verifier.md) | Auto-dispatch reviewer and verifier agents | Session | drupal-contribute-fix, drupal-issue-review | Better quality, consistent review |
| [005](005-split-contribute-fix-skill.md) | Split drupal-contribute-fix into modes | Session | drupal-contribute-fix | Saves ~20KB context per invocation |
| [006](006-auto-test-validation.md) | Automated test legitimacy validation | Session | drupal-contribute-fix, drupal-verifier | Proves tests are real, not cheating |
| [008](008-preflight-search-enforcement.md) | Enforce preflight search before code changes | Session | drupal-issue-review, drupal-issue | Prevents duplicate work |
| [018](018-two-stage-review-per-task.md) | Two-stage review (spec + quality) | **Superpowers** | New agent + drupal-reviewer | Catches "correct but wrong" code |
| [019](019-fresh-subagent-per-phase.md) | Fresh subagent per phase (controller pattern) | **Superpowers** | All workflow skills | Controller stays lean, agents focused |
| [021](021-structured-agent-status-codes.md) | Structured agent status codes | **Superpowers** | All agents | DONE/BLOCKED/NEEDS_CONTEXT handling |
| [022](022-verification-gate-pattern.md) | Verification gate (evidence before claims) | **Superpowers** | All workflow skills | No "should work"; only proven claims |

## P2: Medium (Quality of Life)

| # | Title | Source | Scope | Est. Impact |
|---|-------|--------|-------|-------------|
| [007](007-pipeline-monitoring.md) | Post-push GitLab CI pipeline monitoring | Session | New agent | Catches CI failures automatically |
| [009](009-auto-draft-issue-comment.md) | Auto-draft issue comment before push | Session | drupal-issue, drupal-issue-comment | Better communication on d.o |
| [010](010-related-issue-discovery.md) | Related issue discovery | Session | drupal-issue-fetcher | Broader context for reviews |
| [011](011-batch-task-creation.md) | Reduce task creation overhead | Session | All skills | Saves ~8s preamble per skill |
| [012](012-chrome-mcp-for-screenshots.md) | Use Chrome MCP instead of Playwright | Session | drupal-issue-review, drupal-issue-comment | Saves ~60s per screenshot session |
| [013](013-diff-aware-test-generation.md) | Diff-aware test scaffolding | Session | drupal-contribute-fix | Reduces test writing iterations |
| [020](020-rationalization-prevention.md) | Rationalization prevention tables | **Superpowers** | All skills | Stops model from skipping rules |
| [023](023-explicit-state-handoff-artifacts.md) | Explicit state handoff artifacts | **Superpowers** | All workflow skills | Resumable, auditable workflow |
| [024](024-skill-testing-with-pressure-scenarios.md) | Skill testing with pressure scenarios | **Superpowers** | All skills | Proves skills actually work |

## P3: Low (Cleanup & Polish)

| # | Title | Source | Scope | Est. Impact |
|---|-------|--------|-------|-------------|
| [014](014-contributor-agent-dedup.md) | Clarify/remove drupal-contributor agent overlap | Session | drupal-contributor agent | Reduces confusion |
| [015](015-agent-model-flexibility.md) | Agent model selection per task complexity | Session | All agents | Better quality/cost balance |
| [016](016-review-only-fast-path.md) | Lightweight review-only path (no DDEV) | Session | drupal-issue, drupal-issue-review | 10 min vs 20+ min for code reviews |
| [017](017-interdiff-generation.md) | Generate interdiff for follow-up commits | Session | drupal-contribute-fix | Helps MR reviewers |
| [025](025-finishing-workflow.md) | Structured finishing workflow (post-push) | **Superpowers** | drupal-contribute-fix | Clean exit with options |
| [026](026-no-placeholders-in-plans.md) | No placeholders in test plans/findings | **Superpowers** | drupal-issue-review, drupal-contribute-fix | Complete, actionable artifacts |

## Dependency Graph

```
001 (hands-free) -----> 002 (enriched returns)  [001 benefits from 002]
001 (hands-free) -----> 004 (auto agents)       [001 needs auto-dispatch]
001 (hands-free) -----> 009 (auto comment)       [001 needs auto-comment]
001 (hands-free) -----> 021 (status codes)       [controller needs status handling]
003 (parallel)   -----> 002 (enriched returns)  [parallel needs DDEV status]
004 (auto agents) ----> 018 (two-stage review)  [two distinct reviewers]
004 (auto agents) ----> 015 (model flexibility) [agents need right models]
006 (test validation) > 004 (auto agents)       [verifier does validation]
008 (preflight) ------> 001 (hands-free)        [preflight is part of flow]
013 (diff tests) -----> 003 (parallel)          [test plan during DDEV setup]
018 (two-stage) ------> 021 (status codes)      [reviewers use status protocol]
019 (controller) -----> 002 (enriched returns)  [agents pass context forward]
019 (controller) -----> 021 (status codes)      [agents report structured status]
019 (controller) -----> 023 (state artifacts)   [phases write/read state files]
020 (rationalizations)> 024 (pressure tests)    [test that rationalizations are caught]
022 (verification) ---> 006 (test validation)   [verification includes test legitimacy]
```

## Suggested Execution Order

### Phase 1: Foundation (enables everything)
1. **021** (structured status codes) - universal agent protocol
2. **002** (enriched returns) - eliminate re-reading
3. **022** (verification gates) - evidence before claims

### Phase 2: The Main Goal (hands-free)
4. **001** (hands-free orchestration) - auto-chain all skills
5. **008** (preflight enforcement) - safety gate in the chain
6. **009** (auto-comment) - complete the chain

### Phase 3: Quality Gates
7. **018** (two-stage review) - spec + quality separation
8. **004** (auto agents) - mandatory reviewer/verifier dispatch
9. **006** (test validation) - stash/unstash proof

### Phase 4: Performance
10. **003** (parallel execution) - DDEV + review in parallel
11. **019** (controller pattern) - lean main session
12. **011** (task overhead) - quick win
13. **005** (split skill) - context savings

### Phase 5: Polish
14. **020** (rationalization tables) - discipline enforcement
15. **023** (state artifacts) - resumable workflows
16. **013** (diff-aware tests) - smarter test generation
17. Everything else in priority order

### Phase 6: Validation
18. **024** (pressure testing) - prove it all works

## Key Lessons from Superpowers

Patterns we're adopting from the superpowers plugin system:

| Pattern | Superpowers Source | Our Ticket |
|---------|-------------------|------------|
| Two-stage review (spec then quality) | subagent-driven-development | 018 |
| Fresh subagent per task (controller pattern) | subagent-driven-development | 019 |
| Rationalization prevention tables | TDD, debugging, verification skills | 020 |
| Structured status codes (DONE/BLOCKED/NEEDS_CONTEXT) | subagent-driven-development | 021 |
| Evidence before claims (verification gate) | verification-before-completion | 022 |
| Explicit state artifacts between phases | design doc -> plan doc -> execution | 023 |
| TDD applied to skill creation (pressure tests) | writing-skills | 024 |
| Structured finishing options | finishing-a-development-branch | 025 |
| No placeholders in actionable documents | writing-plans | 026 |
