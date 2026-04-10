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
