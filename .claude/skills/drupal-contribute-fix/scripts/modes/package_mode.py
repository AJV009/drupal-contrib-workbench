"""Package mode: scaffold a Drupal site, require the module, apply patches."""
import os
import re
import sys
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

# Import from parent package — these are injected at contribute_fix.py level
# and passed as parameters or imported directly when this module is used.
def run_package(
    changed_path: Path,
    output_dir: Path,
    project: Optional[str] = None,
    site_root: Optional[Path] = None,
    keywords: List[str] = None,
    description: str = "fix",
    issue_number: Optional[int] = None,
    offline: bool = False,
    force: bool = False,
    upstream_ref: Optional[str] = None,
    skip_validation: bool = False,
    detect_deletions: bool = False,
    max_issues: int = 200,
    test_steps: List[str] = None,
) -> int:
    """
    Run full package workflow - search and generate MR-ready artifacts + local diff.

    Returns:
        Exit code
    """
    keywords = keywords or []
    test_steps = test_steps or []
    output_dir = Path(output_dir)
    changed_path = Path(changed_path).resolve()

    if not any(step.strip() for step in test_steps):
        print("Error: --test-steps is required and must include concrete steps.")
        return EXIT_ERROR

    # Detect site root if not provided
    if site_root is None:
        # Walk up to find composer.json
        current = changed_path
        while current != current.parent:
            if (current / "composer.json").exists():
                site_root = current
                break
            current = current.parent

    # Detect project from path
    if project is None:
        try:
            project, project_type = detect_project_from_path(
                str(changed_path),
                site_root or changed_path.parent
            )
            print(f"Detected project: {project} ({project_type})")
        except BaselineError as e:
            print(f"Error: {e}")
            return EXIT_ERROR
    else:
        # Determine project type from path
        path_str = str(changed_path).lower()
        if "/core/" in path_str or project == "drupal":
            project_type = "core"
        elif "/themes/" in path_str:
            project_type = "theme"
        else:
            project_type = "module"

    # Get list of files in the changed directory for keywords extraction
    file_paths = []
    if changed_path.is_dir():
        for root, dirs, files in os.walk(changed_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                if not f.startswith('.'):
                    file_paths.append(os.path.relpath(os.path.join(root, f), changed_path))

    # Step 1: Run preflight or fetch known issue
    candidates = []
    best_match = None
    confidence = "none"

    api = DrupalOrgAPI(offline=offline)

    if issue_number is not None:
        # User provided a known issue - fetch it and run gatekeeper check
        print(f"Fetching issue #{issue_number}...")
        try:
            issue_data = api.get_issue(issue_number, include_mrs=True)
            if not issue_data:
                print(f"Warning: Could not fetch issue #{issue_number}")
            else:
                # Build an IssueCandidate from the issue data
                # Find MRs from issue detail
                related_mrs = issue_data.get("related_mrs", []) or []
                mr_urls = extract_mr_urls(related_mrs)
                has_mr = bool(mr_urls)

                # Find patches from node AND comments
                patch_urls = collect_patch_urls(api, issue_number, issue_data)
                has_patch = bool(patch_urls)

                status_code = issue_data.get("field_issue_status")
                priority_code = issue_data.get("field_issue_priority")
                best_match = IssueCandidate(
                    nid=issue_number,
                    title=issue_data.get("title", f"Issue #{issue_number}"),
                    url=f"https://www.drupal.org/node/{issue_number}",
                    status=int(status_code) if status_code else 0,
                    status_label=get_status_label(status_code),
                    priority=int(priority_code) if priority_code else 0,
                    priority_label=get_priority_label(priority_code),
                    has_mr=has_mr,
                    has_patch=has_patch,
                    mr_urls=mr_urls,
                    patch_urls=patch_urls,
                    workflow_mode=determine_workflow_mode(has_mr, has_patch),
                    score=100.0,  # High score since user explicitly chose this issue
                    score_breakdown={"user_specified": 100.0},
                )
                candidates = [best_match]
                confidence = "high"  # User specified = high confidence

                print(f"Issue: {best_match.title}")
                print(f"  Status: {best_match.status_label}")
                if has_mr:
                    print(f"  Has MR(s): {', '.join(mr_urls[:3])}")
                if has_patch:
                    print(f"  Has patches: {len(patch_urls)} attached")

        except DrupalOrgAPIError as e:
            print(f"Warning: Could not fetch issue: {e}")
    else:
        # No issue specified - run full preflight search
        exit_code, candidates, best_match, confidence = run_preflight(
            project=project,
            keywords=keywords,
            paths=file_paths[:10],  # Limit paths for search
            output_dir=output_dir,
            offline=offline,
            max_issues=max_issues,
        )

        if exit_code == EXIT_ERROR:
            return exit_code

    # Step 2: Check for existing fix (workflow-aware)
    # This runs for both preflight and known-issue cases
    should_stop, reason, workflow_mode = check_existing_fix(candidates, best_match, confidence)

    if should_stop and not force:
        if workflow_mode == WORKFLOW_MODE_MR:
            print(f"\n*** STOP: Issue is MR-based ***")
        elif workflow_mode == WORKFLOW_MODE_PATCH:
            print(f"\n*** STOP: Issue has historical patch attachments ***")
        else:
            print(f"\n*** STOP: Existing upstream fix found ***")

        print(f"\n{reason}")
        print("\nUse --force to override and generate a local diff artifact anyway.")

        # Still write report (into issue-specific directory)
        stop_issue_nid = issue_number or (best_match.nid if best_match else None)

        # Generate slug for directory name
        def slugify_stop(text: str, max_length: int = 40) -> str:
            slug = re.sub(r'[^a-z0-9]+', '-', text.lower())
            slug = slug.strip('-')
            if len(slug) > max_length:
                slug = slug[:max_length].rsplit('-', 1)[0]
            return slug

        stop_slug = slugify_stop(keywords[0]) if keywords else "fix"
        if stop_issue_nid:
            stop_issue_dir = f"{stop_issue_nid}-{stop_slug}"
        else:
            stop_issue_dir = f"unfiled-{stop_slug}"

        report = create_report(
            project=project,
            keywords=keywords,
            file_paths=file_paths,
            outcome="existing_fix",
            outcome_code=EXIT_EXISTING_FIX,
            outcome_reason=reason,
            candidates=candidates,
            best_match=best_match,
            best_match_confidence=confidence,
            # Even when we STOP, persist the test steps so the output artifact
            # can be used directly for follow-up comments/reviews.
            test_steps=test_steps if test_steps else None,
        )
        write_report(report, output_dir, issue_nid=stop_issue_nid, issue_dir_override=stop_issue_dir)
        print(f"\nArtifacts written to: {output_dir}/{stop_issue_dir}/")

        return EXIT_EXISTING_FIX

    # Step 3: Resolve baseline
    print(f"\nResolving baseline for {project}...")
    try:
        baseline = resolve_baseline(
            project_name=project,
            project_type=project_type,
            site_root=site_root,
            explicit_ref=upstream_ref,
        )
        print(f"Baseline: {baseline.git_url} @ {baseline.ref}")
        print(f"Source: {baseline.source}")
    except BaselineError as e:
        print(f"Error resolving baseline: {e}")
        return EXIT_ERROR

    # Step 4: Checkout baseline
    print("Cloning baseline repository...")
    work_dir = Path(tempfile.mkdtemp(prefix="drupal-contrib-"))
    try:
        baseline_path = checkout_baseline(baseline, work_dir)
        print(f"Checked out to: {baseline_path}")
    except BaselineError as e:
        print(f"Error checking out baseline: {e}")
        shutil.rmtree(work_dir, ignore_errors=True)
        return EXIT_ERROR

    # Step 5: Copy changes and detect modifications
    print("Analyzing changes...")
    source_path = changed_path

    # For core, the site has web/core but the baseline repo has core/ subdir
    # So we compare source files to baseline_path/core/
    if project_type == "core":
        baseline_prefix = "core"
    else:
        baseline_prefix = ""

    # Get changed files (paths are relative to source_path)
    changed_files = get_changed_files_from_git(
        source_path, baseline_path,
        baseline_prefix=baseline_prefix,
        detect_deletions=detect_deletions,
    )
    print(f"Changed files: {len(changed_files)}")

    if not changed_files:
        print("No changes detected.")
        shutil.rmtree(work_dir, ignore_errors=True)
        return EXIT_ERROR

    # Copy changes to baseline (applies baseline_prefix when writing)
    modified, new, deleted = copy_changes_to_baseline(
        source_path, baseline_path, changed_files, baseline_prefix=baseline_prefix
    )
    print(f"  Modified: {len(modified)}, New: {len(new)}, Deleted: {len(deleted)}")

    # Step 6: Security check
    print("\nChecking for security-related changes...")
    try:
        # Generate diff for security check
        import subprocess
        diff_result = subprocess.run(
            ["git", "diff"],
            cwd=baseline_path,
            capture_output=True,
            text=True,
        )
        diff_content = diff_result.stdout

        is_security, indicators = is_security_related(diff_content, changed_files)

        if is_security:
            print("\n*** STOP: Security-related changes detected ***")
            print(format_security_warning(indicators))

            report = create_report(
                project=project,
                keywords=keywords,
                file_paths=changed_files,
                outcome="security",
                outcome_code=EXIT_SECURITY,
                outcome_reason="Security-related changes detected. Follow Drupal Security Team process.",
                candidates=candidates,
                best_match=best_match,
                best_match_confidence=confidence,
                warnings=[i.description for i in indicators],
            )
            write_report(report, output_dir)
            shutil.rmtree(work_dir, ignore_errors=True)
            return EXIT_SECURITY

    except Exception as e:
        print(f"Warning: Security check failed: {e}")

    # Step 7: Determine issue number for directory structure
    # Use explicit issue_number, or best_match if high confidence, or "unfiled"
    effective_issue = issue_number or (best_match.nid if best_match and confidence in ("high", "medium") else None)

    # Generate slug from keywords for directory naming
    def slugify(text: str, max_length: int = 40) -> str:
        slug = re.sub(r'[^a-z0-9]+', '-', text.lower())
        slug = slug.strip('-')
        if len(slug) > max_length:
            slug = slug[:max_length].rsplit('-', 1)[0]
        return slug

    slug = slugify(keywords[0]) if keywords else "fix"
    if effective_issue:
        issue_dir_name = f"{effective_issue}-{slug}"
    else:
        issue_dir_name = f"unfiled-{slug}"

    # Generate local diff into issue-specific directory (flat structure)
    print("\nGenerating local diff artifact...")
    issue_dir = output_dir / issue_dir_name
    diffs_dir = issue_dir / "diffs"

    # Check for .info.yml files
    has_info_yml = any(f.endswith('.info.yml') for f in changed_files)

    try:
        patch_info = generate_patch(
            baseline_path=baseline_path,
            output_dir=diffs_dir,
            project=project,
            description=description,
            issue_number=effective_issue,
            new_files=new,
            reduced_context=has_info_yml,
        )
        print(f"Diff generated: {patch_info.filename}")
        print(f"  Files changed: {patch_info.files_changed}")
        print(f"  +{patch_info.insertions}/-{patch_info.deletions} lines")

        if patch_info.warnings:
            print("\nWarnings:")
            for warning in patch_info.warnings:
                print(f"  - {warning}")

    except PatchError as e:
        print(f"Error generating local diff artifact: {e}")
        shutil.rmtree(work_dir, ignore_errors=True)
        return EXIT_ERROR

    # Step 8: Validation
    validation_results = []
    if not skip_validation:
        print("\nRunning validation...")
        # Use modified + new which include baseline_prefix (e.g., core/ for core changes)
        files_to_validate = modified + new
        full_paths = [baseline_path / f for f in files_to_validate]
        validation_results = validate_files(full_paths)

        for result in validation_results:
            status = "PASSED" if result.passed else "FAILED"
            if result.not_run_reason:
                status = f"SKIPPED ({result.not_run_reason})"
            print(f"  {result.tool}: {status}")

    # Step 9: Write report
    print("\nWriting report...")

    # Determine outcome
    if patch_info.warnings and any("hack" in w.lower() for w in patch_info.warnings):
        outcome = "analysis_only"
        outcome_code = EXIT_ANALYSIS_ONLY
        outcome_reason = "Diff contains patterns that may need review. Consider posting analysis first."
    else:
        outcome = "proceed"
        outcome_code = EXIT_PROCEED
        outcome_reason = "Local diff artifact generated successfully for MR workflow."

    report = create_report(
        project=project,
        keywords=keywords,
        file_paths=changed_files,
        outcome=outcome,
        outcome_code=outcome_code,
        outcome_reason=outcome_reason,
        candidates=candidates,
        best_match=best_match,
        best_match_confidence=confidence,
        patch_info=patch_info,
        validation_results=validation_results,
        warnings=patch_info.warnings,
        test_steps=test_steps if test_steps else None,
    )

    paths = write_report(report, output_dir, issue_nid=effective_issue, issue_dir_override=issue_dir_name)
    print(f"\nArtifacts written to: {output_dir}/")
    print(f"  - {issue_dir_name}/REPORT.md")
    print(f"  - {issue_dir_name}/ISSUE_COMMENT.md")
    print(f"  - {issue_dir_name}/diffs/{patch_info.filename}")

    # Cleanup
    shutil.rmtree(work_dir, ignore_errors=True)

    return outcome_code


