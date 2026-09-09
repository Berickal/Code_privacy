"""Minimal GitHub REST client: auth, retry, rate-limit handling, pagination."""

from __future__ import annotations

import os
import time
from typing import Any, Iterator

import requests

from ..utils import get_logger

log = get_logger()
API = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str | None = None, *, session: requests.Session | None = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.session = session or requests.Session()
        self.session.headers.update({"Accept": "application/vnd.github+json"})
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"

    def get(self, path: str, *, params: dict | None = None, max_retries: int = 5) -> requests.Response:
        url = path if path.startswith("http") else f"{API}{path}"
        resp: requests.Response | None = None
        for attempt in range(max_retries):
            try:
                resp = self.session.get(url, params=params, timeout=30)
            except requests.RequestException as exc:
                wait = 2 ** attempt
                log.warning("github request error ({}); retry in {}s", exc.__class__.__name__, wait)
                time.sleep(wait)
                continue
            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait = max(reset - time.time(), 1) + 1
                log.warning("github rate limit; sleeping {:.0f}s", wait)
                time.sleep(wait)
                continue
            if resp.status_code in (502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            return resp
        if resp is None:
            raise requests.ConnectionError(f"github: {url} failed after {max_retries} retries")
        return resp

    def paginate(self, path: str, *, params: dict | None = None, cap: int | None = None) -> Iterator[dict]:
        params = dict(params or {})
        params.setdefault("per_page", 100)
        seen = 0
        url: str | None = path
        while url:
            resp = self.get(url, params=params if url == path else None)
            resp.raise_for_status()
            payload: Any = resp.json()
            items = payload["items"] if isinstance(payload, dict) and "items" in payload else payload
            for it in items:
                yield it
                seen += 1
                if cap and seen >= cap:
                    return
            url = resp.links.get("next", {}).get("url")
            time.sleep(0.5)

    def rate_limit_remaining(self) -> int:
        try:
            return int(self.get("/rate_limit").json()["resources"]["core"]["remaining"])
        except (KeyError, ValueError, TypeError):
            return -1

    @property
    def authenticated(self) -> bool:
        return self.get("/user").status_code == 200
