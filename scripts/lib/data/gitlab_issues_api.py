"""
GitLab issues API client for git.drupalcode.org.

Thin client to read (and optionally post to) GitLab work-item issues using
only stdlib (urllib, json, time). Mirrors gitlab_api.py conventions:
from_token_file, rate-limit throttle, project URL-encoding, PRIVATE-TOKEN
header handling, and pagination.
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Optional, Dict, List

GITLAB_API = "https://git.drupalcode.org/api/v4"
USER_AGENT = "drupal-contribute-fix/1.0 (drupal.org contribution helper)"
MIN_REQUEST_INTERVAL = 0.5


class GitLabIssuesError(Exception):
    """Exception for GitLab issues API errors."""
    pass


class GitLabIssuesAPI:
    """Client for reading and posting GitLab issues on git.drupalcode.org."""

    def __init__(self, token: Optional[str] = None):
        """
        Initialize the GitLab issues API client.

        Args:
            token: GitLab private access token. Required for posting notes.
        """
        self.token = token
        self._last = 0.0

    @classmethod
    def from_token_file(cls, token_path: str) -> 'GitLabIssuesAPI':
        """
        Create a client by reading a token from a file.

        If the file is missing, unreadable, or empty, returns a client with
        no token.

        Args:
            token_path: Path to file containing the GitLab private token.

        Returns:
            GitLabIssuesAPI instance.
        """
        path = Path(token_path)
        if not path.exists():
            return cls(token=None)

        try:
            token = path.read_text().strip()
            return cls(token=token if token else None)
        except OSError:
            return cls(token=None)

    @staticmethod
    def _encode_project(project: str) -> str:
        """
        URL-encode a project path for GitLab API URLs.

        Args:
            project: Full project path (e.g., 'project/canvas').

        Returns:
            URL-encoded project path.
        """
        return urllib.parse.quote(project, safe="")

    def _throttle(self) -> None:
        """Enforce the minimum interval between requests."""
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self._last = time.monotonic()

    def _request(self, path: str, method: str = "GET", data: Optional[bytes] = None):
        """
        Make a single API request with throttling.

        Args:
            path: API path appended to GITLAB_API.
            method: HTTP method.
            data: Optional request body bytes (JSON).

        Returns:
            Parsed JSON response, or None if the body is empty.

        Raises:
            GitLabIssuesError: On HTTP errors.
        """
        self._throttle()

        url = f"{GITLAB_API}/{path}"
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if self.token:
            headers["PRIVATE-TOKEN"] = self.token
        if data is not None:
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, method=method, data=data, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                body = response.read().decode("utf-8")
                if not body:
                    return None
                return json.loads(body)
        except urllib.error.HTTPError as e:
            raise GitLabIssuesError(
                f"GitLab {method} {path} -> HTTP {e.code}: {e.reason}"
            )

    def get_issue(self, project: str, iid) -> Dict:
        """
        Get metadata for a single issue.

        Args:
            project: Full project path (e.g., 'project/canvas').
            iid: Issue IID (project-scoped).

        Returns:
            Issue metadata dict.
        """
        enc = self._encode_project(project)
        return self._request(f"projects/{enc}/issues/{iid}")

    def get_issue_notes(self, project: str, iid) -> List[Dict]:
        """
        Get all notes (comments) on an issue, paginating until exhausted.

        Args:
            project: Full project path.
            iid: Issue IID.

        Returns:
            Combined list of note dicts.
        """
        enc = self._encode_project(project)
        all_notes: List[Dict] = []
        page = 1
        while True:
            result = self._request(
                f"projects/{enc}/issues/{iid}/notes?per_page=100&sort=asc&page={page}"
            )
            if not result:
                break
            all_notes.extend(result)
            if len(result) < 100:
                break
            page += 1
        return all_notes

    def get_resource_label_events(self, project: str, iid) -> List[Dict]:
        """
        Get resource label events (status/tag changes) on an issue.

        Args:
            project: Full project path.
            iid: Issue IID.

        Returns:
            List of resource label event dicts.
        """
        enc = self._encode_project(project)
        return self._request(
            f"projects/{enc}/issues/{iid}/resource_label_events?per_page=100"
        ) or []

    def search_project_issues(self, project: str, keywords: str) -> List[Dict]:
        """
        Search issues within a single project.

        Args:
            project: Full project path.
            keywords: Search string.

        Returns:
            List of matching issue dicts.
        """
        enc = self._encode_project(project)
        q = urllib.parse.urlencode({"search": keywords, "per_page": 20, "state": "all"})
        return self._request(f"projects/{enc}/issues?{q}") or []

    def search_global_issues(self, keywords: str) -> List[Dict]:
        """
        Search issues across all accessible projects.

        Args:
            keywords: Search string.

        Returns:
            List of matching issue dicts.
        """
        q = urllib.parse.urlencode({"search": keywords, "scope": "all", "per_page": 20})
        return self._request(f"issues?{q}") or []

    def post_issue_note(self, project: str, iid, body: str) -> Dict:
        """
        Post a note (comment) to an issue.

        Args:
            project: Full project path.
            iid: Issue IID.
            body: Note body text.

        Returns:
            The created note dict.

        Raises:
            GitLabIssuesError: If no write-scoped token is configured.
        """
        if not self.token:
            raise GitLabIssuesError(
                "posting a note requires a write-scoped PRIVATE-TOKEN"
            )
        enc = self._encode_project(project)
        data = json.dumps({"body": body}).encode()
        return self._request(
            f"projects/{enc}/issues/{iid}/notes", method="POST", data=data
        )
