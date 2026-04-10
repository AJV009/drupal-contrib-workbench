# Ticket 034 — Cross-Issue Long-Term Memory via bd — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create `scripts/bd-helpers.sh` CLI, wire all workflow phases to write to bd via helpers, add PRIOR KNOWLEDGE query to the fetcher, refactor 031/030 inline writes, add maintainer/lore memory system.

**Architecture:** Single bash CLI at `scripts/bd-helpers.sh` with 12 subcommands. Skills call it instead of inline `bd` commands. Fetcher calls `query-prior-knowledge` for cross-issue intelligence.

**Tech Stack:** Bash, jq, bd CLI, ssh to remote.

**Session rule:** NO GIT COMMITS. Skip all git operations.

---

## Phase A — bd-helpers.sh CLI

### Task 1: Create `scripts/bd-helpers.sh` with all subcommands

**Files:**
- Create: `scripts/bd-helpers.sh`

- [ ] **Step 1: Write the full script**

The script has: shebang, PATH setup for bd, a `die()` helper for best-effort errors, and one function per subcommand dispatched via a `case` statement.

- [ ] **Step 2: Deploy, chmod +x, syntax check**

```bash
scp + chmod +x + bash -n + wc -l
```

- [ ] **Step 3: Test `ensure-issue` creates a synthetic bd issue**

```bash
ssh alphons@192.168.0.218 'export PATH="$HOME/go/bin:$PATH" && cd /home/alphons/drupal/CONTRIB_WORKBENCH && BD_ID=$(scripts/bd-helpers.sh ensure-issue 99999 "Test issue 99999") && echo "bd_id=$BD_ID" && bd show "$BD_ID" --json | jq "{id, title, labels, external_refs}"'
```
Expected: non-empty bd_id, title contains "99999", label includes `drupal-99999`.

- [ ] **Step 4: Test `ensure-issue` is idempotent**

```bash
ssh ... 'BD_ID2=$(scripts/bd-helpers.sh ensure-issue 99999 "Test issue 99999") && echo "bd_id2=$BD_ID2"'
```
Expected: same ID as Step 3.

- [ ] **Step 5: Test `phase-classification`**

```bash
ssh ... 'echo "{\"category\":\"A\",\"module\":\"test_mod\"}" > /tmp/cls.json && scripts/bd-helpers.sh phase-classification "$BD_ID" /tmp/cls.json && bd show "$BD_ID" --json | jq .metadata'
```

- [ ] **Step 6: Test `phase-resonance`**

```bash
ssh ... 'echo "resonance report" > /tmp/res.md && scripts/bd-helpers.sh phase-resonance "$BD_ID" /tmp/res.md && bd comments "$BD_ID" 2>/dev/null | head -5'
```

- [ ] **Step 7: Test `phase-review`**

```bash
ssh ... 'echo "{\"findings\":\"test\"}" > /tmp/rev.json && scripts/bd-helpers.sh phase-review "$BD_ID" /tmp/rev.json && bd show "$BD_ID" --json | jq .description | head -3'
```

- [ ] **Step 8: Test `phase-depth-pre`**

```bash
ssh ... 'echo "pre-fix analysis" > /tmp/dpre.md && scripts/bd-helpers.sh phase-depth-pre "$BD_ID" /tmp/dpre.md && bd show "$BD_ID" --json | jq .design | head -3'
```

- [ ] **Step 9: Test `phase-push-gate` (uses `bd note`, appends)**

```bash
ssh ... 'echo "{\"verdicts\":\"all pass\"}" > /tmp/pg.json && scripts/bd-helpers.sh phase-push-gate "$BD_ID" /tmp/pg.json && bd show "$BD_ID" --json | jq .notes | head -5'
```

- [ ] **Step 10: Test `remember-maintainer` and `remember-lore`**

```bash
ssh ... 'scripts/bd-helpers.sh remember-maintainer test_mod marcus "prefers events" && scripts/bd-helpers.sh remember-lore test_mod testing "use kernel tests" && bd memories module.test_mod'
```

- [ ] **Step 11: Test `query-prior-knowledge`**

```bash
ssh ... 'scripts/bd-helpers.sh query-prior-knowledge test_mod'
```
Expected: JSON with `prior_issues` (containing 99999 issue), `maintainer_prefs`, `module_lore`.

- [ ] **Step 12: Test best-effort on bd failure**

```bash
ssh ... 'PATH=/usr/bin:/bin scripts/bd-helpers.sh ensure-issue 88888 "no-bd test" 2>/tmp/bd-err.txt; echo "exit=$?"; cat /tmp/bd-err.txt; rm -f /tmp/bd-err.txt'
```
Expected: exit=0 (best-effort, no crash), stderr mentions failure.

- [ ] **Step 13: Clean up test issue**

```bash
ssh ... 'export PATH="$HOME/go/bin:$PATH" && bd delete "$BD_ID" --force 2>/dev/null; bd forget module.test_mod.maintainer_pref.marcus 2>/dev/null; bd forget module.test_mod.lore.testing 2>/dev/null; rm -f /tmp/cls.json /tmp/res.md /tmp/rev.json /tmp/dpre.md /tmp/pg.json'
```

---

## Phase B — Refactor existing bd writes

### Task 2: Refactor `/drupal-issue` Step 2.5 (031 inline → helpers)

**Files:**
- Modify: `.claude/skills/drupal-issue/SKILL.md`

- [ ] **Step 1: Read the current Step 2.5 bd write block**

Locate the `bd create`/`bd update` block (~lines 450-470).

- [ ] **Step 2: Replace inline bd calls with helper invocations**

Replace the entire bd block with:
```bash
BD_ID=$(scripts/bd-helpers.sh ensure-issue "$ISSUE_ID" "Drupal issue $ISSUE_ID: {issue title}" --module "{module}")
if [[ -n "$BD_ID" ]]; then
  scripts/bd-helpers.sh phase-classification "$BD_ID" "$WORKFLOW_DIR/00-classification.json"
fi
```

- [ ] **Step 3: Verify replacement**

```bash
grep -n "bd create\|bd update\|bd-helpers" <skill file> | head -10
```
Expected: no `bd create`/`bd update` inline calls remain; `bd-helpers` references present.

---

### Task 3: Refactor `/drupal-contribute-fix` failure path (030 inline → helpers)

**Files:**
- Modify: `.claude/skills/drupal-contribute-fix/SKILL.md`

- [ ] **Step 1: Find the failure-path bd comment block**

Locate `bd comment "$BD_ID" "bd:phase.solution_depth.post.failed_revert` (~line 619-625).

- [ ] **Step 2: Replace with helper invocation**

Replace with:
```bash
if [[ -n "$BD_ID" ]]; then
  scripts/bd-helpers.sh phase-depth-post-fail "$BD_ID" \
    "$WORKFLOW_DIR/02b-solution-depth-post.json" \
    "$WORKFLOW_DIR/02c-recovery-brief.md"
fi
```

- [ ] **Step 3: Verify no inline bd commands remain in the failure path**

---

## Phase C — New bd write points

### Task 4: Add resonance bd write to `/drupal-issue` Step 0.5

**Files:**
- Modify: `.claude/skills/drupal-issue/SKILL.md`

- [ ] **Step 1: Find Step 0.5 (resonance checker return)**

- [ ] **Step 2: Add bd write after resonance artifacts are written**

Insert after the resonance checker dispatch returns:
```
**bd write (best-effort):** After the resonance checker writes
`workflow/00-resonance.json`, mirror to bd:

```bash
if [[ -n "$BD_ID" ]] && [[ -f "$WORKFLOW_DIR/00-resonance.json" ]]; then
  scripts/bd-helpers.sh phase-resonance "$BD_ID" "$WORKFLOW_DIR/00-resonance.json"
fi
```
```

---

### Task 5: Add review bd write to `/drupal-issue-review` Step 4.9

**Files:**
- Modify: `.claude/skills/drupal-issue-review/SKILL.md`

- [ ] **Step 1: Find Step 4.9 (emit depth signals)**

- [ ] **Step 2: Add bd write after review summary is written**

Insert after the `01-review-summary.json` write:
```
**bd write (best-effort):** Mirror the review summary to bd:

```bash
BD_ID=$(scripts/bd-helpers.sh ensure-issue "$ISSUE_ID" "Drupal issue $ISSUE_ID" 2>/dev/null)
if [[ -n "$BD_ID" ]] && [[ -f "$WORKFLOW_DIR/01-review-summary.json" ]]; then
  scripts/bd-helpers.sh phase-review "$BD_ID" "$WORKFLOW_DIR/01-review-summary.json"
fi
```
```

---

### Task 6: Add depth-pre + verification + push-gate writes to `/drupal-contribute-fix`

**Files:**
- Modify: `.claude/skills/drupal-contribute-fix/SKILL.md`

- [ ] **Step 1: Add phase-depth-pre after Step 0.5 pre-fix gate**

After the pre-fix gate writes `01b-solution-depth-pre.json`:
```bash
BD_ID=$(scripts/bd-helpers.sh ensure-issue "$ISSUE_ID" "Drupal issue $ISSUE_ID" 2>/dev/null)
if [[ -n "$BD_ID" ]] && [[ -f "$WORKFLOW_DIR/01b-solution-depth-pre.json" ]]; then
  scripts/bd-helpers.sh phase-depth-pre "$BD_ID" "$WORKFLOW_DIR/01b-solution-depth-pre.json"
fi
```

- [ ] **Step 2: Add phase-verification after Step 5 (Verifier Agent)**

After the verifier returns, if there's a structured verification result:
```bash
if [[ -n "$BD_ID" ]]; then
  scripts/bd-helpers.sh phase-verification "$BD_ID" "$WORKFLOW_DIR/03-push-gate-checklist.json"
fi
```

(Uses the push-gate checklist as the verification proxy since there's no
separate `02-verification-results.json` file yet.)

- [ ] **Step 3: Add phase-push-gate after Step 5.5 checklist write**

After writing `03-push-gate-checklist.json`:
```bash
if [[ -n "$BD_ID" ]] && [[ -f "$WORKFLOW_DIR/03-push-gate-checklist.json" ]]; then
  scripts/bd-helpers.sh phase-push-gate "$BD_ID" "$WORKFLOW_DIR/03-push-gate-checklist.json"
fi
```

---

## Phase D — Fetcher enrichment (the read side)

### Task 7: Add PRIOR KNOWLEDGE step to fetcher agent

**Files:**
- Modify: `.claude/agents/drupal-issue-fetcher.md`

- [ ] **Step 1: Read the current fetcher `full` mode structure**

Find where the agent returns after writing artifacts.

- [ ] **Step 2: Insert the PRIOR KNOWLEDGE query step**

Add before the return section:
```markdown
### Step N: Query bd for prior knowledge (best-effort)

After all artifacts are written, query bd for cross-issue intelligence:

```bash
PRIOR=$(scripts/bd-helpers.sh query-prior-knowledge "<module_name>")
if [[ -n "$PRIOR" ]] && [[ "$PRIOR" != "{}" ]]; then
  echo "$PRIOR" > "$OUT_DIR/prior-knowledge.json"
fi
```

Also query for this issue's existing bd state:

```bash
BD_ID=$(scripts/bd-helpers.sh ensure-issue "<issue_id>" "Drupal issue <issue_id>" 2>/dev/null)
if [[ -n "$BD_ID" ]]; then
  bd show "$BD_ID" --json > "$OUT_DIR/bd-issue-state.json" 2>/dev/null || true
fi
```

If bd has no data, these files are not created. Downstream skills should
check for existence but not require them.
```

- [ ] **Step 3: Add the same step to `delta` mode**

The delta mode should also query bd (it's a read, not a fetch).

- [ ] **Step 4: Verify insertion**

```bash
grep -n "prior.knowledge\|query-prior-knowledge\|PRIOR KNOWLEDGE" <fetcher file>
```

---

## Phase E — Documentation & closure

### Task 8: Update docs

**Files:**
- Modify: `docs/bd-schema.md` — add maintainer_pref + module_lore patterns
- Modify: `CLAUDE.md` — add "Cross-issue memory" subsection
- Modify: `docs/tickets/034-bd-cross-issue-memory.md` — Resolution note
- Modify: `docs/tickets/00-INDEX.md` — status flip

- [ ] **Step 1: Add memory key patterns to bd-schema.md**
- [ ] **Step 2: Add CLAUDE.md subsection**
- [ ] **Step 3: Flip 034 status + write Resolution**
- [ ] **Step 4: Verify**

---

### Task 9: Final verification

- [ ] **Step 1: Verify all files**

```bash
git status --short | grep -E "(bd-helpers|drupal-issue|contribute-fix|issue-review|issue-fetcher|bd-schema|CLAUDE|034|00-INDEX)"
```

- [ ] **Step 2: Verify bd-helpers.sh is executable and syntax-clean**
- [ ] **Step 3: Print summary**
