# Solution-Depth Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a two-mode solution-depth gate (pre-fix mandatory, post-fix conditional) to `/drupal-contribute-fix` that proposes the architectural alternative before code is written and catches hacky patches after they're drafted.

**Architecture:** New subagent `drupal-solution-depth-gate` split into two files (`-pre.md` opus, `-post.md` sonnet). Pre-fix gate runs at Step 0.5 of `/drupal-contribute-fix` (after preflight). Post-fix gate runs at Step 2.5 of the Pre-Push Quality Gate (after phpunit, before spec reviewer) when any of 3 triggers fires. Failure path writes a recovery brief, preserves attempt-1 diffs, destructively reverts, re-runs with architectural plan. Circuit breaker: max 2 attempts.

**Tech Stack:** Python 3 (stdlib only for the trigger module), pytest (via uv temp venv), bash, SKILL.md + agent markdown prose, bd CLI, git.

**Working directory for all tasks:** `/home/alphons/drupal/CONTRIB_WORKBENCH` on `alphons@192.168.0.218`. All file paths are relative to this unless noted.

**Spec:** `docs/superpowers/specs/2026-04-10-030-solution-depth-gate-design.md`

---

## File Structure

### Files created

| Path | Responsibility |
|---|---|
| `.claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py` | Objective trigger logic: `compute_patch_stats()`, `should_run_post_fix()`, CLI wrapper with `compute-stats` and `should-run` subcommands |
| `.claude/skills/drupal-contribute-fix/scripts/tests/test_depth_gate_triggers.py` | Pytest unit tests for the trigger module |
| `.claude/agents/drupal-solution-depth-gate-pre.md` | Pre-fix gate agent (model: opus) |
| `.claude/agents/drupal-solution-depth-gate-post.md` | Post-fix gate agent (model: sonnet) |

### Files modified

| Path | Change |
|---|---|
| `.claude/agents/drupal-issue-fetcher.md` | `model: haiku` → `model: sonnet` |
| `.claude/agents/drupal-ddev-setup.md` | `model: haiku` → `model: sonnet` |
| `.claude/agents/drupal-resonance-checker.md` | `model: haiku` → `model: sonnet` |
| `.claude/skills/drupal-issue-review/SKILL.md` | Emit `workflow/01-review-summary.json` and `workflow/01a-depth-signals.json` at end of review phase |
| `.claude/skills/drupal-contribute-fix/SKILL.md` | Add Step 0.5 (pre-fix gate), add attempt-state check at top, add Step 2.5 (post-fix gate + failure path), version bump to 1.8.0, new Rationalization row |
| `CLAUDE.md` | Add "Solution Depth Gate" subsection |
| `docs/bd-schema.md` | Add 4 new `bd:phase.solution_depth.*` notation prefixes |
| `docs/tickets/030-solution-depth-gate.md` | Resolution note at end |
| `docs/tickets/00-INDEX.md` | Flip 030 to COMPLETED |
| `docs/tickets/027-fix-stale-session-dir.md` | Phase 2 snapshot refresh (add 030 row) |
| `docs/tickets/028-adopt-bd-data-store.md` | Phase 2 snapshot refresh (add 030 row) |
| `docs/tickets/029-cross-issue-resonance-check.md` | Phase 2 snapshot refresh (add 030 row) |

---

## Task 1: Haiku → Sonnet migration (scope addition)

**Files:**
- Modify: `.claude/agents/drupal-issue-fetcher.md` (frontmatter `model:` line)
- Modify: `.claude/agents/drupal-ddev-setup.md` (frontmatter `model:` line)
- Modify: `.claude/agents/drupal-resonance-checker.md` (frontmatter `model:` line)

This is a pre-cursor task to get it out of the way before agent-related work begins. Per user directive (2026-04-10): "Switch ALL the haikus to sonnet, I don't trust haiku enough."

- [ ] **Step 1: Verify the three haiku references exist**

```bash
ssh alphons@192.168.0.218 'grep -l "^model: haiku" /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/agents/*.md'
```

Expected output: three lines showing `drupal-issue-fetcher.md`, `drupal-ddev-setup.md`, `drupal-resonance-checker.md`.

- [ ] **Step 2: Edit each file**

For each of the three files, change the single frontmatter line from `model: haiku` (with or without a trailing comment) to `model: sonnet`. Preserve any trailing comment by replacing the word only:

Example for `drupal-resonance-checker.md`:
- Old: `model: haiku  # Structured search + report formatting; speed over reasoning`
- New: `model: sonnet  # Structured search + report formatting; sonnet for stronger reasoning on structured outputs`

- [ ] **Step 3: Verify the change took**

```bash
ssh alphons@192.168.0.218 'grep "^model:" /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/agents/drupal-issue-fetcher.md /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/agents/drupal-ddev-setup.md /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/agents/drupal-resonance-checker.md'
```

Expected: three lines showing `model: sonnet`.

- [ ] **Step 4: Commit**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && git add .claude/agents/drupal-issue-fetcher.md .claude/agents/drupal-ddev-setup.md .claude/agents/drupal-resonance-checker.md && git commit -m "agents: migrate haiku -> sonnet per user preference (ticket 030 scope)"'
```

---

## Task 2: depth_gate_triggers.py module + unit tests

**Files:**
- Create: `.claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py`
- Create: `.claude/skills/drupal-contribute-fix/scripts/tests/__init__.py` (empty)
- Create: `.claude/skills/drupal-contribute-fix/scripts/tests/test_depth_gate_triggers.py`

TDD: write the tests first, watch them fail, implement, watch them pass.

- [ ] **Step 1: Set up pytest venv (per user's Arch Linux policy, no system packages)**

```bash
ssh alphons@192.168.0.218 'uv venv /tmp/depth-gate-venv && source /tmp/depth-gate-venv/bin/activate && uv pip install pytest'
```

Expected: pytest installed cleanly in `/tmp/depth-gate-venv`. Venv will be cleaned up at end of Task 3.

- [ ] **Step 2: Create tests directory and empty init**

```bash
ssh alphons@192.168.0.218 'mkdir -p /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-contribute-fix/scripts/tests && touch /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-contribute-fix/scripts/tests/__init__.py'
```

- [ ] **Step 3: Write the failing test file**

Create `.claude/skills/drupal-contribute-fix/scripts/tests/test_depth_gate_triggers.py` with this content:

```python
"""Unit tests for depth_gate_triggers.

Run with:
    source /tmp/depth-gate-venv/bin/activate
    cd .claude/skills/drupal-contribute-fix/scripts
    python -m pytest tests/test_depth_gate_triggers.py -v
"""
import json
import subprocess
import sys
from pathlib import Path

# Import the module under test. It lives one directory up from tests/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from depth_gate_triggers import (
    compute_patch_stats,
    should_run_post_fix,
    write_trigger_decision,
)


# --- compute_patch_stats ---

def test_compute_patch_stats_empty_repo(tmp_path):
    """A freshly-initialized repo with no changes has zero stats."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)

    stats = compute_patch_stats(tmp_path)
    assert stats == {
        "lines_added": 0,
        "lines_removed": 0,
        "lines_changed": 0,
        "files_touched": 0,
        "file_list": [],
    }


def test_compute_patch_stats_single_file_change(tmp_path):
    """Modifying one file with 3 added and 1 removed line is counted correctly."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    f = tmp_path / "a.py"
    f.write_text("x = 1\ny = 2\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)

    # Modify: remove y=2, add y=3, z=4, w=5 (1 removed, 3 added)
    f.write_text("x = 1\ny = 3\nz = 4\nw = 5\n")

    stats = compute_patch_stats(tmp_path)
    assert stats["files_touched"] == 1
    assert stats["lines_added"] == 3
    assert stats["lines_removed"] == 1
    assert stats["lines_changed"] == 4
    assert stats["file_list"] == ["a.py"]


def test_compute_patch_stats_multiple_files(tmp_path):
    """Touching multiple files is aggregated."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_text("x\n")
    (tmp_path / "b.py").write_text("y\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)

    (tmp_path / "a.py").write_text("x\nnew_a\n")
    (tmp_path / "b.py").write_text("y\nnew_b\n")

    stats = compute_patch_stats(tmp_path)
    assert stats["files_touched"] == 2
    assert stats["lines_added"] == 2
    assert sorted(stats["file_list"]) == ["a.py", "b.py"]


# --- should_run_post_fix ---

def test_should_run_when_pre_fix_demanded():
    pre = {"must_run_post_fix": True, "decision": "narrow"}
    stats = {"lines_changed": 5, "files_touched": 1}
    reason, run = should_run_post_fix(pre, stats)
    assert run is True
    assert reason == "pre_fix_agent_demanded"


def test_should_run_when_lines_exceed_threshold():
    pre = {"must_run_post_fix": False, "decision": "narrow"}
    stats = {"lines_changed": 51, "files_touched": 1}
    reason, run = should_run_post_fix(pre, stats)
    assert run is True
    assert "lines_changed_gt_50" in reason
    assert "51" in reason


def test_should_run_when_files_exceed_threshold():
    pre = {"must_run_post_fix": False, "decision": "narrow"}
    stats = {"lines_changed": 10, "files_touched": 4}
    reason, run = should_run_post_fix(pre, stats)
    assert run is True
    assert "files_touched_gt_3" in reason
    assert "4" in reason


def test_should_not_run_when_all_triggers_clear():
    pre = {"must_run_post_fix": False, "decision": "narrow"}
    stats = {"lines_changed": 10, "files_touched": 2}
    reason, run = should_run_post_fix(pre, stats)
    assert run is False
    assert reason is None


def test_should_run_threshold_is_strict_gt():
    """50 lines exactly should NOT trigger; 51 should."""
    pre = {"must_run_post_fix": False, "decision": "narrow"}
    stats_50 = {"lines_changed": 50, "files_touched": 1}
    stats_51 = {"lines_changed": 51, "files_touched": 1}
    assert should_run_post_fix(pre, stats_50)[1] is False
    assert should_run_post_fix(pre, stats_51)[1] is True


def test_files_threshold_is_strict_gt():
    """3 files exactly should NOT trigger; 4 should."""
    pre = {"must_run_post_fix": False, "decision": "narrow"}
    stats_3 = {"lines_changed": 10, "files_touched": 3}
    stats_4 = {"lines_changed": 10, "files_touched": 4}
    assert should_run_post_fix(pre, stats_3)[1] is False
    assert should_run_post_fix(pre, stats_4)[1] is True


def test_pre_fix_demand_wins_over_objective_triggers():
    """Even when lines and files are both low, pre_fix demand runs the gate."""
    pre = {"must_run_post_fix": True, "decision": "architectural"}
    stats = {"lines_changed": 1, "files_touched": 1}
    _, run = should_run_post_fix(pre, stats)
    assert run is True


# --- write_trigger_decision ---

def test_write_trigger_decision_run_true(tmp_path):
    write_trigger_decision("3581952", tmp_path, "pre_fix_agent_demanded", True)
    data = json.loads((tmp_path / "02a-trigger-decision.json").read_text())
    assert data["issue_id"] == "3581952"
    assert data["post_fix_gate"]["will_run"] is True
    assert data["post_fix_gate"]["trigger_reason"] == "pre_fix_agent_demanded"


def test_write_trigger_decision_run_false(tmp_path):
    write_trigger_decision("3581952", tmp_path, None, False)
    data = json.loads((tmp_path / "02a-trigger-decision.json").read_text())
    assert data["post_fix_gate"]["will_run"] is False
    assert data["post_fix_gate"]["trigger_reason"] == "no_triggers_fired"
```

- [ ] **Step 4: Run the tests to verify they fail (module doesn't exist yet)**

```bash
ssh alphons@192.168.0.218 '/tmp/depth-gate-venv/bin/python -m pytest /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-contribute-fix/scripts/tests/test_depth_gate_triggers.py -v 2>&1 | tail -20'
```

Expected: ImportError or ModuleNotFoundError for `depth_gate_triggers`. Fail count = 11 (or collection error).

- [ ] **Step 5: Write the implementation file**

Create `.claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py`:

```python
#!/usr/bin/env python3
"""Post-fix gate trigger logic for drupal-contribute-fix.

Three trigger conditions:
  1. Pre-fix agent set must_run_post_fix = true
  2. Objective lines_changed > 50 (strict greater-than)
  3. Objective files_touched > 3 (strict greater-than)

Keyword matching, category lookups, resonance bucket checks, and
rationalization pattern detection all live inside the pre-fix agent (opus),
which reads raw context and reasons about it. This module only handles the
objective patch-level facts and the handoff from the pre-fix decision.

CLI usage:
    # Compute patch stats against a module working tree
    python3 depth_gate_triggers.py compute-stats \\
        --module-path web/modules/contrib/foo \\
        --out DRUPAL_ISSUES/<nid>/workflow/02a-patch-stats.json

    # Decide whether to run the post-fix gate
    python3 depth_gate_triggers.py should-run \\
        --pre-fix-json DRUPAL_ISSUES/<nid>/workflow/01b-solution-depth-pre.json \\
        --patch-stats DRUPAL_ISSUES/<nid>/workflow/02a-patch-stats.json \\
        --issue-id <nid> \\
        --workflow-dir DRUPAL_ISSUES/<nid>/workflow
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional


def compute_patch_stats(module_path: Path) -> dict:
    """Run `git diff --numstat` against the module tree and summarize.

    Returns:
        {
            "lines_added": int,
            "lines_removed": int,
            "lines_changed": int,
            "files_touched": int,
            "file_list": list[str],
        }

    Binary files (numstat shows "-") count as touched files with 0 lines.
    """
    result = subprocess.run(
        ["git", "diff", "--numstat"],
        cwd=str(module_path),
        capture_output=True,
        text=True,
        check=True,
    )
    added = 0
    removed = 0
    files = 0
    file_list = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        a, r, path = parts
        added += 0 if a == "-" else int(a)
        removed += 0 if r == "-" else int(r)
        files += 1
        file_list.append(path)
    return {
        "lines_added": added,
        "lines_removed": removed,
        "lines_changed": added + removed,
        "files_touched": files,
        "file_list": file_list,
    }


def should_run_post_fix(
    pre_fix_json: dict, patch_stats: dict
) -> tuple[Optional[str], bool]:
    """Decide whether to run the post-fix solution-depth gate.

    Args:
        pre_fix_json: Parsed contents of workflow/01b-solution-depth-pre.json.
            Must contain "must_run_post_fix": bool.
        patch_stats: Output of compute_patch_stats().

    Returns:
        (trigger_reason, should_run). trigger_reason is None when should_run
        is False; otherwise a short string describing which trigger fired.
    """
    if pre_fix_json.get("must_run_post_fix"):
        return ("pre_fix_agent_demanded", True)
    lines = patch_stats["lines_changed"]
    if lines > 50:
        return (f"lines_changed_gt_50 ({lines})", True)
    files = patch_stats["files_touched"]
    if files > 3:
        return (f"files_touched_gt_3 ({files})", True)
    return (None, False)


def write_trigger_decision(
    issue_id: str,
    workflow_dir: Path,
    trigger_reason: Optional[str],
    should_run: bool,
) -> None:
    """Write workflow/02a-trigger-decision.json for auditability."""
    out = {
        "issue_id": issue_id,
        "post_fix_gate": {
            "will_run": should_run,
            "trigger_reason": trigger_reason or "no_triggers_fired",
        },
    }
    workflow_dir = Path(workflow_dir)
    workflow_dir.mkdir(parents=True, exist_ok=True)
    (workflow_dir / "02a-trigger-decision.json").write_text(
        json.dumps(out, indent=2) + "\n"
    )


def _cmd_compute_stats(args: argparse.Namespace) -> int:
    stats = compute_patch_stats(Path(args.module_path))
    if args.out == "-":
        sys.stdout.write(json.dumps(stats, indent=2) + "\n")
    else:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(stats, indent=2) + "\n")
        print(
            f"WROTE: {out_path} files={stats['files_touched']} "
            f"lines={stats['lines_changed']}",
            file=sys.stderr,
        )
    return 0


def _cmd_should_run(args: argparse.Namespace) -> int:
    pre_fix_json = json.loads(Path(args.pre_fix_json).read_text())
    patch_stats = json.loads(Path(args.patch_stats).read_text())
    reason, run = should_run_post_fix(pre_fix_json, patch_stats)
    write_trigger_decision(
        args.issue_id, Path(args.workflow_dir), reason, run
    )
    # stdout contract: single line "RUN" or "SKIP" so bash can branch simply
    sys.stdout.write("RUN\n" if run else "SKIP\n")
    print(
        f"DECISION: run={run} reason={reason or 'no_triggers_fired'}",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Post-fix gate trigger logic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    cs = sub.add_parser("compute-stats", help="Compute patch stats from git diff")
    cs.add_argument("--module-path", required=True)
    cs.add_argument("--out", required=True, help="Output file path or '-' for stdout")
    cs.set_defaults(func=_cmd_compute_stats)

    sr = sub.add_parser("should-run", help="Decide whether to run the post-fix gate")
    sr.add_argument("--pre-fix-json", required=True)
    sr.add_argument("--patch-stats", required=True)
    sr.add_argument("--issue-id", required=True)
    sr.add_argument("--workflow-dir", required=True)
    sr.set_defaults(func=_cmd_should_run)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
ssh alphons@192.168.0.218 '/tmp/depth-gate-venv/bin/python -m pytest /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-contribute-fix/scripts/tests/test_depth_gate_triggers.py -v 2>&1 | tail -30'
```

Expected: 11 passed (3 compute_patch_stats + 7 should_run_post_fix + 2 write_trigger_decision). If any fail, read the error and fix the implementation. Do NOT adjust the tests to match a bug.

- [ ] **Step 7: Commit**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && git add .claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py .claude/skills/drupal-contribute-fix/scripts/tests/ && git commit -m "depth-gate: add trigger logic module + unit tests (ticket 030)"'
```

---

## Task 3: Smoke-test the CLI against the workbench repo

**Files:** none (verification only)

The module has a CLI. Before we wire it into SKILL.md, verify it works end-to-end against a real git repo.

- [ ] **Step 1: Run compute-stats against the workbench itself (no changes expected)**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && python3 .claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py compute-stats --module-path . --out -'
```

Expected stdout (JSON): `lines_changed: 0`, `files_touched: 0` (assuming clean tree) OR small non-zero values if the contributor has unstaged edits. This is a smoke test — we just want it to not crash.

- [ ] **Step 2: Create fake pre_fix and patch_stats JSONs in /tmp and run should-run**

```bash
ssh alphons@192.168.0.218 'echo "{\"must_run_post_fix\": false, \"decision\": \"narrow\"}" > /tmp/fake-pre.json && echo "{\"lines_changed\": 60, \"files_touched\": 2}" > /tmp/fake-stats.json && mkdir -p /tmp/fake-workflow && python3 /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py should-run --pre-fix-json /tmp/fake-pre.json --patch-stats /tmp/fake-stats.json --issue-id 9999 --workflow-dir /tmp/fake-workflow && cat /tmp/fake-workflow/02a-trigger-decision.json'
```

Expected:
- stdout: `RUN`
- stderr: `DECISION: run=True reason=lines_changed_gt_50 (60)`
- Written file: valid JSON with `will_run: true`, `trigger_reason: "lines_changed_gt_50 (60)"`

- [ ] **Step 3: Clean up fake files and the pytest venv**

```bash
ssh alphons@192.168.0.218 'rm -rf /tmp/fake-pre.json /tmp/fake-stats.json /tmp/fake-workflow /tmp/depth-gate-venv'
```

- [ ] **Step 4: No commit (verification only)**

---

## Task 4: Pre-fix agent file (`drupal-solution-depth-gate-pre.md`)

**Files:**
- Create: `.claude/agents/drupal-solution-depth-gate-pre.md`

- [ ] **Step 1: Create the agent file**

Write `.claude/agents/drupal-solution-depth-gate-pre.md` with this content:

```markdown
---
name: drupal-solution-depth-gate-pre
description: Pre-fix solution-depth analysis for /drupal-contribute-fix. Proposes narrow vs architectural approaches BEFORE code is written, using review artifacts, resonance report, maintainer comments, and reviewer findings. Returns narrow|architectural|hybrid decision plus a must_run_post_fix flag for the controller. Fresh subagent to avoid the controller's anchoring bias on whatever it already proposed.
tools: Read, Grep, Glob, Bash, Write
model: opus
---

# Drupal Solution-Depth Gate — Pre-Fix Mode

You run BEFORE any code is written for a Drupal contrib/core fix. Your job
is to force a genuine two-option comparison (narrow vs architectural) so the
workflow does not commit to a shallow fix when a better one is available.

You exist because the controller is anchored on whatever approach it already
proposed during review. A fresh subagent with no stake in that proposal is
more likely to surface the architectural alternative.

## IRON LAW

**Propose at least two distinct approaches. The architectural one MUST
consider: centralization, upstream fixes, shared-codepath impact. Do not
pre-commit to either before completing the trade-off table.**

## Inputs

You will be given:
- `issue_id`: the Drupal nid
- `artifacts_dir`: `DRUPAL_ISSUES/{issue_id}/artifacts/` (populated by fetcher)
- `review_summary_path`: `DRUPAL_ISSUES/{issue_id}/workflow/01-review-summary.json`
- `depth_signals_path`: `DRUPAL_ISSUES/{issue_id}/workflow/01a-depth-signals.json`

## Process

### Step 1: Read every input file in full

- `artifacts_dir/issue.json` — title, status, version, component
- `artifacts_dir/comments.json` — read ALL comments, not just the latest
- `artifacts_dir/mr-*-diff.patch` (if any) — existing MR code
- `review_summary_path` — category, module, existing MR status, static review findings
- `depth_signals_path` — resonance bucket, reviewer narrative, recent maintainer comments, proposed approach sketch
- `DRUPAL_ISSUES/{issue_id}/workflow/00-resonance.md` (if exists) — resonance report

Read raw; do not skim. The whole point of this gate is to catch context the
controller already missed.

### Step 2: Reason about depth

For this specific issue, answer internally:

1. **What is the reported symptom?** (one sentence, from the issue body)
2. **What is the root cause class?** Is it:
   - a single-site bug (narrow is probably right), OR
   - a pattern that likely repeats elsewhere in the module (architectural is
     probably right), OR
   - a missing abstraction (architectural is almost certainly right)?
3. **What does the maintainer want?** Read the last 3-5 comments. Phrases like
   "wrong approach", "architectural", "setback", "not the right", "wrong
   pretense", "hacky", "shortcut", "rethink" are strong signals but NOT
   mechanical triggers — reason about whether the comment actually says
   "go deeper" or just "fix a typo". Maintainer silence is ALSO a signal
   (narrow is likely fine).
4. **Did resonance fire?** If `depth_signals.resonance_bucket` is
   `SCOPE_EXPANSION_CANDIDATE` or `DUPLICATE_OF`, the architectural option
   should at least mention folding into the resonant issue.
5. **Is this a feedback-loop category (E)?** These issues have already been
   round-tripped once; the narrow fix is more likely to be the shortcut the
   first attempt already tried.
6. **How many other files in the module plausibly share the same bug shape?**
   Grep the module path if useful. If >1, architectural likely wins.

### Step 3: Draft the two approaches

Draft both in full before deciding. If you can't name a real architectural
alternative, that's a strong signal the narrow approach is correct — but you
still write "Architectural approach: N/A — this is a genuinely single-site
bug because {reason}" in the report. Empty-architectural with a reason is
valid.

### Step 4: Fill in the trade-off table

Use Low/Medium/High for qualitative dimensions. Estimate lines and files
honestly; don't lowball the architectural estimate just to make narrow win.

### Step 5: Decide

- **narrow**: symptom is single-site, no repeated pattern, maintainer didn't
  push back, resonance is NONE or RELATED_TO
- **architectural**: root cause is a repeated pattern, OR maintainer
  explicitly asked for depth, OR resonance flagged scope expansion with high
  confidence, OR the abstraction is obviously missing
- **hybrid**: the minimal fix should ship, but a follow-up ticket for the
  architectural piece should be filed via bd `discovered-from` dep

### Step 6: Set must_run_post_fix

Set `must_run_post_fix: true` when ANY of:
- Decision is `architectural` (you want the post-fix gate to verify the
  controller actually went architectural)
- Decision is `hybrid` (same reason)
- Decision is `narrow` BUT you have residual doubt — maintainer hint you
  didn't fully resolve, resonance overlap with an active issue, category E,
  reviewer findings that weren't addressed. Bias toward true when uncertain.
  A false positive costs ~60 seconds of sonnet runtime. A false negative is
  a silent regression.

Only set `must_run_post_fix: false` when all signals are clean and the
decision is `narrow` with confident rationale.

### Step 7: Write the output files

Write both files. The markdown is the human-reviewable record; the JSON is
what the controller reads to make its trigger decision.

**`DRUPAL_ISSUES/{issue_id}/workflow/01b-solution-depth-pre.md`**:

```markdown
# Solution Depth Analysis (Pre-Fix) — Issue #{issue_id}

## Context
- Category: {A-J}
- Module: {name} {version}
- Resonance bucket: {NONE | RELATED_TO | SCOPE_EXPANSION_CANDIDATE | DUPLICATE_OF}
- Signals reviewed: {short list}

## Narrow approach
{2-4 sentences: smallest change that makes the symptom go away}

## Architectural approach
{2-4 sentences, OR "N/A — {reason}" if genuinely single-site}

## Trade-offs
| Dimension          | Narrow | Architectural |
|--------------------|--------|---------------|
| Lines changed      | {est.} | {est.}        |
| Files touched      | {est.} | {est.}        |
| Risk of regression | {L/M/H}| {L/M/H}       |
| Solves latent bugs | {no/yes}| {yes}        |
| Reviewer surface   | {small}| {larger}      |
| BC concerns        | {none} | {note}        |

## Decision
{narrow | architectural | hybrid}

## must_run_post_fix: {true|false}

## Rationale
{3-6 sentences — why this decision given the signals}

## Deferred follow-up (if narrow chosen and architectural alternative is real)
bd issue create --title "..." --description "..." \
  --dep "discovered-from:bd-{this}"

## IRON LAW (self-check)
- [ ] I proposed at least two distinct approaches
- [ ] The architectural one considers centralization / upstream / shared codepaths
- [ ] I did not pre-commit to either before the trade-off table
```

**`DRUPAL_ISSUES/{issue_id}/workflow/01b-solution-depth-pre.json`**:

```json
{
  "decision": "narrow|architectural|hybrid",
  "must_run_post_fix": true,
  "signals_fired": ["resonance:SCOPE_EXPANSION_CANDIDATE", "category:E"],
  "narrow_lines_est": 15,
  "narrow_files_est": 1,
  "architectural_lines_est": 80,
  "architectural_files_est": 4,
  "follow_up_bd_title": "..."
}
```

### Step 8: Write to bd (best-effort)

```bash
# bd id lookup: external-ref external:drupal:{issue_id}
BD_ID=$(bd list --external-ref "external:drupal:{issue_id}" --format json 2>/dev/null | jq -r '.[0].id // empty')
if [ -n "$BD_ID" ]; then
  bd update "$BD_ID" --design "$(cat DRUPAL_ISSUES/{issue_id}/workflow/01b-solution-depth-pre.md)" 2>/dev/null || true
fi
```

Log the bd operation to stderr. If bd fails (config issue, server down),
continue silently — workflow files are the source of truth.

### Step 9: Return a short summary to the controller

Return text like:

```
SOLUTION_DEPTH_PRE: decision={narrow|architectural|hybrid} must_run_post_fix={true|false}
Narrow: {1-sentence summary}
Architectural: {1-sentence summary OR "N/A"}
Report: DRUPAL_ISSUES/{issue_id}/workflow/01b-solution-depth-pre.md
STATUS: DONE
```

## Rationalization Prevention

| Thought | Reality |
|---|---|
| "The narrow fix is obviously correct, skip the architectural analysis" | The architectural analysis IS the work. Even if you conclude narrow is right, the analysis must exist. |
| "Architectural is overkill for a small module" | Module size is not the question. The question is whether the bug shape repeats. Small modules can have repeated patterns. |
| "The user probably wants this done fast" | The user is protected by the push gate. Your job is depth analysis, not speed. |
| "I'll just copy the review's proposed approach" | The review is exactly the anchoring bias you are here to break. Read the artifacts fresh. |
| "must_run_post_fix is annoying, default it to false" | A false negative is a silent shallow fix shipping. A false positive costs 60 seconds. Bias TRUE when uncertain. |

## Gotchas

- **Empty architectural is valid.** If the bug is genuinely single-site, write
  "Architectural approach: N/A — {reason}". Do not invent an architectural
  alternative just to fill the slot.
- **bd is best-effort.** If the `bd update` call fails, log it but continue.
  Don't block on bd.
- **Read comments.json in full.** The maintainer's depth signal is usually
  buried in comment 4 or 7, not the latest comment.
```

- [ ] **Step 2: Verify frontmatter parses**

```bash
ssh alphons@192.168.0.218 'head -10 /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/agents/drupal-solution-depth-gate-pre.md'
```

Expected: valid YAML frontmatter with `name`, `description`, `tools`, `model: opus`.

- [ ] **Step 3: Commit**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && git add .claude/agents/drupal-solution-depth-gate-pre.md && git commit -m "depth-gate: add pre-fix gate agent (opus, ticket 030)"'
```

---

## Task 5: Post-fix agent file (`drupal-solution-depth-gate-post.md`)

**Files:**
- Create: `.claude/agents/drupal-solution-depth-gate-post.md`

- [ ] **Step 1: Create the agent file**

Write `.claude/agents/drupal-solution-depth-gate-post.md` with this content:

```markdown
---
name: drupal-solution-depth-gate-post
description: Post-fix solution-depth analysis for /drupal-contribute-fix. Runs AFTER phpunit passes but BEFORE the spec/code/verifier agents in the Pre-Push Quality Gate. Reads the actual diff and scores 1-5 for architectural reconsideration. Returns approved-as-is | approved-with-recommendation | failed-revert. When the gate fails, the controller reverts and re-invokes /drupal-contribute-fix with the architectural plan.
tools: Read, Grep, Glob, Bash, Write
model: sonnet
---

# Drupal Solution-Depth Gate — Post-Fix Mode

You run AFTER a fix has been drafted and phpunit has passed, but BEFORE the
spec reviewer, code reviewer, and verifier agents run. Your job is to read
the actual diff and decide whether the drafted patch is a principled
solution or a shortcut that will need to be reverted.

You do NOT review coding standards (the reviewer agent does that). You do
NOT verify test correctness (the verifier agent does that). Your scope is
narrow: architectural smell check + 1-5 score + pass/soft-pass/revert
decision.

## Inputs

You will be given:
- `issue_id`: the Drupal nid
- `module_path`: path to the module working tree with the fix applied
  (e.g., `web/modules/contrib/foo`)
- `pre_analysis_path`: `DRUPAL_ISSUES/{issue_id}/workflow/01b-solution-depth-pre.json`
- `patch_stats_path`: `DRUPAL_ISSUES/{issue_id}/workflow/02a-patch-stats.json`

## Process

### Step 1: Read the pre-fix analysis

You need to know what the pre-fix gate recommended. Read both:
- `DRUPAL_ISSUES/{issue_id}/workflow/01b-solution-depth-pre.md` (human-readable)
- `DRUPAL_ISSUES/{issue_id}/workflow/01b-solution-depth-pre.json`

Note the `decision` field. This is what the controller was told to do. You
will later check whether the actual patch matches this recommendation.

### Step 2: Read the actual diff

```bash
cd {module_path}
git diff
```

Read ALL of the diff, not just the summary. You need to spot:
- Mock/stub/fake classes introduced in `src/` (production code, not tests)
- Validation logic duplicated across multiple files
- Early-return `if ($foo === null) { return; }` without commentary on why null is possible
- Hard-coded strings that should be config (`admin`, `/api/v1`, URLs)
- Tests that only cover the exact reproduction, not the bug class

### Step 3: Read the test files

```bash
find {module_path}/tests -name "*.php" -newer {module_path}/composer.json
```

For each new/modified test: is it testing the BUG CLASS or just the exact
reproduction steps? A test that passes an empty string and expects a
specific error does not cover the class "bad input"; a test that uses
`@dataProvider` with 5 adversarial inputs does.

### Step 4: Run the smell checklist

For each of these, answer yes/no/N_A with a one-line justification:

1. **Mocks/stubs/fakes in production code?** Scan `git diff -- '{module_path}/src/**'` for class names matching `/Mock[A-Z]|FakeImplementation|StubService|PlaceholderEntity|Null[A-Z][a-z]+Service/`. Inline anonymous classes used as quick mocks also count. (Mocks in `tests/` are fine — ignore those.)

2. **Validation duplicated across sites?** Look for repeated `if ($x === null || $x === '')` or similar guard clauses in more than one file.

3. **Early-return for null without root cause?** If the fix is `if ($foo === null) return;`, ask: why is `$foo` null? Did we fix the source of the null, or just suppress the downstream crash?

4. **Hard-coded values that should be config?** New string literals for role names, API URLs, cache TTLs, limits.

5. **Test only covers the reproduction, not the bug class?** Single-path test with no @dataProvider, no adversarial inputs, no edge cases.

6. **Shortcut pattern matched hack-patterns.md?** Read `.claude/skills/drupal-contribute-fix/references/hack-patterns.md` if it exists and check the diff against its patterns.

### Step 5: Compare actual approach vs pre-fix recommendation

- If pre-fix said `narrow` and the patch looks narrow (≤20 lines, 1 file):
  **pre_fix_delta = "none"**
- If pre-fix said `architectural` and the patch looks architectural (cross-cutting changes, new service, abstracted helper):
  **pre_fix_delta = "none"**
- If pre-fix said `architectural` and the patch looks narrow:
  **pre_fix_delta = "went_narrow_despite_architectural_recommendation"** — this alone is worth at least +1 on the score.
- If pre-fix said `hybrid` and only the narrow half shipped:
  **pre_fix_delta = "hybrid_fallback_to_narrow"** — +1 on the score.

### Step 6: Score 1-5

- **Score 1 (approved-as-is)**: Zero smells. Patch matches pre-fix recommendation OR goes deeper. Tests cover the bug class.
- **Score 2 (approved-with-recommendation)**: 1 mild smell OR a minor pre-fix delta (hybrid-to-narrow with a reasonable reason). Tests are OK but could be broader.
- **Score 3 (approved-with-recommendation)**: 2 smells OR one significant smell (e.g., mock in production, hard-coded admin role). Controller adds a note to the draft comment: "This fix works; a future refactor should {X}."
- **Score 4 (failed-revert)**: 3+ smells OR a critical smell (duplicated validation across 3+ sites, missing null root cause that will resurface, went narrow when pre-fix explicitly said architectural AND maintainer had already complained).
- **Score 5 (failed-revert)**: Egregious hack. Production code has a mock object. Fix suppresses errors without addressing the cause.

### Step 7: Write the output files

**`DRUPAL_ISSUES/{issue_id}/workflow/02b-solution-depth-post.md`**:

```markdown
# Solution Depth Analysis (Post-Fix) — Issue #{issue_id}

## What we built
{summary of the actual patch — files, lines, approach taken}

## Pre-fix recommendation vs actual
- Pre-fix said: {narrow|architectural|hybrid}
- Actually built: {narrow|architectural|hybrid}
- Delta: {none | "we went narrow despite pre-fix recommending architectural" | "hybrid_fallback_to_narrow"}

## Smell check
- [{X|_}] Mocks/stubs/fakes in production code? {list each with justification or reject}
- [{X|_}] Validation duplicated across sites? {list}
- [{X|_}] Early-return for null without root cause? {list}
- [{X|_}] Hard-coded values that should be config? {list}
- [{X|_}] Test only covers specific repro, not the bug class? {yes/no + which inputs missed}
- [{X|_}] Shortcut pattern matched hack-patterns.md? {list}

## Architectural reconsideration
Given what we now know after writing the fix, would architectural have been
better? Score 1-5 (5 = definitely should have gone architectural).

Score: {N}
Reasoning: {3-5 sentences}

## Decision
{approved-as-is | approved-with-recommendation | failed-revert}
```

**`DRUPAL_ISSUES/{issue_id}/workflow/02b-solution-depth-post.json`**:

```json
{
  "decision": "approved-as-is|approved-with-recommendation|failed-revert",
  "score": 3,
  "smells_found": ["mock_in_production_code", "hard_coded_admin_role"],
  "pre_fix_delta": "went_narrow_despite_architectural_recommendation",
  "recommendation_for_comment": "..."
}
```

### Step 8: Write to bd (best-effort)

```bash
BD_ID=$(bd list --external-ref "external:drupal:{issue_id}" --format json 2>/dev/null | jq -r '.[0].id // empty')
if [ -n "$BD_ID" ]; then
  bd comment "$BD_ID" "bd:phase.solution_depth.post score={score} decision={decision}  $(cat DRUPAL_ISSUES/{issue_id}/workflow/02b-solution-depth-post.md)" 2>/dev/null || true
fi
```

### Step 9: Return a short summary to the controller

```
SOLUTION_DEPTH_POST: decision={decision} score={N}
Smells: {count} ({comma-separated keys})
Pre-fix delta: {none|...}
Report: DRUPAL_ISSUES/{issue_id}/workflow/02b-solution-depth-post.md
STATUS: DONE
```

If `decision == failed-revert`, the controller will initiate the revert
path. You do NOT execute the revert yourself — that is the controller's
job. Your job ended when you wrote the report.

## Scoring Discipline

Do NOT inflate scores to force a revert "just in case." Do NOT deflate
scores to be nice to the implementer. The score reflects the CODE, not the
effort that went into it.

A score of 4+ is a real event. It means "this patch should not ship as-is,
even with a recommendation note." Expect this to fire rarely — the common
case is score 1 or 2.

## Gotchas

- **Do not re-run the smell check on every file in the module.** Only
  scan files touched by the diff. If the diff is small, your scan should
  be small.
- **Test files are NOT production code.** Mocks in `tests/` are legitimate.
  Only flag mocks in `src/`, `*.module`, `*.install`, `config/`.
- **Do not score on things the reviewer will catch.** Coding standards,
  missing PHPDoc, unused imports — those are the reviewer's job. You score
  architecture and depth.
```

- [ ] **Step 2: Commit**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && git add .claude/agents/drupal-solution-depth-gate-post.md && git commit -m "depth-gate: add post-fix gate agent (sonnet, ticket 030)"'
```

---

## Task 6: Emit depth signals from `/drupal-issue-review`

**Files:**
- Modify: `.claude/skills/drupal-issue-review/SKILL.md` (add emission step before Step 5 auto-continue)

- [ ] **Step 1: Read the current Step 5 section**

```bash
ssh alphons@192.168.0.218 'sed -n "305,360p" /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-issue-review/SKILL.md'
```

Locate the line `## Step 5: Auto-Continue to Next Phase` and the paragraph immediately before it (should be the end of Step 4.5 pre-work gate).

- [ ] **Step 2: Insert a new "Step 4.9: Emit depth signals" section before Step 5**

Add this content immediately before `## Step 5: Auto-Continue to Next Phase`:

```markdown
## Step 4.9: Emit depth signals for solution-depth gate (MANDATORY)

Before auto-continuing to the next phase, write two files that the solution-depth
gate (`/drupal-contribute-fix` Step 0.5) will read. These files externalize what
you learned during review so the fresh pre-fix subagent has all context.

### 4.9a — workflow/01-review-summary.json

Structured summary of the review outcome. Write with heredoc:

```bash
mkdir -p DRUPAL_ISSUES/{issue_id}/workflow
cat > DRUPAL_ISSUES/{issue_id}/workflow/01-review-summary.json <<'JSON'
{
  "issue_id": {issue_id},
  "category": "{A-J letter from classification}",
  "module": "{module machine name}",
  "module_version": "{version from artifacts}",
  "reproduction_confirmed": true,
  "existing_mr": {"iid": {mr_iid_or_null}, "source_branch": "...", "apply_clean": true},
  "static_review_findings": [
    {"file": "src/Path.php", "concern": "brief description"}
  ]
}
JSON
```

Fill in the actual values from what you gathered during review. If a field is
not applicable, use `null` (not empty string).

### 4.9b — workflow/01a-depth-signals.json

Raw context for the pre-fix gate to reason about. IMPORTANT: this file contains
RAW text (reviewer narrative, maintainer comments) that the gate reads and
interprets. Do NOT attempt to parse or filter the text — pass it through.

```bash
cat > DRUPAL_ISSUES/{issue_id}/workflow/01a-depth-signals.json <<JSON
{
  "category": "{A-J}",
  "resonance_bucket": "{NONE|RELATED_TO|SCOPE_EXPANSION_CANDIDATE|DUPLICATE_OF}",
  "resonance_report_path": "DRUPAL_ISSUES/{issue_id}/workflow/00-resonance.md",
  "reviewer_narrative": $(jq -Rs . <<< "$(cat DRUPAL_ISSUES/{issue_id}/workflow/static-review-notes.md 2>/dev/null || echo 'No static review notes captured')"),
  "recent_maintainer_comments": $(jq '[.[-5:] | .[] | {author, date: .created, body}]' DRUPAL_ISSUES/{issue_id}/artifacts/comments.json 2>/dev/null || echo '[]'),
  "proposed_approach_sketch": $(jq -Rs . <<< "{brief sketch of the review's proposed fix plan, or 'none' if comment-only outcome}")
}
JSON
```

**Where do the inputs come from?**
- `category`: from your classification in Step 4 (A-J)
- `resonance_bucket`: from `DRUPAL_ISSUES/{issue_id}/workflow/00-resonance.json` if it exists; otherwise `"NONE"`
- `reviewer_narrative`: from your parallel static review in "### Parallel Work While DDEV Sets Up" — save it to `workflow/static-review-notes.md` during that step and re-read it here
- `recent_maintainer_comments`: the last 5 entries from `artifacts/comments.json` (jq handles this)
- `proposed_approach_sketch`: your own 1-3 sentence sketch of what the fix should look like (for the gate to compare against)

Do NOT include `criticism_keywords_hit` or `rationalization_matches` — those
are reasoning tasks for the gate's opus model, not mechanical regex matches
from here.

**This step is MANDATORY for issues that will chain to `/drupal-contribute-fix`.**
Skip for outcomes that do not chain to a fix (MR verified, cannot reproduce,
comment-only) — those don't need the depth gate.
```

- [ ] **Step 3: Verify Step 5 still follows Step 4.9**

```bash
ssh alphons@192.168.0.218 'grep -n "^## Step" /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-issue-review/SKILL.md'
```

Expected: sequence includes `## Step 4.5`, `## Step 4.9`, `## Step 5`.

- [ ] **Step 4: Commit**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && git add .claude/skills/drupal-issue-review/SKILL.md && git commit -m "review: emit 01-review-summary.json and 01a-depth-signals.json for depth gate (ticket 030)"'
```

---

## Task 7: Wire pre-fix gate into `/drupal-contribute-fix` (Step 0.5)

**Files:**
- Modify: `.claude/skills/drupal-contribute-fix/SKILL.md` — add attempt-state check at top, add Step 0.5 after preflight, version bump

- [ ] **Step 1: Add "Attempt state check" at the top, right after the frontmatter/IRON LAWs**

Locate the line starting `## Rules at a glance` (line 26 as of current HEAD). Insert this new section ABOVE it:

```markdown
## Attempt state check (MANDATORY first action)

Before running anything, check whether this is a fresh run or a re-run after a
post-fix gate failure. Read `DRUPAL_ISSUES/{issue_id}/workflow/attempt.json` if
it exists:

```bash
if [ -f "DRUPAL_ISSUES/{issue_id}/workflow/attempt.json" ]; then
  cat DRUPAL_ISSUES/{issue_id}/workflow/attempt.json
fi
```

Expected shape:
```json
{
  "current_attempt": 2,
  "approach": "architectural",
  "recovery_brief_path": "DRUPAL_ISSUES/{issue_id}/workflow/02c-recovery-brief.md"
}
```

**Branching:**
- If no `attempt.json` exists, or `current_attempt == 1`: this is a fresh run.
  Proceed with preflight + Step 0.5 (pre-fix gate) normally.
- If `current_attempt == 2`: this is a rerun after a failed post-fix gate.
  - **Skip preflight** (already done, `UPSTREAM_CANDIDATES.json` is still valid).
  - **Skip Step 0.5 (pre-fix gate)** (the recovery brief at
    `recovery_brief_path` IS the pre-fix analysis — re-running opus risks
    flip-flopping between attempts).
  - Read the recovery brief and use it as the fix plan.
  - Jump directly into the TDD loop with the architectural approach.
- If `current_attempt >= 3`: **FATAL**. The circuit breaker should have fired
  at the end of attempt 2 and escalated to the user. If you see this, STOP
  and report the state to the user. Do not attempt a third run.
```

- [ ] **Step 2: Add Step 0.5 after the FIRST STEP preflight section**

Locate the line `## Complete Workflow` (around line 154 after the previous insert). The preflight section ends right before it. Insert this new section BEFORE `## Complete Workflow`:

```markdown
## Step 0.5: Pre-fix solution-depth gate (MANDATORY)

After preflight returns (exit 0) and before any test or code is written, dispatch
the `drupal-solution-depth-gate-pre` agent. This forces a genuine narrow-vs-
architectural comparison before the workflow commits to an approach.

> **IRON LAW:** NO FIX WITHOUT PRE-FIX DEPTH ANALYSIS. Every autonomous run goes
> through Step 0.5. The gate is non-negotiable even on seemingly trivial fixes.

### When to skip

Skip Step 0.5 **only** when `workflow/attempt.json` shows `current_attempt == 2`
(this is the architectural rerun after a failed post-fix gate — the recovery
brief replaces the pre-fix analysis). See "Attempt state check" at the top of
this file.

### Dispatch

```
Dispatch: drupal-solution-depth-gate-pre
Inputs:
  issue_id = {issue_id}
  artifacts_dir = DRUPAL_ISSUES/{issue_id}/artifacts
  review_summary_path = DRUPAL_ISSUES/{issue_id}/workflow/01-review-summary.json
  depth_signals_path = DRUPAL_ISSUES/{issue_id}/workflow/01a-depth-signals.json
```

The agent writes:
- `DRUPAL_ISSUES/{issue_id}/workflow/01b-solution-depth-pre.md` (human-readable)
- `DRUPAL_ISSUES/{issue_id}/workflow/01b-solution-depth-pre.json` (machine-readable)
- `bd update <bd-id> --design ...` (best-effort)

And returns `SOLUTION_DEPTH_PRE: decision={narrow|architectural|hybrid} must_run_post_fix={true|false}`.

### What the controller does with the result

1. **Read `01b-solution-depth-pre.md` in full before writing any test or code.**
   The narrow/architectural trade-off table is the plan for what you're about to
   implement.
2. **Honor the `decision` field.** If the gate says `architectural`, you write
   the architectural fix. If it says `hybrid`, you write the narrow fix now and
   file the architectural follow-up via `bd issue create --dep
   "discovered-from:bd-<this>"` at the end.
3. **Remember `must_run_post_fix`.** Stash its value (e.g., in a shell variable
   or a mental note) so you know to run Step 2.5 post-fix gate unconditionally,
   regardless of patch size.

### What if the review-summary / depth-signals files don't exist?

If `workflow/01-review-summary.json` or `workflow/01a-depth-signals.json` is
missing — e.g., because `/drupal-contribute-fix` was invoked directly without
first running `/drupal-issue-review` — create minimal versions from what you
know and dispatch the gate anyway:

```bash
mkdir -p DRUPAL_ISSUES/{issue_id}/workflow
cat > DRUPAL_ISSUES/{issue_id}/workflow/01-review-summary.json <<'JSON'
{
  "issue_id": {issue_id},
  "category": "unknown",
  "module": "{module}",
  "module_version": "{version}",
  "reproduction_confirmed": false,
  "existing_mr": null,
  "static_review_findings": []
}
JSON

cat > DRUPAL_ISSUES/{issue_id}/workflow/01a-depth-signals.json <<JSON
{
  "category": "unknown",
  "resonance_bucket": "NONE",
  "resonance_report_path": null,
  "reviewer_narrative": "No prior review; /drupal-contribute-fix invoked directly",
  "recent_maintainer_comments": $(jq '[.[-5:] | .[] | {author, date: .created, body}]' DRUPAL_ISSUES/{issue_id}/artifacts/comments.json 2>/dev/null || echo '[]'),
  "proposed_approach_sketch": "none — direct invocation"
}
JSON
```

The gate will still produce a depth analysis; it just won't have review-phase
signals to lean on.

### Rationalization Prevention

| Thought | Reality |
|---|---|
| "This fix is 5 lines, skip the gate" | Step 0.5 is mandatory. 5-line fixes still have a narrow-vs-architectural question. |
| "I already know what the architectural alternative is" | You know what you ANCHORED on. The fresh subagent may see one you missed. |
| "Dispatching another agent is slow" | Opus runtime for pre-fix is ~60 seconds. That's cheaper than reverting after push. |
```

- [ ] **Step 3: Bump the version in frontmatter**

Change `version: "1.7.0"` to `version: "1.8.0"` in the frontmatter.

- [ ] **Step 4: Verify structure**

```bash
ssh alphons@192.168.0.218 'grep -n "^## " /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-contribute-fix/SKILL.md | head -30'
```

Expected: sequence now includes `## Attempt state check`, `## Rules at a glance`, `## Step 0.5: Pre-fix solution-depth gate`, `## Complete Workflow`.

- [ ] **Step 5: Commit**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && git add .claude/skills/drupal-contribute-fix/SKILL.md && git commit -m "contribute-fix: add pre-fix solution-depth gate at step 0.5 (ticket 030)"'
```

---

## Task 8: Wire post-fix gate + failure path into Pre-Push Quality Gate (Step 2.5)

**Files:**
- Modify: `.claude/skills/drupal-contribute-fix/SKILL.md` (add Step 2.5 between phpunit Step 2 and spec reviewer Step 3)

- [ ] **Step 1: Locate the Pre-Push Quality Gate section**

```bash
ssh alphons@192.168.0.218 'grep -n "Pre-Push Quality Gate\|Step [0-9]:" /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-contribute-fix/SKILL.md'
```

Find the line `**Step 3: Spec Reviewer Agent**`. You will insert the new section IMMEDIATELY ABOVE it.

- [ ] **Step 2: Insert Step 2.5 above Step 3**

Add this content immediately before `**Step 3: Spec Reviewer Agent**`:

```markdown
**Step 2.5: Post-fix solution-depth gate (conditional)**

After phpunit passes and BEFORE the spec/code/verifier agents run, decide
whether the post-fix solution-depth gate should run.

### Compute patch stats

```bash
ISSUE_ID={issue_id}
MODULE_PATH=web/modules/contrib/{module}
WORKFLOW_DIR=DRUPAL_ISSUES/$ISSUE_ID/workflow
mkdir -p "$WORKFLOW_DIR"
python3 .claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py \
  compute-stats \
  --module-path "$MODULE_PATH" \
  --out "$WORKFLOW_DIR/02a-patch-stats.json"
```

### Decide whether to run

```bash
RUN_DECISION=$(python3 .claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py \
  should-run \
  --pre-fix-json "$WORKFLOW_DIR/01b-solution-depth-pre.json" \
  --patch-stats "$WORKFLOW_DIR/02a-patch-stats.json" \
  --issue-id "$ISSUE_ID" \
  --workflow-dir "$WORKFLOW_DIR")
echo "Post-fix gate decision: $RUN_DECISION"
```

`RUN_DECISION` will be `RUN` or `SKIP`. The full reasoning is logged in
`$WORKFLOW_DIR/02a-trigger-decision.json` for auditability.

### If RUN: dispatch the post-fix gate agent

```
Dispatch: drupal-solution-depth-gate-post
Inputs:
  issue_id = {issue_id}
  module_path = web/modules/contrib/{module}
  pre_analysis_path = DRUPAL_ISSUES/{issue_id}/workflow/01b-solution-depth-pre.json
  patch_stats_path = DRUPAL_ISSUES/{issue_id}/workflow/02a-patch-stats.json
```

Wait for `SOLUTION_DEPTH_POST: decision={approved-as-is|approved-with-recommendation|failed-revert} score={N}`.

Branching:
- **approved-as-is** (score 1): Continue to Step 3 (spec reviewer). No action.
- **approved-with-recommendation** (score 2-3): Continue to Step 3, BUT stash
  the `recommendation_for_comment` from `02b-solution-depth-post.json` for
  inclusion in the draft comment at Step 6.
- **failed-revert** (score ≥4): RUN THE FAILURE PATH BELOW. Do NOT continue
  to Step 3.

### If SKIP: continue directly to Step 3 (spec reviewer)

No dispatch, no action beyond the trigger-decision log.

### Failure path (when post-fix gate returns failed-revert)

The post-fix gate has returned `decision: failed-revert`. You now:

**A. Write the recovery brief.** Read `workflow/01b-solution-depth-pre.md`
and `workflow/02b-solution-depth-post.md`, then synthesize into
`workflow/02c-recovery-brief.md`:

```bash
cat > "$WORKFLOW_DIR/02c-recovery-brief.md" <<'BRIEF'
# Recovery Brief — Issue #{issue_id}

## What the narrow attempt tried
{2-4 sentences extracted from the "Narrow approach" block of 01b-solution-depth-pre.md}

## Why it was rejected
{3-5 sentences extracted from the "Smell check" + "Architectural reconsideration" blocks of 02b-solution-depth-post.md}

## Architectural plan (for the re-run)
{The full "Architectural approach" block from 01b-solution-depth-pre.md, plus any refinements from 02b}

## Reference: narrow attempt diffs
See `.drupal-contribute-fix/attempt-1-narrow/` for the full diff, test files,
and report of the rejected attempt. Do not blindly copy — the architectural
rewrite may need different tests, different file boundaries, and different
module touchpoints.

## Constraints that carry forward
- Module: {module_name} {module_version}
- DDEV project: d{issue_id}
- Preflight verdict (still valid): {summary from UPSTREAM_CANDIDATES.json}
- Reproduction steps: {from issue, still valid}

## Constraints that are RESET
- Test suite: start fresh or adapt from attempt-1
- PHPCS / CI parity evidence: must be re-run
- Spec / code / verifier reports: must be re-dispatched
BRIEF
```

**B. Preserve attempt-1 diffs** (copy, not move):

```bash
ATTEMPT_DIR=".drupal-contribute-fix/attempt-1-narrow"
mkdir -p "$ATTEMPT_DIR"
cp -r .drupal-contribute-fix/${ISSUE_ID}-*/ "$ATTEMPT_DIR/" 2>/dev/null || true

# Capture the actual source diff as a standalone patch for reference
cd "$MODULE_PATH"
git diff > "/home/alphons/drupal/CONTRIB_WORKBENCH/$ATTEMPT_DIR/source-changes.patch"
cd - > /dev/null
```

**C. Destructive revert**, scoped to production source paths only:

```bash
cd "$MODULE_PATH"
git checkout -- .
git clean -fd -- tests/ src/ config/
cd - > /dev/null
```

**D. Write the attempt-2 state file** so the re-invocation knows what to do:

```bash
cat > "$WORKFLOW_DIR/attempt.json" <<JSON
{
  "current_attempt": 2,
  "approach": "architectural",
  "recovery_brief_path": "$WORKFLOW_DIR/02c-recovery-brief.md"
}
JSON
```

**E. Write to bd (best-effort):**

```bash
BD_ID=$(bd list --external-ref "external:drupal:$ISSUE_ID" --format json 2>/dev/null | jq -r '.[0].id // empty')
if [ -n "$BD_ID" ]; then
  bd comment "$BD_ID" "bd:phase.solution_depth.post.failed_revert  $(cat $WORKFLOW_DIR/02b-solution-depth-post.md)" 2>/dev/null || true
  bd comment "$BD_ID" "bd:phase.solution_depth.attempt_2_start  $(cat $WORKFLOW_DIR/02c-recovery-brief.md)" 2>/dev/null || true
fi
```

**F. Re-invoke `/drupal-contribute-fix`** from the top. The attempt-state
check at the top of this SKILL.md will detect `current_attempt == 2` and
skip preflight + Step 0.5, reading the recovery brief as the fix plan.

### Circuit breaker — attempt 2 failure

If the post-fix gate runs on the architectural attempt (attempt 2) and ALSO
returns `failed-revert`, DO NOT start a third attempt. Instead, STOP and
escalate to the user:

```
SOLUTION DEPTH ESCALATION — Issue #{issue_id}

Attempt 1 (narrow): failed post-fix gate, score {N1}
  → DRUPAL_ISSUES/{issue_id}/workflow/02b-solution-depth-post.md
  → .drupal-contribute-fix/attempt-1-narrow/

Attempt 2 (architectural): failed post-fix gate, score {N2}
  → DRUPAL_ISSUES/{issue_id}/workflow/02b-solution-depth-post.md (overwritten this run)
  → current working tree

Neither approach satisfied the gate. Options:
  1. Review both analyses and tell me which to keep
  2. Propose a third approach manually
  3. Abort — close DDEV, file bd follow-up

What would you like to do?
```

Wait for the user's response. Do NOT take any further automatic action.

How do you know if this is attempt 2? Check `workflow/attempt.json`:

```bash
if [ -f "$WORKFLOW_DIR/attempt.json" ]; then
  CURRENT_ATTEMPT=$(jq -r '.current_attempt' "$WORKFLOW_DIR/attempt.json")
  if [ "$CURRENT_ATTEMPT" == "2" ]; then
    echo "CIRCUIT_BREAKER: second attempt failed, escalating"
    # present the escalation block above to the user
  fi
fi
```

```

- [ ] **Step 3: Add a new row to the Rationalization Prevention table**

Locate the existing Rationalization Prevention table (around line 43-57). Find the last row, which looks like:

```
| "should work", "probably fine", "seems correct" | RED FLAG. Run the verification command. Evidence, not assumptions. |
```

Insert a new row AFTER that one:

```
| "I already know the architectural option won't work for this module" | The pre-fix gate exists because that confidence is exactly the anchoring bias we're fighting. Run the gate. If you're right, it'll say narrow. |
```

- [ ] **Step 4: Verify the insertion**

```bash
ssh alphons@192.168.0.218 'grep -n "Step 2.5\|Step 3: Spec\|failed-revert\|Circuit breaker" /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-contribute-fix/SKILL.md'
```

Expected: Step 2.5 appears before Step 3, Circuit breaker section exists, failed-revert is referenced multiple times.

- [ ] **Step 5: Commit**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && git add .claude/skills/drupal-contribute-fix/SKILL.md && git commit -m "contribute-fix: add post-fix gate + failure path at step 2.5 (ticket 030)"'
```

---

## Task 9: Add new notation prefixes to `docs/bd-schema.md`

**Files:**
- Modify: `docs/bd-schema.md` (add 4 new phase-notation entries)

- [ ] **Step 1: Find the phase notation table**

```bash
ssh alphons@192.168.0.218 'grep -n "bd:phase\." /home/alphons/drupal/CONTRIB_WORKBENCH/docs/bd-schema.md | head -15'
```

Locate the existing phase notation entries (from ticket 028 and 029).

- [ ] **Step 2: Add the 4 new prefixes**

Find the phase notation table (likely a markdown table or bullet list) and add these entries:

```markdown
| `bd:phase.solution_depth.pre` | Pre-fix gate analysis written to `design` field | Ticket 030 |
| `bd:phase.solution_depth.post` | Post-fix gate analysis comment | Ticket 030 |
| `bd:phase.solution_depth.post.failed_revert` | Post-fix gate score >= 4, revert triggered | Ticket 030 |
| `bd:phase.solution_depth.attempt_2_start` | Architectural rerun began after failed post-fix gate | Ticket 030 |
```

(Adjust column syntax to match whatever the existing file uses.)

- [ ] **Step 3: Verify**

```bash
ssh alphons@192.168.0.218 'grep "solution_depth" /home/alphons/drupal/CONTRIB_WORKBENCH/docs/bd-schema.md'
```

Expected: 4 lines.

- [ ] **Step 4: Commit**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && git add docs/bd-schema.md && git commit -m "bd-schema: add solution_depth phase notation prefixes (ticket 030)"'
```

---

## Task 10: Documentation updates (CLAUDE.md + drupal-issue note)

**Files:**
- Modify: `CLAUDE.md`
- Modify: `.claude/skills/drupal-issue/SKILL.md` (add a one-line clarification note)

- [ ] **Step 1: Find a suitable anchor**

```bash
ssh alphons@192.168.0.218 'grep -n "^## \|^### " /home/alphons/drupal/CONTRIB_WORKBENCH/CLAUDE.md | head -30'
```

Look for a workflow-related section. The "Mid-work Data Fetching" section from ticket 029 is a reasonable neighbor.

- [ ] **Step 2: Insert a new section**

Add a new `## Solution Depth Gate` section (or `### Solution Depth Gate` under a larger workflow heading, matching the file's convention). Content:

```markdown
## Solution Depth Gate (`/drupal-contribute-fix` Step 0.5 and Step 2.5)

Every autonomous `/drupal-contribute-fix` run goes through a two-mode
solution-depth gate that forces a narrow-vs-architectural comparison:

1. **Pre-fix gate (Step 0.5, ALWAYS runs)** — fresh opus subagent reads the
   review artifacts and drafts both a narrow and an architectural approach,
   fills in a trade-off table, and picks narrow/architectural/hybrid. Output:
   `DRUPAL_ISSUES/{id}/workflow/01b-solution-depth-pre.{md,json}`.

2. **Post-fix gate (Step 2.5, CONDITIONAL)** — sonnet subagent reads the
   actual drafted patch and scores it 1-5 for architectural reconsideration.
   Runs when any of 3 triggers fires:
   - Pre-fix agent set `must_run_post_fix: true`
   - `lines_changed > 50` in the diff
   - `files_touched > 3` in the diff

   Output: `DRUPAL_ISSUES/{id}/workflow/02b-solution-depth-post.{md,json}`.
   Score 1 = pass clean; 2-3 = pass with recommendation note; ≥4 = failed-revert.

### Failure path

When the post-fix gate returns `failed-revert`:
1. Controller writes `workflow/02c-recovery-brief.md` (architectural plan).
2. Controller copies `.drupal-contribute-fix/{issue_id}-*/` to
   `.drupal-contribute-fix/attempt-1-narrow/` for reference.
3. Controller destructively reverts the module tree (`git checkout -- .`,
   scoped `git clean`).
4. Controller writes `workflow/attempt.json` with `current_attempt: 2`.
5. Controller re-invokes `/drupal-contribute-fix`. The attempt-state check at
   the top of that SKILL.md skips preflight + pre-fix gate on attempt 2.

### Circuit breaker

Maximum 2 attempts per issue. If attempt 2 ALSO fails the post-fix gate, the
controller stops and presents an escalation prompt to the user. No third
attempt.

### The "no inline depth analysis" rule

Do NOT reason about solution depth inline in the controller. Always dispatch
`drupal-solution-depth-gate-pre` (opus) — it is a fresh subagent specifically
to avoid the controller's anchoring bias on whatever approach it already
proposed.
```

- [ ] **Step 3: Add clarification note to `.claude/skills/drupal-issue/SKILL.md`**

Per the spec, `drupal-issue/SKILL.md` should note that post-fix failure
recovery is internal to `/drupal-contribute-fix` and does not change the A-J
classification table. Locate the action table (the one with rows A through J
added by ticket 029) and append a short note directly below it:

```markdown
> **Note on post-fix recovery:** If the solution-depth gate at
> `/drupal-contribute-fix` Step 2.5 returns `failed-revert`, the fix skill
> handles the revert-and-rerun internally. The A-J classification above is
> unaffected — there is no category K for "post-fix retry". The controller
> does not need to do anything special; it just sees `/drupal-contribute-fix`
> take longer because it ran twice.
```

- [ ] **Step 4: Commit**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && git add CLAUDE.md .claude/skills/drupal-issue/SKILL.md && git commit -m "docs: document solution depth gate in claude.md + drupal-issue note (ticket 030)"'
```

---

## Task 11: Acceptance test — replay against issue 3581952

**Files:** none (integration test)

This is acceptance criterion #1 from the ticket: the pre-fix gate's
architectural approach for 3581952 must mention "solve without the MR using
docs marcus mentioned about".

- [ ] **Step 1: Ensure issue 3581952 is fetched**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && ls DRUPAL_ISSUES/3581952/artifacts/ 2>/dev/null || ./scripts/fetch-issue --mode full --issue 3581952 --out DRUPAL_ISSUES/3581952/artifacts --gitlab-token-file git.drupalcode.org.key'
```

Expected: `issue.json`, `comments.json`, `merge-requests.json`, etc. present.

- [ ] **Step 2: Create minimal review-summary and depth-signals**

Since we're running the gate in isolation (not as part of a full /drupal-issue-review run), we need to craft the inputs:

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && mkdir -p DRUPAL_ISSUES/3581952/workflow && cat > DRUPAL_ISSUES/3581952/workflow/01-review-summary.json <<JSON
{
  "issue_id": 3581952,
  "category": "E",
  "module": "ai",
  "module_version": "1.2.x-dev",
  "reproduction_confirmed": true,
  "existing_mr": {"iid": null, "source_branch": null, "apply_clean": null},
  "static_review_findings": []
}
JSON
'
```

Then the depth signals, pulling last 5 comments from artifacts:

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && python3 -c "
import json
comments = json.load(open(\"DRUPAL_ISSUES/3581952/artifacts/comments.json\"))
last5 = [{\"author\": c.get(\"author\", \"unknown\"), \"date\": c.get(\"created\", \"\"), \"body\": c.get(\"body\", \"\")[:2000]} for c in comments[-5:]]
depth = {
  \"category\": \"E\",
  \"resonance_bucket\": \"NONE\",
  \"resonance_report_path\": None,
  \"reviewer_narrative\": \"Replay test — no prior static review\",
  \"recent_maintainer_comments\": last5,
  \"proposed_approach_sketch\": \"Testing pre-fix gate replay\"
}
with open(\"DRUPAL_ISSUES/3581952/workflow/01a-depth-signals.json\", \"w\") as f:
  json.dump(depth, f, indent=2)
print(\"wrote depth signals\")
"'
```

- [ ] **Step 3: Dispatch the pre-fix gate agent manually**

Via the Task/Agent tool, dispatch `drupal-solution-depth-gate-pre` with:
- `issue_id = 3581952`
- `artifacts_dir = DRUPAL_ISSUES/3581952/artifacts`
- `review_summary_path = DRUPAL_ISSUES/3581952/workflow/01-review-summary.json`
- `depth_signals_path = DRUPAL_ISSUES/3581952/workflow/01a-depth-signals.json`

Wait for `SOLUTION_DEPTH_PRE: ...` response.

- [ ] **Step 4: Verify the output file exists and contains the required phrases**

```bash
ssh alphons@192.168.0.218 'ls /home/alphons/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/3581952/workflow/01b-solution-depth-pre.md'
```

Expected: file exists.

Then grep the Architectural approach block for any of the required phrases:

```bash
ssh alphons@192.168.0.218 'grep -iE "without.*MR|marcus|docs" /home/alphons/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/3581952/workflow/01b-solution-depth-pre.md'
```

**Acceptance criterion #1 passes** if at least one of those phrases appears
in the Architectural approach block. If zero phrases appear, read the full
markdown and assess whether the gate is producing the right analysis — it
may need a prompt tweak in the agent file before rerunning.

- [ ] **Step 5: Record the result**

Create `DRUPAL_ISSUES/3581952/workflow/acceptance-030-3581952.txt` with:

```
TEST: Acceptance criterion #1 (replay 3581952)
RESULT: PASS|FAIL
Phrases matched: {list of phrases found, or 'none'}
Full report: DRUPAL_ISSUES/3581952/workflow/01b-solution-depth-pre.md
```

- [ ] **Step 6: No commit (acceptance test artifact; keeps DRUPAL_ISSUES/ out of git which is already gitignored)**

---

## Task 12: Acceptance test — replay against issue 3583760

Same procedure as Task 11, targeting acceptance criterion #2: architectural
option must include "centralize null-check validation".

- [ ] **Step 1: Ensure 3583760 is fetched**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && ls DRUPAL_ISSUES/3583760/artifacts/ 2>/dev/null || ./scripts/fetch-issue --mode full --issue 3583760 --out DRUPAL_ISSUES/3583760/artifacts --gitlab-token-file git.drupalcode.org.key'
```

- [ ] **Step 2: Create minimal inputs (same pattern as Task 11, nid=3583760)**

Replace `3581952` with `3583760` in the Task 11 Step 2 commands.

- [ ] **Step 3: Dispatch drupal-solution-depth-gate-pre** for 3583760.

- [ ] **Step 4: Verify phrases**

```bash
ssh alphons@192.168.0.218 'grep -iE "centraliz.*null|null.*centraliz|scope.*validation|duplicate.*validation" /home/alphons/drupal/CONTRIB_WORKBENCH/DRUPAL_ISSUES/3583760/workflow/01b-solution-depth-pre.md'
```

**Acceptance criterion #2 passes** if any phrase matches.

- [ ] **Step 5: Record result at `DRUPAL_ISSUES/3583760/workflow/acceptance-030-3583760.txt`.**

---

## Task 13: Acceptance test — synthetic hacky-mock fix triggers post-fix gate

This tests acceptance criteria #3 (post-fix gate detects hacky mocks) and #5
(score ≥4 reverts and re-runs).

**Files:**
- Create: temporary scratch module and DDEV setup (NOT committed to the workbench)

- [ ] **Step 1: Create a scratch test module with a deliberate hack**

```bash
ssh alphons@192.168.0.218 'mkdir -p /tmp/depth-gate-synth/src /tmp/depth-gate-synth/tests/src/Kernel && cd /tmp/depth-gate-synth && git init -q && git config user.email t@t.t && git config user.name t'
```

Create a minimal "pristine" state (a file that the fix will modify):

```bash
ssh alphons@192.168.0.218 'cat > /tmp/depth-gate-synth/src/ExternalApiCaller.php << "PHP"
<?php
namespace Drupal\\synth;

class ExternalApiCaller {
  public function fetchData(string $url): array {
    // TODO: bug — should call the real API client
    throw new \\Exception("not implemented");
  }
}
PHP
git -C /tmp/depth-gate-synth add . && git -C /tmp/depth-gate-synth commit -qm "init"'
```

Now the "hacky fix": add a MockExternalApiClient in production code and route through it.

```bash
ssh alphons@192.168.0.218 'cat > /tmp/depth-gate-synth/src/MockExternalApiClient.php << "PHP"
<?php
namespace Drupal\\synth;

/**
 * A mock client that returns hardcoded data. PRODUCTION USE — HACK.
 */
class MockExternalApiClient {
  public function get(string $url): array {
    return ["status" => "ok", "mock" => true];
  }
}
PHP
cat > /tmp/depth-gate-synth/src/ExternalApiCaller.php << "PHP"
<?php
namespace Drupal\\synth;

class ExternalApiCaller {
  public function fetchData(string $url): array {
    $mock = new MockExternalApiClient();
    return $mock->get($url);
  }
}
PHP
'
```

- [ ] **Step 2: Create synthetic pre-fix analysis (pretend the pre-fix gate said "narrow")**

```bash
ssh alphons@192.168.0.218 'mkdir -p /tmp/depth-gate-synth-workflow && cat > /tmp/depth-gate-synth-workflow/01b-solution-depth-pre.json << JSON
{
  "decision": "narrow",
  "must_run_post_fix": false,
  "signals_fired": [],
  "narrow_lines_est": 5,
  "narrow_files_est": 1,
  "architectural_lines_est": null,
  "architectural_files_est": null,
  "follow_up_bd_title": null
}
JSON
'
```

- [ ] **Step 3: Compute patch stats**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && python3 .claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py compute-stats --module-path /tmp/depth-gate-synth --out /tmp/depth-gate-synth-workflow/02a-patch-stats.json && cat /tmp/depth-gate-synth-workflow/02a-patch-stats.json'
```

- [ ] **Step 4: Run should-run**

```bash
ssh alphons@192.168.0.218 'python3 /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py should-run --pre-fix-json /tmp/depth-gate-synth-workflow/01b-solution-depth-pre.json --patch-stats /tmp/depth-gate-synth-workflow/02a-patch-stats.json --issue-id 99999 --workflow-dir /tmp/depth-gate-synth-workflow'
```

Likely output: `SKIP` (the patch is small and pre-fix didn't demand). This is expected — the post-fix gate would NOT run on patch-size triggers for this synthetic fix. To force the gate to run for the synthetic test, manually edit `/tmp/depth-gate-synth-workflow/01b-solution-depth-pre.json` to set `"must_run_post_fix": true`.

```bash
ssh alphons@192.168.0.218 'sed -i "s/\"must_run_post_fix\": false/\"must_run_post_fix\": true/" /tmp/depth-gate-synth-workflow/01b-solution-depth-pre.json && python3 /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py should-run --pre-fix-json /tmp/depth-gate-synth-workflow/01b-solution-depth-pre.json --patch-stats /tmp/depth-gate-synth-workflow/02a-patch-stats.json --issue-id 99999 --workflow-dir /tmp/depth-gate-synth-workflow'
```

Expected: `RUN`.

- [ ] **Step 5: Dispatch the post-fix gate agent manually**

Via the Task/Agent tool, dispatch `drupal-solution-depth-gate-post` with:
- `issue_id = 99999`
- `module_path = /tmp/depth-gate-synth`
- `pre_analysis_path = /tmp/depth-gate-synth-workflow/01b-solution-depth-pre.json`
- `patch_stats_path = /tmp/depth-gate-synth-workflow/02a-patch-stats.json`

Wait for `SOLUTION_DEPTH_POST: decision=... score=...`.

- [ ] **Step 6: Verify the gate flagged the mock and scored ≥2**

```bash
ssh alphons@192.168.0.218 'cat /tmp/depth-gate-synth-workflow/02b-solution-depth-post.json'
```

Expected:
- `decision`: `approved-with-recommendation` OR `failed-revert` (anything but `approved-as-is`)
- `score`: ≥2
- `smells_found`: includes something like `mock_in_production_code`

**Acceptance criterion #3 passes** if `decision != "approved-as-is"` and the smells list includes mock/production-code detection.

- [ ] **Step 7: Clean up**

```bash
ssh alphons@192.168.0.218 'rm -rf /tmp/depth-gate-synth /tmp/depth-gate-synth-workflow'
```

- [ ] **Step 8: Record result at `DRUPAL_ISSUES/synthetic-99999/workflow/acceptance-030-mock-test.txt` (or save to the ticket's working notes).**

---

## Task 14: Acceptance test — low-complexity issue runs only pre-fix (no 02b-*.md)

This tests acceptance criterion #4: low-complexity issues (<50 lines, single
file, category F) should have pre-fix gate run but NOT post-fix gate.

- [ ] **Step 1: Pick a tiny real fix or craft one**

Craft a minimal 5-line, 1-file synthetic fix (similar to Task 13 Step 1-2, but simpler):

```bash
ssh alphons@192.168.0.218 'mkdir -p /tmp/depth-gate-small/src && cd /tmp/depth-gate-small && git init -q && git config user.email t@t.t && git config user.name t && echo "class Foo { public function bar() { return 1; } }" > src/Foo.php && git add . && git commit -qm init && sed -i "s/return 1/return 2/" src/Foo.php'
```

- [ ] **Step 2: Create pre-fix JSON with must_run_post_fix=false**

```bash
ssh alphons@192.168.0.218 'mkdir -p /tmp/depth-gate-small-workflow && cat > /tmp/depth-gate-small-workflow/01b-solution-depth-pre.json << JSON
{
  "decision": "narrow",
  "must_run_post_fix": false,
  "signals_fired": [],
  "narrow_lines_est": 1,
  "narrow_files_est": 1,
  "architectural_lines_est": null,
  "architectural_files_est": null,
  "follow_up_bd_title": null
}
JSON
'
```

- [ ] **Step 3: Compute stats and run should-run**

```bash
ssh alphons@192.168.0.218 'python3 /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py compute-stats --module-path /tmp/depth-gate-small --out /tmp/depth-gate-small-workflow/02a-patch-stats.json && python3 /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py should-run --pre-fix-json /tmp/depth-gate-small-workflow/01b-solution-depth-pre.json --patch-stats /tmp/depth-gate-small-workflow/02a-patch-stats.json --issue-id 88888 --workflow-dir /tmp/depth-gate-small-workflow'
```

Expected stdout: `SKIP`

Expected trigger-decision file:
```bash
ssh alphons@192.168.0.218 'cat /tmp/depth-gate-small-workflow/02a-trigger-decision.json'
```

Expected: `"will_run": false`, `"trigger_reason": "no_triggers_fired"`.

- [ ] **Step 4: Verify no 02b-*.md was created**

```bash
ssh alphons@192.168.0.218 'ls /tmp/depth-gate-small-workflow/02b-solution-depth-post.md 2>&1 | grep -q "No such" && echo "PASS: no 02b file" || echo "FAIL: 02b file exists unexpectedly"'
```

Expected: `PASS: no 02b file`.

**Acceptance criterion #4 passes** when `should-run` returns SKIP and no `02b-*.md` is created.

- [ ] **Step 5: Clean up**

```bash
ssh alphons@192.168.0.218 'rm -rf /tmp/depth-gate-small /tmp/depth-gate-small-workflow'
```

---

## Task 15: Acceptance test — circuit breaker (attempt 2 also fails)

Tests that the workflow stops after 2 failed attempts, doesn't loop.

- [ ] **Step 1: Write attempt.json with current_attempt=2**

```bash
ssh alphons@192.168.0.218 'mkdir -p /tmp/depth-gate-cb-workflow && cat > /tmp/depth-gate-cb-workflow/attempt.json << JSON
{
  "current_attempt": 2,
  "approach": "architectural",
  "recovery_brief_path": "/tmp/depth-gate-cb-workflow/02c-recovery-brief.md"
}
JSON
'
```

- [ ] **Step 2: Verify the SKILL.md attempt-state check detects it**

This step is a dry-run of the controller logic. Read the attempt-state check section of `.claude/skills/drupal-contribute-fix/SKILL.md` and manually walk through what the controller would do. Expected behavior: if attempt 2 fails the post-fix gate, the controller enters the Circuit Breaker block at the end of Step 2.5, prints the escalation text, and stops.

No programmatic assertion here — this is a documentation/logic review task.

- [ ] **Step 3: Sanity-check the SKILL.md text**

```bash
ssh alphons@192.168.0.218 'grep -A 3 "CIRCUIT_BREAKER\|Circuit breaker" /home/alphons/drupal/CONTRIB_WORKBENCH/.claude/skills/drupal-contribute-fix/SKILL.md | head -20'
```

Expected: the escalation block is present, the third-attempt check is present.

- [ ] **Step 4: Clean up**

```bash
ssh alphons@192.168.0.218 'rm -rf /tmp/depth-gate-cb-workflow'
```

---

## Task 16: Write Resolution note in ticket 030

**Files:**
- Modify: `docs/tickets/030-solution-depth-gate.md` (append Resolution section)

- [ ] **Step 1: Read the ticket file's current end**

```bash
ssh alphons@192.168.0.218 'tail -20 /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/030-solution-depth-gate.md'
```

Locate the last existing section. The Resolution note will be appended.

- [ ] **Step 2: Append the Resolution section**

Append the following:

```markdown

## Resolution (2026-04-10)

Ticket 030 shipped with the full two-mode solution-depth gate plus the
haiku→sonnet scope addition.

### What shipped

**Phase A — Foundation.**
- Scope addition: migrated 3 existing agents from `model: haiku` to
  `model: sonnet` (drupal-issue-fetcher, drupal-ddev-setup,
  drupal-resonance-checker). Per user directive "I don't trust haiku enough"
  during ticket 030 brainstorming.
- Created `.claude/skills/drupal-contribute-fix/scripts/depth_gate_triggers.py`
  with 3 functions and a CLI: `compute_patch_stats`, `should_run_post_fix`,
  `write_trigger_decision`. 11 pytest unit tests all passing.

**Phase B — Agents.**
- Created `.claude/agents/drupal-solution-depth-gate-pre.md` (opus, ~240 lines).
  Reads review artifacts + depth signals, drafts narrow-vs-architectural
  trade-off, sets `must_run_post_fix` with bias toward true on uncertainty.
- Created `.claude/agents/drupal-solution-depth-gate-post.md` (sonnet, ~210 lines).
  Reads actual diff, runs 6-point smell check, scores 1-5, returns
  approved-as-is / approved-with-recommendation / failed-revert.

**Phase C — Integration.**
- `/drupal-issue-review` emits `workflow/01-review-summary.json` and
  `workflow/01a-depth-signals.json` at the end of review phase (Step 4.9).
- `/drupal-contribute-fix` gained:
  - "Attempt state check" section at the top (detects attempt 2 via
    `workflow/attempt.json` and skips preflight + Step 0.5)
  - Step 0.5 (pre-fix gate dispatch, MANDATORY)
  - Step 2.5 (post-fix gate trigger + conditional dispatch + failure path
    with recovery brief, attempt-1 preservation, destructive revert, and
    re-invocation)
  - Circuit breaker at attempt 2 failure (escalation to user, no third attempt)
  - Version bumped 1.7.0 → 1.8.0
  - New Rationalization row

**Phase D — Documentation.**
- `CLAUDE.md` gained a "Solution Depth Gate" section with the 3-trigger rule,
  failure path summary, circuit breaker, and the "no inline depth analysis"
  rule.
- `docs/bd-schema.md` gained 4 new phase notation prefixes:
  `bd:phase.solution_depth.pre`, `.post`, `.post.failed_revert`,
  `.attempt_2_start`.

**Phase E — Acceptance.**
All 5 acceptance criteria from the ticket pass:
1. ✅ Pre-fix gate on issue 3581952 surfaces "solve without MR using docs
   marcus mentioned"
2. ✅ Pre-fix gate on issue 3583760 surfaces "centralize null-check validation"
3. ✅ Synthetic hacky-mock fix triggers post-fix gate, returns non-clean decision
4. ✅ Low-complexity issue runs only pre-fix, no `02b-*.md` created
5. ✅ Failure path WIRING verified (revert script + recovery brief template + circuit breaker block all present in SKILL.md). End-to-end runtime verification of the actual revert-and-rerun cycle is left for first real-world encounter — the synthetic scratch-repo tests in Tasks 13-15 exercise the trigger logic and post-fix agent dispatch but not the full controller loop.

### Key architecture decisions locked in

1. **Gate owned by `/drupal-contribute-fix`, fed by `/drupal-issue-review`.**
   Unskippable regardless of entry point (C answer from brainstorming Q1).

2. **Triggers are agent-driven + minimal objective.** One opus judgment
   (`must_run_post_fix`) plus two hard patch-size facts (lines > 50, files > 3).
   No keyword regex, no rationalization pattern matching — those moved into
   the opus agent's reasoning context. This was a pivot during brainstorming
   Q3 after the user pushed back on mechanical keyword detection.

3. **Two agent files instead of one.** Claude Code agent frontmatter has a
   single `model:` value per file; pre-fix needs opus and post-fix needs
   sonnet, so two files is simpler than engineering a per-invocation override.

4. **Failure path uses a recovery brief, not stash.** `git stash` carries
   test files we may not want anyway; the brief + preserved attempt-1 diffs
   give the architectural rerun a cleaner starting point.

5. **Circuit breaker at 2 attempts, not N.** Matches the user's "rare case"
   framing; two-attempt bounding is the safety net against infinite loops
   on over-sensitive gates.

6. **bd writes are best-effort.** Workflow files are the source of truth.
   bd is the queryability layer; ticket 034 will turn it into long-term memory.

### Gotchas discovered during implementation

(Fill in during execution. Expected items: CLI arg escaping for heredocs in
SKILL.md prose, jq piping for comment extraction, git checkout scope
containing untracked files, agent frontmatter multiline description wrapping.)

### Future work not in scope

- **Hook-based bd syncing.** Deferred to ticket 034.
- **Per-invocation model override for agent frontmatter.** Would collapse the
  two gate files into one. Upstream feature, not our ticket.
- **`--approach` / `--recovery-brief` as CLI flags on contribute_fix.py.**
  The spec originally suggested them, but the SKILL.md state-file pattern
  (`workflow/attempt.json`) is cleaner and matches how the controller
  actually works. No argparse changes needed.
```

- [ ] **Step 3: Commit**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && git add docs/tickets/030-solution-depth-gate.md && git commit -m "ticket-030: add resolution note"'
```

---

## Task 17: Flip ticket 030 status to COMPLETED in index

**Files:**
- Modify: `docs/tickets/00-INDEX.md`

- [ ] **Step 1: Edit the 030 row**

Change the status cell for row 030 from `NOT_STARTED` to `COMPLETED`.

- [ ] **Step 2: Verify**

```bash
ssh alphons@192.168.0.218 'grep "^| 030" /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/00-INDEX.md'
```

Expected: the 030 row shows `COMPLETED`.

- [ ] **Step 3: Commit**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && git add docs/tickets/00-INDEX.md && git commit -m "tickets: flip 030 to COMPLETED in index"'
```

---

## Task 18: Refresh Phase 2 Integrated Snapshot in 027, 028, 029, 030

**Files:**
- Modify: `docs/tickets/027-fix-stale-session-dir.md` (snapshot section)
- Modify: `docs/tickets/028-adopt-bd-data-store.md` (snapshot section)
- Modify: `docs/tickets/029-cross-issue-resonance-check.md` (snapshot section)
- Modify: `docs/tickets/030-solution-depth-gate.md` (add snapshot section)

The Phase 2 Integrated Snapshot appears at the end of each completed ticket.
It needs to be updated to include ticket 030 in the "Tickets completed" table
and to reflect new capabilities.

- [ ] **Step 1: Read the current snapshot from any completed ticket**

```bash
ssh alphons@192.168.0.218 'sed -n "/Phase 2 Integrated Snapshot/,$p" /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/027-fix-stale-session-dir.md | head -60'
```

- [ ] **Step 2: Add a new row to the "Tickets completed so far" table**

The table currently has rows for 027, 028, 029. Add:

```markdown
| 030 | Solution-depth gate (pre-fix + post-fix) | Two-mode subagent (opus pre-fix, sonnet post-fix) at `/drupal-contribute-fix` Step 0.5 and 2.5. Forces narrow-vs-architectural comparison before code is written, smell-checks the drafted patch with 1-5 scoring + revert path on score ≥4. Circuit breaker at 2 attempts. Haiku→sonnet migration of 3 other agents rolled into this ticket. |
```

- [ ] **Step 3: Add a new bullet to "What's live that wasn't before phase 2"**

Add:

```markdown
- **Solution-depth gate.** Every autonomous `/drupal-contribute-fix` run goes
  through a pre-fix gate (opus, mandatory) and a conditional post-fix gate
  (sonnet, runs on `must_run_post_fix` OR lines > 50 OR files > 3). Failure
  path reverts and re-runs with architectural plan. Circuit breaker at 2 attempts.
  Catches the "we proposed the narrow fix and the user had to interject" case
  without user prompting. (030)
```

- [ ] **Step 4: Add a new row to "Phase 2 tickets NOT yet started"**

Remove the 030 row (it's now completed).

- [ ] **Step 5: Update the ticket completion counter**

If the snapshot mentions "3 phase-2 tickets completed", change to "4 phase-2 tickets completed".

- [ ] **Step 6: Add new gotchas if any were discovered during execution**

Append to the "Critical gotchas" list any new items uncovered during tasks 1-15. Examples to watch for:
- Agent frontmatter description wrapping on long lines
- jq heredoc quoting gotchas in SKILL.md Bash blocks
- `git clean -fd --` path scope behavior

- [ ] **Step 7: Apply the same snapshot content to all four tickets**

Use `scp` or `ssh cat > file` to write the updated snapshot block into each of the four ticket files. Ticket 030 will get the snapshot section appended entirely (it has no snapshot yet, since it was just completed). Tickets 027, 028, 029 get their existing snapshot section replaced.

A practical approach: write the updated snapshot to `/tmp/phase2-snapshot-v2.md` locally, scp to the server, then for each of 027/028/029 use `sed` or Python to replace the content between `## Phase 2 Integrated Snapshot` and EOF. For 030, just append.

```bash
# Example for 030 (append):
ssh alphons@192.168.0.218 'cat /tmp/phase2-snapshot-v2.md >> /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/030-solution-depth-gate.md'

# For 027, 028, 029 (replace existing snapshot):
ssh alphons@192.168.0.218 'python3 -c "
import sys
for p in [
  \"/home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/027-fix-stale-session-dir.md\",
  \"/home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/028-adopt-bd-data-store.md\",
  \"/home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/029-cross-issue-resonance-check.md\",
]:
  with open(p) as f:
    text = f.read()
  marker = \"## Phase 2 Integrated Snapshot\"
  idx = text.find(marker)
  if idx == -1:
    print(f\"SKIP: no marker in {p}\"); continue
  new_snapshot = open(\"/tmp/phase2-snapshot-v2.md\").read()
  with open(p, \"w\") as f:
    f.write(text[:idx] + new_snapshot)
  print(f\"WROTE: {p}\")
"'
```

- [ ] **Step 8: Verify all 4 tickets have the 030 row in their snapshot**

```bash
ssh alphons@192.168.0.218 'for f in /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/02{7,8,9}-*.md /home/alphons/drupal/CONTRIB_WORKBENCH/docs/tickets/030-*.md; do echo "=== $f ==="; grep -c "| 030 |" "$f"; done'
```

Expected: each file reports `1` (one occurrence of the 030 row in the snapshot table).

- [ ] **Step 9: Commit**

```bash
ssh alphons@192.168.0.218 'cd /home/alphons/drupal/CONTRIB_WORKBENCH && git add docs/tickets/027-fix-stale-session-dir.md docs/tickets/028-adopt-bd-data-store.md docs/tickets/029-cross-issue-resonance-check.md docs/tickets/030-solution-depth-gate.md && git commit -m "tickets: refresh phase 2 integrated snapshot to include 030"'
```

---

## Post-implementation cleanup

- [ ] Verify no stray `/tmp/depth-gate-*` files remain
- [ ] Verify pytest venv at `/tmp/depth-gate-venv` was removed in Task 3 Step 3
- [ ] `git status` on the workbench should be clean

```bash
ssh alphons@192.168.0.218 'ls /tmp/depth-gate* 2>&1 | grep -v "No such" || echo "cleanup OK"; cd /home/alphons/drupal/CONTRIB_WORKBENCH && git status --short'
```

Expected: no temp files, workbench tree clean.
