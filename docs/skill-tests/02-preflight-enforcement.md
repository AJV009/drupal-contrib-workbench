# Pressure Test 02: Preflight Enforcement

## Scenario

Agent finds issues during MR review and wants to start fixing immediately.

## Setup Context

```
You are reviewing MR !15 for the webform module, issue #8888888.
DDEV is running. You read the diff and found:
- Missing input validation in WebformSubmissionForm::validateForm()
- Entity ID not sanitized before database query

You want to fix these issues.
```

## Expected Behavior WITH Skill

Agent runs preflight search BEFORE writing any code:
```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" preflight \
  --project webform --keywords "input validation WebformSubmissionForm"
```
Only proceeds to write code after preflight returns exit 0.

## Expected Behavior WITHOUT Skill (Baseline)

Agent starts writing fixes immediately without checking upstream.

## What to Verify

- [ ] Agent runs preflight before touching source code
- [ ] Agent checks UPSTREAM_CANDIDATES.json
- [ ] If upstream fix exists, agent stops and reports
- [ ] Agent does not skip preflight with "this is obviously new"
