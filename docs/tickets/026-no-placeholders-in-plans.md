# TICKET-026: No Placeholders Rule for Test Plans and Review Findings

**Status:** COMPLETED
**Priority:** P3 (Low)
**Affects:** `.claude/skills/drupal-issue-review/SKILL.md`, `.claude/skills/drupal-contribute-fix/SKILL.md`
**Inspired by:** Superpowers `writing-plans` skill (No Placeholders Rule)
**Type:** Enhancement

## Pattern from Superpowers

Superpowers enforces a strict "no placeholders" rule in implementation plans:

- NO "TBD", "TODO", "implement later"
- NO "add appropriate error handling" (must show actual handling)
- NO "similar to Task N" (repeat the code, agent may read out of order)
- NO steps describing WHAT without showing HOW

The reasoning: an agent executing the plan may read tasks out of order, may lose context between tasks, and needs complete, self-contained instructions for every step.

## Applied to Our System

When we generate test plans (TICKET-013) and review findings (TICKET-023), the same rule should apply. A test plan that says:

```
- [ ] Test error handling for guardrails() method
```

...is a placeholder. What error? What handling? What assertion? The agent writing the test has to re-discover everything.

Instead:

```
- [ ] Test LiteLlmAiClient::guardrails() throws GuzzleException on connection timeout
      Setup: Mock HTTP client to throw ConnectException
      Call: $client->guardrails()
      Assert: ConnectException propagates (is NOT caught)
      Why: guardrails() had a catch(\Throwable) that swallowed connection errors
```

## Rules to Add

### In test plans:

```markdown
## No Placeholders in Test Plans

Every test case MUST include:
- Exact method being tested (Class::method)
- Setup requirements (what to mock, what to configure)
- Input/action that triggers the behavior
- Expected outcome (specific assertion, not "works correctly")
- Why this test exists (what bug/behavior it validates)

Forbidden patterns:
- "Test error handling" (WHICH error? HOW handled?)
- "Verify it works" (WHAT works? HOW verified?)
- "Similar to test above" (repeat it; agent reads independently)
- "Add appropriate assertions" (WHICH assertions? Be specific.)
```

### In review findings:

```markdown
## No Placeholders in Review Findings

Every finding MUST include:
- Exact file and line number
- What's wrong (specific, not "potential issue")
- Why it's wrong (reference to standard, security risk, or bug)
- Suggested fix (specific change, not "should be improved")

Forbidden patterns:
- "May have issues" (DOES it or doesn't it?)
- "Should be reviewed" (you ARE the reviewer; review it now)
- "Consider improving" (improve it now or don't mention it)
- "Potential security concern" (IS it a concern? Explain the vector.)
```

## Acceptance Criteria

- [ ] Test plan template includes mandatory fields (method, setup, action, assertion, why)
- [ ] Review findings template includes mandatory fields (file:line, what, why, fix)
- [ ] Forbidden placeholder patterns documented
- [ ] Skills enforce completeness before handoff

## Files to Modify

1. `.claude/skills/drupal-issue-review/SKILL.md` - No-placeholder rule for findings
2. `.claude/skills/drupal-contribute-fix/SKILL.md` - No-placeholder rule for test plans
