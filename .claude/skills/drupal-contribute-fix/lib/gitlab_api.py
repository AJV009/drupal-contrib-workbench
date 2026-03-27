"""
GitLab API client for git.drupalcode.org.

Uses only stdlib (urllib, json, time) to minimize dependencies.
Handles MR search, metadata, diffs, and notes with rate limiting and pagination.
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Optional, Dict, List

# GitLab configuration
GITLAB_BASE = "https://git.drupalcode.org"
API_BASE = f"{GITLAB_BASE}/api/v4"
USER_AGENT = "drupal-contribute-fix/1.0 (drupal.org contribution helper)"

# Rate limiting: 0.5s between requests
MIN_REQUEST_INTERVAL = 0.5
_last_request_time = 0.0


class GitLabAPIError(Exception):
    """Exception for GitLab API errors."""
    pass


class GitLabAPI:
    """Client for git.drupalcode.org GitLab API (v4)."""

    def __init__(self, token: Optional[str] = None):
        """
        Initialize the GitLab API client.

        Args:
            token: GitLab private access token. Required for some endpoints (e.g., notes).
        """
        self.token = token

    @classmethod
    def from_token_file(cls, token_path: str) -> 'GitLabAPI':
        """
        Create a client by reading a token from a file.

        If the file does not exist, returns a client with no token.

        Args:
            token_path: Path to file containing the GitLab private token.

        Returns:
            GitLabAPI instance.
        """
        path = Path(token_path)
        if not path.exists():
            return cls(token=None)

        try:
            token = path.read_text().strip()
            return cls(token=token if token else None)
        except OSError:
            return cls(token=None)

    def _encode_project(self, project: str) -> str:
        """
        URL-encode a project path for GitLab API URLs.

        GitLab requires project paths like 'project/ai' to be encoded as
        'project%2Fai' in API URLs.

        Args:
            project: Project short name (e.g., 'ai', 'canvas').

        Returns:
            URL-encoded full project path.
        """
        full_path = f"project/{project}"
        return urllib.parse.quote(full_path, safe='')

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        global _last_request_time
        now = time.time()
        elapsed = now - _last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        _last_request_time = time.time()

    def _request(self, endpoint: str, params: Optional[Dict] = None,
                 paginate: bool = False, per_page: int = 100) -> any:
        """
        Make an API request with rate limiting and optional pagination.

        Args:
            endpoint: API endpoint path (appended to API_BASE).
            params: Query parameters.
            paginate: If True, follow all pages and concatenate list results.
            per_page: Items per page when paginating.

        Returns:
            JSON response (dict or list). When paginating, returns concatenated list.
        """
        params = dict(params) if params else {}

        if paginate:
            params['per_page'] = per_page
            # First page
            first_result, headers = self._do_request(endpoint, params)
            if not isinstance(first_result, list):
                return first_result

            all_results = list(first_result)

            # Check total pages from response headers
            total_pages_str = headers.get('x-total-pages', '1')
            try:
                total_pages = int(total_pages_str)
            except (ValueError, TypeError):
                total_pages = 1

            # Fetch remaining pages
            for page in range(2, total_pages + 1):
                params['page'] = page
                page_result, _ = self._do_request(endpoint, params)
                if isinstance(page_result, list):
                    all_results.extend(page_result)

            return all_results
        else:
            result, _ = self._do_request(endpoint, params)
            return result

    def _do_request(self, endpoint: str, params: Optional[Dict] = None):
        """
        Execute a single HTTP request against the GitLab API.

        Args:
            endpoint: API endpoint path.
            params: Query parameters.

        Returns:
            Tuple of (parsed JSON, response headers dict).
        """
        self._rate_limit()

        url = f"{API_BASE}/{endpoint}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        request = urllib.request.Request(url)
        request.add_header("User-Agent", USER_AGENT)
        request.add_header("Accept", "application/json")
        if self.token:
            request.add_header("PRIVATE-TOKEN", self.token)

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
                # Extract headers as a simple dict
                headers = {k.lower(): v for k, v in response.getheaders()}
                return data, headers
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise GitLabAPIError("Authentication required: invalid or missing token")
            raise GitLabAPIError(f"GitLab API request failed: {e.code} {e.reason} ({url})")
        except urllib.error.URLError as e:
            raise GitLabAPIError(f"Network error: {e.reason}")

    def search_merge_requests(self, project: str, issue_id: int) -> List[Dict]:
        """
        Search for merge requests related to a drupal.org issue.

        Args:
            project: Project short name (e.g., 'ai', 'drupal').
            issue_id: Drupal.org issue node ID to search for.

        Returns:
            List of merge request dicts matching the search.
        """
        encoded = self._encode_project(project)
        endpoint = f"projects/{encoded}/merge_requests"
        params = {
            'search': str(issue_id),
            'state': 'all',
        }
        return self._request(endpoint, params, paginate=True)

    def get_merge_request(self, project: str, iid: int) -> Dict:
        """
        Get metadata for a single merge request.

        Args:
            project: Project short name.
            iid: Merge request IID (project-scoped ID, not global ID).

        Returns:
            Merge request metadata dict.
        """
        encoded = self._encode_project(project)
        endpoint = f"projects/{encoded}/merge_requests/{iid}"
        return self._request(endpoint)

    def get_mr_diffs(self, project: str, iid: int) -> List[Dict]:
        """
        Get the diffs for a merge request as structured JSON.

        Args:
            project: Project short name.
            iid: Merge request IID.

        Returns:
            List of diff dicts (one per changed file).
        """
        encoded = self._encode_project(project)
        endpoint = f"projects/{encoded}/merge_requests/{iid}/diffs"
        return self._request(endpoint, paginate=True, per_page=100)

    def get_mr_plain_diff(self, project: str, iid: int) -> str:
        """
        Get the raw plain-text diff for a merge request.

        This uses the web URL format, not the API, and returns raw text.

        Args:
            project: Project short name.
            iid: Merge request IID.

        Returns:
            Raw unified diff as a string.
        """
        self._rate_limit()

        url = f"{GITLAB_BASE}/project/{project}/-/merge_requests/{iid}.diff"

        request = urllib.request.Request(url)
        request.add_header("User-Agent", USER_AGENT)
        if self.token:
            request.add_header("PRIVATE-TOKEN", self.token)

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise GitLabAPIError("Authentication required: invalid or missing token")
            raise GitLabAPIError(f"Failed to fetch plain diff: {e.code} {e.reason} ({url})")
        except urllib.error.URLError as e:
            raise GitLabAPIError(f"Network error: {e.reason}")

    def get_mr_notes(self, project: str, iid: int) -> List[Dict]:
        """
        Get all notes (comments) on a merge request.

        Requires authentication (PRIVATE-TOKEN).

        Args:
            project: Project short name.
            iid: Merge request IID.

        Returns:
            List of note dicts sorted by creation date ascending.

        Raises:
            GitLabAPIError: If no token is configured.
        """
        if not self.token:
            raise GitLabAPIError(
                "Authentication required: MR notes endpoint requires a PRIVATE-TOKEN. "
                "Use GitLabAPI.from_token_file() or pass token to constructor."
            )

        encoded = self._encode_project(project)
        endpoint = f"projects/{encoded}/merge_requests/{iid}/notes"
        params = {
            'sort': 'asc',
            'order_by': 'created_at',
        }
        return self._request(endpoint, params, paginate=True)
