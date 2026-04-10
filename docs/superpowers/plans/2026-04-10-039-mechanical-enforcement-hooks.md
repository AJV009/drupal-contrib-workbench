# Ticket 039 — Mechanical Enforcement Hooks + bd Session Progress — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add PreToolUse (push gate) and Stop (workflow completion) hooks that mechanically enforce the pre-push quality gate via exit code 2 blocking. Include bd writes for cross-session progress tracking. Add the `03-push-gate-checklist.json` state file that the hooks gate on.

**Architecture:** Two bash scripts in `.claude/hooks/`, wired via `.claude/settings.json`. The fix skill writes `03-push-gate-checklist.json` at new Step 5.5; hooks read it. bd writes are best-effort side-effects.

**Tech Stack:** Bash, jq, Claude Code hooks (settings.json), bd CLI, ssh to remote `alphons@192.168.0.218:/home/alphons/drupal/CONTRIB_WORKBENCH`.

**Session rule:** NO GIT COMMITS. User reviews full pile at end.

---

## Phase A — Hook scripts

### Task 1: Create `.claude/hooks/push-gate.sh`

**Files:**
- Create: `.claude/hooks/push-gate.sh`

- [ ] **Step 1: Create hooks directory and write the script**

```bash
ssh alphons@192.168.0.218 'mkdir -p /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/hooks'
```

Then write the full script via scp.

- [ ] **Step 2: Make executable and syntax check**

```bash
ssh alphons@192.168.0.218 'chmod +x /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/hooks/push-gate.sh && bash -n /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/hooks/push-gate.sh && echo "syntax ok"'
```

- [ ] **Step 3: Test — non-push Bash command exits 0**

Pipe a synthetic non-push tool call to the hook:

```bash
ssh alphons@192.168.0.218 'echo "{\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"ls -la\"},\"cwd\":\"/home/alphons/drupal/CONTRIB_WORKBENCH\"}" | bash /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/hooks/push-gate.sh; echo "exit=$?"'
```
Expected: `exit=0` (not a push, passthrough).

- [ ] **Step 4: Test — non-Bash tool exits 0**

```bash
ssh alphons@192.168.0.218 'echo "{\"tool_name\":\"Read\",\"tool_input\":{\"file_path\":\"/tmp/x\"},\"cwd\":\"/home/alphons/drupal/CONTRIB_WORKBENCH\"}" | bash /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/hooks/push-gate.sh; echo "exit=$?"'
```
Expected: `exit=0`.

- [ ] **Step 5: Test — git push with no checklist exits 2**

```bash
ssh alphons@192.168.0.218 'echo "{\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"git push origin feature-branch\"},\"cwd\":\"/home/alphons/drupal/CONTRIB_WORKBENCH\"}" | bash /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/hooks/push-gate.sh 2>/tmp/push-stderr.txt; echo "exit=$?"; cat /tmp/push-stderr.txt; rm /tmp/push-stderr.txt'
```
Expected: `exit=2`, stderr contains "BLOCKED: No push-gate checklist found".

- [ ] **Step 6: Test — git push with clean checklist exits 0**

Create a synthetic checklist, then test:

```bash
ssh alphons@192.168.0.218 'mkdir -p /home/alphons/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/99999/workflow && jq -n "{ci_parity_exit_code:0,phpunit_passed:true,depth_gate_decision:\"SKIP\",spec_reviewer_verdict:\"SPEC_COMPLIANT\",reviewer_verdict:\"APPROVED\",verifier_verdict:\"VERIFIED\",timestamp:\"$(date -Iseconds)\",issue_id:\"99999\"}" > /home/alphons/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/99999/workflow/03-push-gate-checklist.json && echo "{\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"git push origin feature-branch\"},\"cwd\":\"/home/alphons/drupal/CONTRIB_WORKBENCH\"}" | bash /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/hooks/push-gate.sh; echo "exit=$?"'
```
Expected: `exit=0` (clean checklist, push allowed).

- [ ] **Step 7: Test — git push with NEEDS_WORK verdict exits 2**

```bash
ssh alphons@192.168.0.218 'jq ".reviewer_verdict = \"NEEDS_WORK\"" /home/alphons/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/99999/workflow/03-push-gate-checklist.json > /tmp/c.json && mv /tmp/c.json /home/alphons/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/99999/workflow/03-push-gate-checklist.json && echo "{\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"git push origin feature-branch\"},\"cwd\":\"/home/alphons/drupal/CONTRIB_WORKBENCH\"}" | bash /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/hooks/push-gate.sh 2>/tmp/push-stderr.txt; echo "exit=$?"; cat /tmp/push-stderr.txt; rm /tmp/push-stderr.txt'
```
Expected: `exit=2`, stderr contains "BLOCKED: Push-gate checklist has failing checks" + "reviewer_verdict=NEEDS_WORK".

---

### Task 2: Create `.claude/hooks/workflow-completion.sh`

**Files:**
- Create: `.claude/hooks/workflow-completion.sh`

- [ ] **Step 1: Write the script and deploy**

Write via scp, chmod +x, syntax check.

- [ ] **Step 2: Test — no review summary exits 0 (not in fix flow)**

```bash
ssh alphons@192.168.0.218 'echo "{\"cwd\":\"/home/alphons/drupal/CONTRIB_WORKBENCH\"}" | bash /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/hooks/workflow-completion.sh; echo "exit=$?"'
```
Expected: `exit=0` (no recent review summary, not in a fix flow).

- [ ] **Step 3: Test — review exists + no checklist exits 2 (mid-fix block)**

Create a fresh review summary without a checklist:

```bash
ssh alphons@192.168.0.218 'mkdir -p /home/alphons/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/99999/workflow && echo "{\"status\":\"done\"}" > /home/alphons/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/99999/workflow/01-review-summary.json && rm -f /home/alphons/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/99999/workflow/03-push-gate-checklist.json && echo "{\"cwd\":\"/home/alphons/drupal/CONTRIB_WORKBENCH\"}" | bash /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/hooks/workflow-completion.sh 2>/tmp/stop-stderr.txt; echo "exit=$?"; cat /tmp/stop-stderr.txt; rm /tmp/stop-stderr.txt'
```
Expected: `exit=2`, stderr contains "BLOCKED: Review completed for issue 99999 but push-gate checklist is missing."

- [ ] **Step 4: Test — review exists + checklist exists exits 0 (complete)**

```bash
ssh alphons@192.168.0.218 'jq -n "{ci_parity_exit_code:0,phpunit_passed:true,depth_gate_decision:\"SKIP\",spec_reviewer_verdict:\"SPEC_COMPLIANT\",reviewer_verdict:\"APPROVED\",verifier_verdict:\"VERIFIED\",timestamp:\"$(date -Iseconds)\",issue_id:\"99999\"}" > /home/alphons/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/99999/workflow/03-push-gate-checklist.json && echo "{\"cwd\":\"/home/alphons/drupal/CONTRIB_WORKBENCH\"}" | bash /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/hooks/workflow-completion.sh; echo "exit=$?"'
```
Expected: `exit=0` (workflow complete, stop allowed).

- [ ] **Step 5: Clean up synthetic test dir**

```bash
ssh alphons@192.168.0.218 'rm -rf /home/alphons/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/99999'
```

---

## Phase B — Settings integration

### Task 3: Update `.claude/settings.json`

**Files:**
- Modify: `.claude/settings.json`

- [ ] **Step 1: Read current settings**

```bash
ssh alphons@192.168.0.218 'cat /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/settings.json'
```

- [ ] **Step 2: Add PreToolUse and Stop entries**

Use python to merge the new hooks into the existing JSON:

```python
# read existing, add new hook entries, write back
```

- [ ] **Step 3: Verify settings.json is valid JSON and has all 4 hook events**

```bash
ssh alphons@192.168.0.218 'jq "." /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/settings.json > /dev/null && echo "valid json" && jq ".hooks | keys" /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/settings.json'
```
Expected: `["PreCompact", "PreToolUse", "SessionStart", "Stop"]` (4 events).

---

## Phase C — SKILL.md Step 5.5

### Task 4: Add Step 5.5 to `/drupal-contribute-fix`

**Files:**
- Modify: `.claude/skills/drupal-contribute-fix/SKILL.md`

- [ ] **Step 1: Read the current Step 5 / Step 6 boundary**

Find the exact insertion point between "Step 5: Verifier Agent" and "Step 6: Draft Issue Comment".

- [ ] **Step 2: Insert Step 5.5**

Use python replacement to insert the new step.

- [ ] **Step 3: Verify insertion**

```bash
ssh alphons@192.168.0.218 'grep -n "Step 5.5" /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-contribute-fix/SKILL.md'
```
Expected: exactly one match for "Step 5.5: Write push-gate checklist".

---

## Phase D — Documentation

### Task 5: Update `docs/workflow-state-files.md`

**Files:**
- Modify: `docs/workflow-state-files.md`

- [ ] **Step 1: Add `03-push-gate-checklist.json` row to registry table**

Insert after the `attempt.json` row:

```
| `03-push-gate-checklist.json` | `/drupal-contribute-fix` Step 5.5 | (no status; verdicts checked by hooks) | `.claude/hooks/push-gate.sh` + `.claude/hooks/workflow-completion.sh` | 039 |
```

- [ ] **Step 2: Verify row count increased by 1**

```bash
ssh alphons@192.168.0.218 'grep -c "^|" /home/alphons/drupal/CONTRIB_WORKBENCH/docs/workflow-state-files.md'
```

---

### Task 6: Update `docs/bd-schema.md`

**Files:**
- Modify: `docs/bd-schema.md`

- [ ] **Step 1: Add 3 new phase notation rows**

Insert after existing `bd:phase.solution_depth.attempt_2_start` row:

```
| `bd:phase.push_gate.<nid>` | Stop hook | Push gate reached, includes verdicts |
| `bd:phase.session_incomplete.<nid>` | Stop hook | Session ended before push gate |
| `bd:phase.push_gate.blocked.<nid>` | PreToolUse hook | Premature push blocked |
```

---

### Task 7: Add CLAUDE.md subsection

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Find insertion anchor**

Insert new "Mechanical enforcement hooks" section near the "Orphaned DDEV cleanup" section added in 032.

- [ ] **Step 2: Insert subsection**

---

### Task 8: Create ticket file + status flip + Resolution note

**Files:**
- Create: `docs/tickets/039-mechanical-enforcement-hooks.md`
- Modify: `docs/tickets/00-INDEX.md`

- [ ] **Step 1: Add 039 row to index**

Insert after 038 row:

```
| 039 | Mechanical enforcement hooks + bd session progress       | P1 | COMPLETED   | Enhancement  | 033        |
```

- [ ] **Step 2: Create ticket file with resolution**

---

### Task 9: bd writes integration test

**Files:** None (verification only)

- [ ] **Step 1: Create synthetic test fixtures**

```bash
ssh alphons@192.168.0.218 'mkdir -p /home/alphons/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/99999/workflow'
```

- [ ] **Step 2: Test push block writes to bd**

Run push-gate.sh with no checklist → should write bd memory. Then check:

```bash
ssh alphons@192.168.0.218 'bd memories push_gate 2>/dev/null || echo "bd not available or no memories"'
```

- [ ] **Step 3: Test stop writes to bd**

Run workflow-completion.sh with both files present → should write bd progress. Check bd memories.

- [ ] **Step 4: Clean up**

Remove synthetic test dir.

---

### Task 10: Final verification + summary

**Files:** None (verification only)

- [ ] **Step 1: Verify all new/modified files**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && git status --short | grep -E "(hooks/|settings.json|contribute-fix|workflow-state|bd-schema|CLAUDE.md|039|00-INDEX)" | sort'
```

- [ ] **Step 2: Verify settings.json loads cleanly**

```bash
ssh alphons@192.168.0.218 'jq "." /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/settings.json > /dev/null && echo "valid"'
```

- [ ] **Step 3: Print summary**
