"""Patch and MR URL extraction utilities."""
from typing import List
import re

# These functions need DrupalOrgAPI passed as a parameter
# (originally imported at module level in contribute_fix.py)
def _extract_patch_urls_from_files(api: DrupalOrgAPI, files: List) -> List[str]:
    """Extract patch/diff URLs from file references."""
    patch_urls = []
    for file_ref in files or []:
        fid = None
        if isinstance(file_ref, dict):
            fid = file_ref.get("fid") or file_ref.get("id")
            if not fid and file_ref.get("url"):
                url = file_ref.get("url", "")
                if url.endswith((".patch", ".diff")):
                    patch_urls.append(url)
                continue
        elif isinstance(file_ref, (int, str)) and str(file_ref).isdigit():
            fid = int(file_ref)

        if fid:
            try:
                file_data = api.get_file(int(fid))
                filename = file_data.get("filename", "")
                url = file_data.get("url", "")
                if filename.endswith((".patch", ".diff")) and url:
                    patch_urls.append(url)
            except Exception:
                continue

    return patch_urls



def collect_patch_urls(api: DrupalOrgAPI, issue_nid: int, issue_data: dict) -> List[str]:
    """Collect patch URLs from issue node and comments."""
    urls = []

    # Node attachments (field_issue_files or legacy upload field)
    node_files = issue_data.get("field_issue_files") or issue_data.get("upload") or []
    urls.extend(_extract_patch_urls_from_files(api, node_files))

    # Comment attachments (most Drupal patches are here)
    try:
        comments = api.get_comments(issue_nid)
        for comment in comments:
            comment_files = comment.get("field_comment_upload") or comment.get("upload") or []
            urls.extend(_extract_patch_urls_from_files(api, comment_files))
    except Exception:
        pass

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            deduped.append(url)

    return deduped



def extract_mr_urls(related_mrs: List) -> List[str]:
    """Extract MR URLs from mixed related_mrs payloads (dicts and/or strings)."""
    urls = []
    for mr in related_mrs or []:
        if isinstance(mr, str):
            if mr:
                urls.append(mr)
            continue
        if isinstance(mr, dict):
            url = mr.get("url")
            if url:
                urls.append(url)

    seen = set()
    return [u for u in urls if not (u in seen or seen.add(u))]



