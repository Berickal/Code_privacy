"""Timestamp oracle backed by GitHub commit history.

The earliest commit that touched a path is a good proxy for when that file first
appeared. Force-pushes / history rewrites can move it earlier; the SWH REST
cross-check (a 20% sample) catches the important cases.
"""

from __future__ import annotations

from datetime import date, datetime

from .base import TimestampOracle
from .github_client import GitHubClient


class GitHubTimestampOracle(TimestampOracle):
    def __init__(self, client: GitHubClient | None = None):
        self.client = client or GitHubClient()

    def first_seen(
        self, *, sha1_git: str, repo: str | None = None, path: str | None = None
    ) -> date | None:
        if not repo or not path:
            return None
        # Walk to the last page of the commit list for this path -> oldest commit.
        resp = self.client.get(
            f"/repos/{repo}/commits", params={"path": path, "per_page": 1}
        )
        if resp.status_code != 200:
            return None
        last = resp.links.get("last", {}).get("url")
        if last:
            resp = self.client.get(last)
        commits = resp.json()
        if not commits:
            return None
        oldest = commits[-1]
        stamp = (
            oldest.get("commit", {}).get("committer", {}).get("date")
            or oldest.get("commit", {}).get("author", {}).get("date")
        )
        if not stamp:
            return None
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).date()

    def repo_created(self, repo: str) -> date | None:
        resp = self.client.get(f"/repos/{repo}")
        if resp.status_code != 200:
            return None
        return datetime.fromisoformat(resp.json()["created_at"].replace("Z", "+00:00")).date()
