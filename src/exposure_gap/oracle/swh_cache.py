"""Persistent SQLite cache for Software Heritage lookups.

SWH REST responses are stable (an archived object does not change), so every lookup is
cached forever. Lets the corpus pipeline re-run for free and keeps us well under the
rate limit on incremental runs.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS content_known (
    sha1_git TEXT PRIMARY KEY,
    known    INTEGER NOT NULL,
    fetched_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS origin_first_visit (
    url          TEXT PRIMARY KEY,
    first_visit  TEXT,          -- ISO date or NULL
    archived     INTEGER NOT NULL,
    fetched_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS content_first_seen (
    sha1_git    TEXT PRIMARY KEY,
    first_seen  TEXT,           -- ISO date or NULL
    source      TEXT NOT NULL,  -- "graph" | "origin" | "none"
    fetched_at  TEXT NOT NULL
);
"""


class SWHCache:
    def __init__(self, path: str | Path = "corpus/swh_cache.sqlite"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- content_known -------------------------------------------------
    def get_known(self, sha1_git: str) -> bool | None:
        row = self._conn.execute(
            "SELECT known FROM content_known WHERE sha1_git=?", (sha1_git,)
        ).fetchone()
        return None if row is None else bool(row[0])

    def put_known(self, sha1_git: str, known: bool) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO content_known VALUES (?,?,datetime('now'))",
            (sha1_git, int(known)),
        )
        self._conn.commit()

    # -- origin_first_visit --------------------------------------
    def get_origin(self, url: str) -> tuple[date | None, bool] | None:
        row = self._conn.execute(
            "SELECT first_visit, archived FROM origin_first_visit WHERE url=?", (url,)
        ).fetchone()
        if row is None:
            return None
        return (date.fromisoformat(row[0]) if row[0] else None, bool(row[1]))

    def put_origin(self, url: str, first_visit: date | None, archived: bool) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO origin_first_visit VALUES (?,?,?,datetime('now'))",
            (url, first_visit.isoformat() if first_visit else None, int(archived)),
        )
        self._conn.commit()

    # -- content_first_seen -------------------------------------
    def get_first_seen(self, sha1_git: str) -> tuple[date | None, str] | None:
        row = self._conn.execute(
            "SELECT first_seen, source FROM content_first_seen WHERE sha1_git=?", (sha1_git,)
        ).fetchone()
        if row is None:
            return None
        return (date.fromisoformat(row[0]) if row[0] else None, row[1])

    def put_first_seen(self, sha1_git: str, first_seen: date | None, source: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO content_first_seen VALUES (?,?,?,datetime('now'))",
            (sha1_git, first_seen.isoformat() if first_seen else None, source),
        )
        self._conn.commit()

    # -- export -----------------------------------------------------
    def dump(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for table in ("content_known", "origin_first_visit", "content_first_seen"):
            cur = self._conn.execute(f"SELECT * FROM {table}")
            cols = [d[0] for d in cur.description]
            out[table] = [dict(zip(cols, r)) for r in cur.fetchall()]
        return out

    def to_json(self, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(json.dumps(self.dump(), indent=2))
        return p

    def close(self) -> None:
        self._conn.close()
