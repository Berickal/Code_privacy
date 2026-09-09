"""Software Heritage REST API — independent provenance / timestamp cross-check.

Public endpoints (no token, ~120 req/min):
  * ``/content/sha1_git:X/``          — is this blob archived by SWH?
  * ``/origin/<url>/visits/``          — earliest SWH visit of a repository

Graph endpoints (``/graph/...``) require a **free** API token (request one at
https://archive.softwareheritage.org/api/ → set ``SWH_TOKEN``). Only with a token can
we resolve a blob to its earliest containing revision (``committer_date``) — the exact
independent check the report specifies (Section 6.2.2). Without a token we fall back to
the repository's earliest SWH visit date, which is a weaker but still-independent
existence signal.

All lookups go through :class:`~exposure_gap.oracle.swh_cache.SWHCache`.
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime

import requests

from ..utils import get_logger
from .base import MembershipOracle, TimestampOracle
from .swh_cache import SWHCache

log = get_logger()
BASE = "https://archive.softwareheritage.org/api/1"


def _parse_date(stamp: str | None) -> date | None:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).date()
    except ValueError:
        return None


class SWHRestOracle(TimestampOracle, MembershipOracle):
    def __init__(self, token: str | None = None, cache: SWHCache | None = None):
        self.token = self._clean_token(token or os.environ.get("SWH_TOKEN"))
        self.cache = cache or SWHCache()
        self.session = requests.Session()
        self._auth_dropped = False
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"
        # content endpoint allows ~120/min anon; be conservative
        self._min_interval = 0.15 if self.token else 0.6
        self._last = 0.0

    @staticmethod
    def _clean_token(raw: str | None) -> str | None:
        """Reject placeholder / comment-polluted values (e.g. a stray '# ...')."""
        if not raw:
            return None
        tok = raw.strip().strip('"').strip("'")
        if not tok or tok.startswith("#") or " " in tok or tok.lower() in {"none", "changeme"}:
            return None
        return tok

    def _drop_auth(self, why: str) -> None:
        if not self._auth_dropped:
            log.warning("SWH_TOKEN rejected ({}) — continuing unauthenticated", why)
            self.session.headers.pop("Authorization", None)
            self.token = None
            self._auth_dropped = True
            self._min_interval = 0.6

    @property
    def graph_enabled(self) -> bool:
        return bool(self.token)

    # ------------------------------------------------------------------
    def _get(self, path: str) -> requests.Response | None:
        wait = self._min_interval - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        try:
            resp = self.session.get(f"{BASE}{path}", timeout=30)
        except requests.RequestException as exc:  # pragma: no cover - network
            log.warning("swh request failed: {}", exc)
            return None
        self._last = time.time()
        if resp.status_code in (401, 403) and "Authorization" in self.session.headers:
            self._drop_auth(f"HTTP {resp.status_code}")
            return self._get(path)
        if resp.status_code == 429:
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 30))
            time.sleep(max(reset - time.time(), 1) + 1)
            return self._get(path)
        return resp

    # -- MembershipOracle -------------------------------------------
    def contains(self, sha1_git: str) -> bool:
        cached = self.cache.get_known(sha1_git)
        if cached is not None:
            return cached
        resp = self._get(f"/content/sha1_git:{sha1_git}/")
        known = bool(resp is not None and resp.status_code == 200)
        self.cache.put_known(sha1_git, known)
        return known

    # -- origin visits ------------------------------------------
    def origin_first_visit(
        self, url: str, *, max_pages: int = 8, stop_before: date | None = None
    ) -> tuple[date | None, bool]:
        """Earliest SWH visit date for a repo (visits page newest-first).

        Stops early once a visit older than ``stop_before`` is found (enough to prove
        pre-cutoff existence) or after ``max_pages`` pages (~800 visits) — deep history
        is not worth the request budget when we only need the earliest bound.
        """
        cached = self.cache.get_origin(url)
        if cached is not None:
            return cached
        first: date | None = None
        archived = False
        resp = self._get(f"/origin/{url}/visits/?per_page=100")
        pages = 0
        while resp is not None and resp.status_code == 200 and resp.json():
            archived = True
            page_dates = [d for d in (_parse_date(v.get("date")) for v in resp.json()) if d]
            if page_dates:
                page_min = min(page_dates)
                first = page_min if first is None else min(first, page_min)
            if stop_before and first and first < stop_before:
                break
            pages += 1
            nxt = resp.links.get("next", {}).get("url")
            if not nxt or pages >= max_pages:
                break
            resp = self._get(nxt.replace(BASE, ""))
        self.cache.put_origin(url, first, archived)
        return first, archived

    # -- TimestampOracle ------------------------------------------
    def first_seen(
        self, *, sha1_git: str, repo: str | None = None, path: str | None = None
    ) -> date | None:
        cached = self.cache.get_first_seen(sha1_git)
        if cached is not None:
            return cached[0]

        result: date | None = None
        source = "none"
        if self.graph_enabled:
            result = self._first_seen_via_graph(sha1_git)
            if result is not None:
                source = "graph"
        if result is None and repo:
            url = repo if repo.startswith("http") else f"https://github.com/{repo}"
            result, _ = self.origin_first_visit(url)
            if result is not None:
                source = "origin"
        self.cache.put_first_seen(sha1_git, result, source)
        return result

    def _first_seen_via_graph(self, sha1_git: str) -> date | None:
        walk = self._get(
            f"/graph/randomwalk/backward/swh:1:cnt:{sha1_git}/rev,rel/?limit=5"
        )
        if walk is None or walk.status_code != 200:
            return None
        for line in walk.text.splitlines():
            swhid = line.strip()
            if swhid.startswith("swh:1:rev:"):
                rev = self._get(f"/revision/{swhid.split(':')[-1]}/")
                if rev is not None and rev.status_code == 200:
                    d = _parse_date(
                        rev.json().get("committer_date") or rev.json().get("date")
                    )
                    if d:
                        return d
        return None
