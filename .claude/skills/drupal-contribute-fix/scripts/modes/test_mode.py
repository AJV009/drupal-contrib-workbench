"""Test mode: run tests against an existing DDEV environment."""
import os
import sys
import subprocess
from pathlib import Path
from typing import List, Optional
def run_test(
    issue_number: int,
    tested_on: str,
    result: str,
    output_dir: Path,
    notes: Optional[str] = None,
    mr_number: Optional[str] = None,
    patch_name: Optional[str] = None,
) -> int:
    """
    Generate a Tested-by/RTBC comment for an existing MR or diff artifact.

    Returns:
        Exit code (0 for success)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Fetch issue details
    api = DrupalOrgAPI()
    print(f"Fetching issue #{issue_number}...")

    try:
        issue_data = api.get_issue(issue_number, include_mrs=True)
        if not issue_data:
            print(f"Error: Could not fetch issue #{issue_number}")
            return EXIT_ERROR
    except DrupalOrgAPIError as e:
        print(f"API Error: {e}")
        return EXIT_ERROR

    issue_title = issue_data.get("title", f"Issue #{issue_number}")
    issue_url = f"https://www.drupal.org/node/{issue_number}"

    # Determine what was tested
    if mr_number:
        tested_artifact = f"MR !{mr_number}"
    elif patch_name:
        tested_artifact = f"diff `{patch_name}`"
    else:
        # Try to auto-detect from issue
        related_mrs = issue_data.get("related_mrs", [])
        mr_urls = extract_mr_urls(related_mrs)
        if mr_urls:
            mr_url = mr_urls[0]
            mr_id = mr_url.split("/")[-1] if mr_url else "latest"
            tested_artifact = f"MR !{mr_id}"
        else:
            tested_artifact = "the latest diff/patch artifact"

    # Generate comment based on result
    lines = [
        "## Test Comment",
        "",
        f"**Issue:** [{issue_title}]({issue_url})",
        f"**Tested:** {tested_artifact}",
        f"**Environment:** {tested_on}",
        "",
        "---",
        "",
        "**Copy/paste this into the issue:**",
        "",
        "---",
        "",
    ]

    if result == "pass":
        lines.extend([
            f"### Tested {tested_artifact} - Works as expected",
            "",
            f"**Environment:** {tested_on}",
            "",
            "**Steps tested:**",
            "1. Applied the diff/checked out the MR",
            "2. [Describe what you tested]",
            "3. [Describe expected vs actual result]",
            "",
            "**Result:** The fix works correctly.",
            "",
        ])
        if notes:
            lines.extend([f"**Notes:** {notes}", ""])
        lines.extend([
            "RTBC+1 from my testing.",
            "",
        ])
    elif result == "fail":
        lines.extend([
            f"### Tested {tested_artifact} - Does NOT work",
            "",
            f"**Environment:** {tested_on}",
            "",
            "**Steps tested:**",
            "1. Applied the diff/checked out the MR",
            "2. [Describe what you tested]",
            "",
            "**Result:** The fix does not resolve the issue.",
            "",
            "**Error/behavior observed:**",
            "[Describe what went wrong]",
            "",
        ])
        if notes:
            lines.extend([f"**Notes:** {notes}", ""])
        lines.extend([
            "Setting back to \"Needs work\".",
            "",
        ])
    else:  # partial
        lines.extend([
            f"### Tested {tested_artifact} - Partial success",
            "",
            f"**Environment:** {tested_on}",
            "",
            "**Steps tested:**",
            "1. Applied the diff/checked out the MR",
            "2. [Describe what you tested]",
            "",
            "**Result:** The fix works with caveats.",
            "",
            "**What works:**",
            "- [List what works]",
            "",
            "**What doesn't work:**",
            "- [List issues]",
            "",
        ])
        if notes:
            lines.extend([f"**Notes:** {notes}", ""])

    comment_content = "\n".join(lines)

    # Write to file
    comment_path = output_dir / "TEST_COMMENT.md"
    with open(comment_path, 'w') as f:
        f.write(comment_content)

    print(f"\nTest comment generated: {comment_path}")
    print(f"\nResult: {result.upper()}")
    print(f"Tested: {tested_artifact}")
    print(f"Environment: {tested_on}")

    return EXIT_PROCEED


