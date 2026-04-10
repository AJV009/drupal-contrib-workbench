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
    python3 depth_gate_triggers.py compute-stats \
        --module-path web/modules/contrib/foo \
        --out DRUPAL_ISSUES/<nid>/workflow/02a-patch-stats.json

    # Decide whether to run the post-fix gate
    python3 depth_gate_triggers.py should-run \
        --pre-fix-json DRUPAL_ISSUES/<nid>/workflow/01b-solution-depth-pre.json \
        --patch-stats DRUPAL_ISSUES/<nid>/workflow/02a-patch-stats.json \
        --issue-id <nid> \
        --workflow-dir DRUPAL_ISSUES/<nid>/workflow
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple


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
) -> Tuple[Optional[str], bool]:
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
