"""
Raw file download helper — for fetching non-API content from drupal.org
or git.drupalcode.org that the API clients don't cover.

Use cases:
  - Fetching a raw composer.json from a project branch (ddev setup)
  - Downloading an arbitrary .patch file (contribute_fix reroll)

NOT for:
  - API endpoints — use drupalorg_api.DrupalOrgAPI or gitlab_api.GitLabAPI
  - Issue metadata, comments, MR data — use fetch_issue.py modes

This module is intentionally minimal: urllib with User-Agent and timeout,
no caching, no rate limiting. Raw file downloads are infrequent enough that
per-call throttling is unnecessary, and caching doesn't help because the
caller usually wants the latest content.
"""

import urllib.request
import urllib.error
from typing import Optional


DEFAULT_USER_AGENT = "drupal-workbench/1.0 (contrib helper)"
DEFAULT_TIMEOUT = 30


class RawFetchError(Exception):
    """Raised when a raw file fetch fails."""
    pass


def download_raw_file(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
    user_agent: Optional[str] = None,
) -> str:
    """
    Download a raw file from a URL and return its content as a string.

    Args:
        url: Full URL to fetch (http:// or https://)
        timeout: Request timeout in seconds (default 30)
        user_agent: Override the default User-Agent header

    Returns:
        The response body decoded as UTF-8.

    Raises:
        RawFetchError: On HTTP errors, network errors, or decode failures.
    """
    ua = user_agent or DEFAULT_USER_AGENT
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as e:
        raise RawFetchError(f"HTTP {e.code} fetching {url}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise RawFetchError(f"Network error fetching {url}: {e.reason}") from e
    except Exception as e:
        raise RawFetchError(f"Unexpected error fetching {url}: {e}") from e

    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as e:
        raise RawFetchError(f"Response from {url} is not valid UTF-8: {e}") from e


def download_raw_file_bytes(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
    user_agent: Optional[str] = None,
) -> bytes:
    """
    Same as download_raw_file but returns raw bytes (no UTF-8 decode).

    Use this for binary files or when the caller wants to control decoding.
    """
    ua = user_agent or DEFAULT_USER_AGENT
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as e:
        raise RawFetchError(f"HTTP {e.code} fetching {url}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise RawFetchError(f"Network error fetching {url}: {e.reason}") from e
    except Exception as e:
        raise RawFetchError(f"Unexpected error fetching {url}: {e}") from e
