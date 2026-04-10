#!/usr/bin/env python3
"""
drupal-contribute-fix: Upstream contribution helper for Drupal.

Searches drupal.org issue queue before generating local diffs, detects existing
fixes, and packages minimal upstream-acceptable contributions.

Exit codes:
    0  - PROCEED: MR artifacts + local diff generated
    10 - STOP: Existing upstream fix found
    20 - STOP: Fixed in newer upstream version
    30 - STOP: Analysis-only recommended
    40 - ERROR: Could not complete
    50 - STOP: Security-related issue detected
"""

import argparse
import os
import re
import sys
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

# Add both the local lib (for issue_matcher, baseline_repo, etc.) and the
# workbench-shared data lib (for drupalorg_api, drupalorg_urls, etc.) to sys.path.
# Data modules were moved to scripts/lib/data/ in ticket 029 Phase C.
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
LIB_DIR = REPO_ROOT / "lib"
WORKBENCH_ROOT = SCRIPT_DIR.parent.parent.parent.parent
DATA_LIB_DIR = WORKBENCH_ROOT / "scripts" / "lib" / "data"
sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(DATA_LIB_DIR))

from drupalorg_api import DrupalOrgAPI, DrupalOrgAPIError, is_fixed_status, get_status_label, get_priority_label
from drupalorg_urls import build_project_issue_search_url
from raw_fetch import download_raw_file, RawFetchError
from issue_queue_integration import find_dorg_script
from issue_matcher import (
    IssueMatcher,
    IssueCandidate,
    determine_workflow_mode,
    WORKFLOW_MODE_MR,
    WORKFLOW_MODE_PATCH,
    WORKFLOW_MODE_NONE,
)
from baseline_repo import (
    detect_project_from_path,
    resolve_baseline,
    checkout_baseline,
    BaselineError,
)
from patch_packager import (
    copy_changes_to_baseline,
    get_changed_files_from_git,
    generate_patch,
    PatchError,
)
from security_detector import is_security_related, format_security_warning
from validator import validate_files
from report_writer import (
    create_report,
    write_candidates_json,
    write_report,
)


# Exit codes
EXIT_PROCEED = 0
EXIT_EXISTING_FIX = 10
EXIT_FIXED_UPSTREAM = 20
EXIT_ANALYSIS_ONLY = 30
EXIT_ERROR = 40
EXIT_SECURITY = 50



# --- Extracted modules (ticket 034 decomposition) ---
from lib.patch_utils import _extract_patch_urls_from_files, collect_patch_urls, extract_mr_urls
from modes.package_mode import run_package
from modes.test_mode import run_test
from modes.reroll_mode import run_reroll


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Drupal upstream contribution helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Preflight command
    preflight = subparsers.add_parser(
        "preflight",
        help="Search upstream without generating local contribution artifacts",
    )
    preflight.add_argument(
        "--project", "-p",
        required=True,
        help="Drupal project machine name (e.g., metatag, drupal)",
    )
    preflight.add_argument(
        "--keywords", "-k",
        nargs="+",
        default=[],
        help="Search keywords (error messages, terms)",
    )
    preflight.add_argument(
        "--paths",
        nargs="+",
        default=[],
        help="Relevant file paths",
    )
    preflight.add_argument(
        "--out", "-o",
        default=".drupal-contribute-fix",
        help="Output directory (default: .drupal-contribute-fix)",
    )
    preflight.add_argument(
        "--offline",
        action="store_true",
        help="Use cached data only, don't make API requests",
    )
    preflight.add_argument(
        "--max-issues",
        type=int,
        default=200,
        help="Maximum issues to fetch for matching (default: 200)",
    )

    # Package command
    package = subparsers.add_parser(
        "package",
        help="Search upstream and generate contribution artifacts",
    )
    package.add_argument(
        "--root", "-r",
        type=Path,
        help="Drupal site root directory",
    )
    package.add_argument(
        "--changed-path", "-c",
        type=Path,
        required=True,
        help="Path to changed module/theme/core directory",
    )
    package.add_argument(
        "--project", "-p",
        help="Drupal project machine name (auto-detected if not provided)",
    )
    package.add_argument(
        "--keywords", "-k",
        nargs="+",
        default=[],
        help="Search keywords (error messages, terms)",
    )
    package.add_argument(
        "--description", "-d",
        default="fix",
        help="Short description for diff filename",
    )
    package.add_argument(
        "--issue", "-i",
        type=int,
        help="Known issue number (uses this issue for gatekeeper check)",
    )
    package.add_argument(
        "--out", "-o",
        default=".drupal-contribute-fix",
        help="Output directory (default: .drupal-contribute-fix)",
    )
    package.add_argument(
        "--offline",
        action="store_true",
        help="Use cached data only",
    )
    package.add_argument(
        "--force",
        action="store_true",
        help="Generate local diff artifact even if existing fix found",
    )
    package.add_argument(
        "--upstream-ref",
        help="Explicit git ref for baseline (overrides detection)",
    )
    package.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip code validation checks",
    )
    package.add_argument(
        "--detect-deletions",
        action="store_true",
        help="Detect deleted files (risky with Composer-installed trees)",
    )
    package.add_argument(
        "--max-issues",
        type=int,
        default=200,
        help="Maximum issues to fetch for matching",
    )
    package.add_argument(
        "--test-steps",
        nargs="+",
        required=True,
        help="Required. Specific test steps for the issue comment",
    )

    # Test command - generate RTBC-style comment for existing MR/diff
    test_cmd = subparsers.add_parser(
        "test",
        help="Generate a Tested-by/RTBC comment for an existing MR or diff artifact",
    )
    test_cmd.add_argument(
        "--issue", "-i",
        type=int,
        required=True,
        help="Issue number to test",
    )
    test_cmd.add_argument(
        "--tested-on",
        required=True,
        help="Environment tested on (e.g., 'Drupal 10.2, PHP 8.2')",
    )
    test_cmd.add_argument(
        "--result",
        choices=["pass", "fail", "partial"],
        required=True,
        help="Test result: pass (works), fail (broken), partial (works with caveats)",
    )
    test_cmd.add_argument(
        "--notes",
        help="Additional notes about the test",
    )
    test_cmd.add_argument(
        "--mr",
        help="Specific MR number tested (e.g., '42')",
    )
    test_cmd.add_argument(
        "--patch",
        help="Specific diff/patch filename tested",
    )
    test_cmd.add_argument(
        "--out", "-o",
        default=".drupal-contribute-fix",
        help="Output directory (default: .drupal-contribute-fix)",
    )

    # Reroll command - help reroll a patch for a different version
    reroll = subparsers.add_parser(
        "reroll",
        help="Reroll an existing patch for a different version/branch",
    )
    reroll.add_argument(
        "--issue", "-i",
        type=int,
        required=True,
        help="Issue number",
    )
    reroll.add_argument(
        "--patch-url",
        required=True,
        help="URL of the patch to reroll",
    )
    reroll.add_argument(
        "--target-ref",
        required=True,
        help="Target branch/ref for the reroll (e.g., '2.0.x')",
    )
    reroll.add_argument(
        "--project", "-p",
        help="Drupal project machine name (auto-detected from patch if not provided)",
    )
    reroll.add_argument(
        "--out", "-o",
        default=".drupal-contribute-fix",
        help="Output directory (default: .drupal-contribute-fix)",
    )

    return parser.parse_args()



def run_preflight(
    project: str,
    keywords: List[str],
    paths: List[str],
    output_dir: Path,
    offline: bool = False,
    max_issues: int = 200,
) -> Tuple[int, List[IssueCandidate], Optional[IssueCandidate], str]:
    """
    Run preflight check - search upstream for existing issues.

    Returns:
        Tuple of (exit_code, candidates, best_match, confidence)
    """
    print(f"Searching drupal.org issue queue for project: {project}")
    print(f"Manual keyword search (Drupal.org UI): {build_project_issue_search_url(project, keywords)}")
    print("Note: Drupal.org api-d7 does not support a `text=` filter (it returns HTTP 412).")

    api = DrupalOrgAPI(offline=offline)

    # Get project node ID
    try:
        project_nid = api.get_project_nid(project)
        if not project_nid:
            print(f"Error: Could not find project '{project}' on drupal.org")
            return EXIT_ERROR, [], None, "none"
    except DrupalOrgAPIError as e:
        print(f"API Error: {e}")
        return EXIT_ERROR, [], None, "none"

    print(f"Found project nid: {project_nid}")

    # Search for matching issues
    matcher = IssueMatcher(api)
    candidates = matcher.find_candidates(
        project_nid=project_nid,
        keywords=keywords,
        file_paths=paths,
        max_issues=max_issues,
    )

    best_match, confidence = matcher.get_best_match_confidence(candidates)

    print(f"\nFound {len(candidates)} relevant issues")
    if best_match:
        print(f"Best match: {best_match.title}")
        print(f"  URL: {best_match.url}")
        print(f"  Status: {best_match.status_label}")
        print(f"  Confidence: {confidence}")
        if best_match.has_mr:
            print(f"  Has MR(s): {', '.join(best_match.mr_urls)}")

        dorg_path = find_dorg_script(REPO_ROOT)
        if dorg_path:
            print(
                "\nOptional deep summary (drupal-issue-queue):\n"
                f"  python3 {dorg_path} --format md issue {best_match.nid} --mode summary --comments 10 --files-limit 0 --resolve-tags none --related-mrs"
            )
            if not offline:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                summary_path = output_dir / f"ISSUE_{best_match.nid}_SUMMARY.md"
                try:
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(dorg_path),
                            "--format",
                            "md",
                            "issue",
                            str(best_match.nid),
                            "--mode",
                            "summary",
                            "--comments",
                            "10",
                            "--files-limit",
                            "0",
                            "--resolve-tags",
                            "none",
                            "--related-mrs",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        summary_path.write_text(result.stdout, encoding="utf-8")
                        print(f"Saved issue summary: {summary_path}")
                    else:
                        print(
                            "Warning: drupal-issue-queue summary failed "
                            f"(exit {result.returncode}): {result.stderr.strip()}",
                            file=sys.stderr,
                        )
                except Exception as e:
                    print(f"Warning: drupal-issue-queue summary error: {e}", file=sys.stderr)
        else:
            print(
                "\nOptional deep summary (drupal-issue-queue skill):\n"
                f"  python scripts/dorg.py issue {best_match.nid} --format md\n"
                "  (run from the drupal-issue-queue directory)"
            )

    return EXIT_PROCEED, candidates, best_match, confidence



def check_existing_fix(
    candidates: List[IssueCandidate],
    best_match: Optional[IssueCandidate],
    confidence: str,
) -> Tuple[bool, str, str]:
    """
    Check if an existing fix likely exists, with workflow-aware logic.

    Per Drupal contribution workflow:
    - If issue is MR-based, recommend reviewing/updating the MR
    - If issue only has historical patch attachments, recommend opening/updating an MR
    - If issue is fixed, recommend using the existing fix

    Returns:
        Tuple of (should_stop, reason, workflow_mode)
    """
    if not best_match:
        return False, "", WORKFLOW_MODE_NONE

    workflow_mode = best_match.workflow_mode

    # Check if issue is already fixed (highest priority)
    if is_fixed_status(best_match.status) and confidence in ("high", "medium"):
        return True, f"Issue already fixed: {best_match.url}", workflow_mode

    # MR-based issue: recommend working via MR workflow
    if workflow_mode == WORKFLOW_MODE_MR and confidence in ("high", "medium"):
        mr_list = ', '.join(best_match.mr_urls[:3])  # Limit to first 3
        reason = (
            f"Issue is MR-based. Review/update the existing MR instead of creating a separate patch submission.\n"
            f"  Issue: {best_match.url}\n"
            f"  MR(s): {mr_list}\n\n"
            f"To test the MR locally, download as `.diff` or `.patch`:\n"
            f"  {best_match.mr_urls[0]}.diff (if available)\n\n"
            f"Note: Don't point Composer directly at MR URLs - download the file instead."
        )
        return True, reason, workflow_mode

    # Patch-only issue: recommend MR-first workflow going forward
    if workflow_mode == WORKFLOW_MODE_PATCH and confidence in ("high", "medium"):
        reason = (
            f"Issue has patch attachments but no active MR.\n"
            f"  Issue: {best_match.url}\n"
            f"  Existing patches: {len(best_match.patch_urls)} attached\n\n"
            f"For new work, use MR workflow: create/get push access to the issue fork, "
            f"push commits, and open/update a merge request."
        )
        return True, reason, workflow_mode

    # Check top candidates for fixed status
    for candidate in candidates[:5]:
        if is_fixed_status(candidate.status):
            return True, f"Related issue already fixed: {candidate.url}", candidate.workflow_mode

    return False, "", workflow_mode



def main():
    """Main entry point."""
    args = parse_args()

    if args.command == "preflight":
        exit_code, candidates, best_match, confidence = run_preflight(
            project=args.project,
            keywords=args.keywords,
            paths=args.paths,
            output_dir=Path(args.out),
            offline=args.offline,
            max_issues=args.max_issues,
        )

        # Write candidates JSON only - no report folder for preflight
        # Preflight is just a search; issue folders are only created by `package`
        output_dir = Path(args.out)
        write_candidates_json(candidates, output_dir)

        # Check for existing fix (workflow-aware)
        should_stop, reason, workflow_mode = check_existing_fix(candidates, best_match, confidence)
        if should_stop:
            if workflow_mode == WORKFLOW_MODE_MR:
                print(f"\n*** Issue is MR-based - review existing MR ***")
            elif workflow_mode == WORKFLOW_MODE_PATCH:
                print(f"\n*** Issue has historical patches - use MR workflow going forward ***")
            else:
                print(f"\n*** Existing fix likely exists ***")
            print(f"\n{reason}")
            sys.exit(EXIT_EXISTING_FIX)

        sys.exit(exit_code)

    elif args.command == "package":
        exit_code = run_package(
            changed_path=args.changed_path,
            output_dir=Path(args.out),
            project=args.project,
            site_root=args.root,
            keywords=args.keywords,
            description=args.description,
            issue_number=args.issue,
            offline=args.offline,
            force=args.force,
            upstream_ref=args.upstream_ref,
            skip_validation=args.skip_validation,
            detect_deletions=args.detect_deletions,
            max_issues=args.max_issues,
            test_steps=args.test_steps,
        )
        sys.exit(exit_code)

    elif args.command == "test":
        exit_code = run_test(
            issue_number=args.issue,
            tested_on=args.tested_on,
            result=args.result,
            output_dir=Path(args.out),
            notes=args.notes,
            mr_number=args.mr,
            patch_name=args.patch,
        )
        sys.exit(exit_code)

    elif args.command == "reroll":
        exit_code = run_reroll(
            issue_number=args.issue,
            patch_url=args.patch_url,
            target_ref=args.target_ref,
            output_dir=Path(args.out),
            project=args.project,
        )
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
