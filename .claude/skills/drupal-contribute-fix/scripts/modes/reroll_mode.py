"""Reroll mode: reroll patches and MRs to a new branch."""
import os
import re
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional
def run_reroll(
    issue_number: int,
    patch_url: str,
    target_ref: str,
    output_dir: Path,
    project: Optional[str] = None,
) -> int:
    """
    Reroll an existing patch for a different version/branch.

    Returns:
        Exit code
    """
    import re

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract project name from patch URL if not provided
    if not project:
        # Try to parse from URL like /project/metatag/...
        match = re.search(r'/project/([^/]+)/', patch_url)
        if match:
            project = match.group(1)
        else:
            # Try to parse from filename like metatag-fix-123.patch
            filename = patch_url.split('/')[-1]
            project = filename.split('-')[0]

    if not project:
        print("Error: Could not determine project name. Use --project to specify.")
        return EXIT_ERROR

    print(f"Rerolling patch for {project} to {target_ref}...")
    print(f"Original patch: {patch_url}")

    # Download the original patch via the consolidated raw_fetch helper
    # (ticket 029 Phase D: no more inline urllib.request in skill scripts).
    print("\nDownloading original patch...")
    try:
        original_patch = download_raw_file(
            patch_url,
            user_agent="drupal-contribute-fix/1.0",
        )
    except RawFetchError as e:
        print(f"Error downloading patch: {e}")
        return EXIT_ERROR

    # Save original patch
    original_filename = patch_url.split('/')[-1]
    original_path = output_dir / f"original-{original_filename}"
    with open(original_path, 'w') as f:
        f.write(original_patch)
    print(f"Saved original: {original_path}")

    # Clone target branch
    print(f"\nCloning {project} @ {target_ref}...")
    work_dir = Path(tempfile.mkdtemp(prefix="drupal-reroll-"))

    try:
        baseline = resolve_baseline(
            project_name=project,
            project_type="module",  # Assume module for reroll
            explicit_ref=target_ref,
        )
        baseline_path = checkout_baseline(baseline, work_dir)
    except BaselineError as e:
        print(f"Error: {e}")
        shutil.rmtree(work_dir, ignore_errors=True)
        return EXIT_ERROR

    # Try to apply the patch
    print("\nAttempting to apply patch...")
    import subprocess

    apply_result = subprocess.run(
        ["git", "apply", "--check", str(original_path)],
        cwd=baseline_path,
        capture_output=True,
        text=True,
    )

    if apply_result.returncode == 0:
        print("Patch applies cleanly! No reroll needed.")
        print(f"\nYou can use the original patch as-is on {target_ref}.")

        # Generate comment
        lines = [
            "## Reroll Comment",
            "",
            f"**Issue:** https://www.drupal.org/node/{issue_number}",
            f"**Original patch:** {patch_url}",
            f"**Target branch:** {target_ref}",
            "",
            "---",
            "",
            "**Copy/paste this into the issue:**",
            "",
            "---",
            "",
            f"Tested the patch from #{issue_number} against `{target_ref}`.",
            "",
            "**Result:** Patch applies cleanly, no reroll needed.",
            "",
        ]
    else:
        print("Patch does not apply cleanly. Attempting 3-way merge...")

        # Try 3-way apply
        apply_3way = subprocess.run(
            ["git", "apply", "--3way", str(original_path)],
            cwd=baseline_path,
            capture_output=True,
            text=True,
        )

        if apply_3way.returncode == 0:
            print("Applied with 3-way merge.")

            # Generate the rerolled patch
            diff_result = subprocess.run(
                ["git", "diff"],
                cwd=baseline_path,
                capture_output=True,
                text=True,
            )

            # Save rerolled patch
            reroll_filename = f"{project}-reroll-{issue_number}-{target_ref.replace('/', '-')}.patch"
            reroll_path = output_dir / "patches" / reroll_filename
            reroll_path.parent.mkdir(parents=True, exist_ok=True)

            with open(reroll_path, 'w') as f:
                f.write(diff_result.stdout)

            print(f"\nRerolled patch: {reroll_path}")

            # Generate interdiff if possible
            lines = [
                "## Reroll Comment",
                "",
                f"**Issue:** https://www.drupal.org/node/{issue_number}",
                f"**Original patch:** {patch_url}",
                f"**Target branch:** {target_ref}",
                f"**Rerolled patch:** `{reroll_filename}`",
                "",
                "---",
                "",
                "**Copy/paste this into the issue:**",
                "",
                "---",
                "",
                f"### Reroll for {target_ref}",
                "",
                f"The patch from comment #[X] did not apply cleanly to `{target_ref}`.",
                "",
                f"Attached is a rerolled version (`{reroll_filename}`).",
                "",
                "**Changes from original:**",
                "- [Describe any manual conflict resolution]",
                "",
            ]
        else:
            print("\nPatch requires manual conflict resolution.")
            print(f"Conflicts:\n{apply_3way.stderr}")

            lines = [
                "## Reroll Required (Manual)",
                "",
                f"**Issue:** https://www.drupal.org/node/{issue_number}",
                f"**Original patch:** {patch_url}",
                f"**Target branch:** {target_ref}",
                "",
                "The patch could not be automatically rerolled.",
                "",
                "**Conflicts:**",
                "```",
                apply_3way.stderr[:1000],
                "```",
                "",
                "Manual resolution required.",
            ]

    comment_content = "\n".join(lines)
    comment_path = output_dir / "REROLL_COMMENT.md"
    with open(comment_path, 'w') as f:
        f.write(comment_content)

    print(f"\nReroll comment: {comment_path}")

    # Cleanup
    shutil.rmtree(work_dir, ignore_errors=True)

    return EXIT_PROCEED


