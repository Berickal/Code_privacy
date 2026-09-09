"""Clone detection — the report's #1 internal-validity threat (Section 6.3, 15).

Two independent filters, both must pass:

1. :class:`LocalHashDeduper` — exact ``sha1_git`` duplication across repos (Type-1 at
   content-hash level; replaces SWH Athena Q3 in the no-AWS build).
2. :class:`SourcererCCRunner` — Type-1 + Type-2 near-duplicates. Uses the real
   SourcererCC jar when ``$SOURCERERCC_JAR`` is set, otherwise a normalized-token
   Jaccard approximation at the Type-2 threshold.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from itertools import combinations
from pathlib import Path

from ..utils import get_logger

log = get_logger()

_TOKEN = re.compile(r"[A-Za-z_]\w*|\d+|[^\s\w]")
TYPE2_JACCARD = 0.70
SHINGLE_K = 5
_PY_KEYWORDS = frozenset(__import__("keyword").kwlist)


class LocalHashDeduper:
    """Group by ``sha1_git``; any hash seen in >1 distinct repo is a clone."""

    def clone_ids(self, records: list[tuple[str, str, str]]) -> set[str]:
        """``records`` = list of (file_id, sha1_git, repo)."""
        by_hash: dict[str, set[str]] = {}
        hash_of: dict[str, str] = {}
        for file_id, sha1_git, repo in records:
            by_hash.setdefault(sha1_git, set()).add(repo)
            hash_of[file_id] = sha1_git
        bad_hashes = {h for h, repos in by_hash.items() if len(repos) > 1}
        return {fid for fid, h in hash_of.items() if h in bad_hashes}


class SourcererCCRunner:
    def __init__(self, jar_path: str | None = None, type2_threshold: float = TYPE2_JACCARD):
        self.jar_path = jar_path or os.environ.get("SOURCERERCC_JAR")
        self.type2_threshold = type2_threshold

    def clone_ids(self, sources: dict[str, str], languages: dict[str, str]) -> set[str]:
        if self.jar_path and Path(self.jar_path).exists():
            return self._run_jar(sources)
        log.warning(
            "SOURCERERCC_JAR unset — using {}-shingle Jaccard Type-2 approximation "
            "(install the jar for the real study run)",
            SHINGLE_K,
        )
        return self._approx(sources, languages)

    # ------------------------------------------------------------------
    @staticmethod
    def _normalise_stream(src: str) -> list[str]:
        """Ordered token stream with identifiers/literals collapsed (Type-2)."""
        src = re.sub(r"#.*", "", src)
        src = re.sub(r"//.*", "", src)
        src = re.sub(r'(""".*?"""|\'\'\'.*?\'\'\')', "", src, flags=re.S)
        out = []
        for t in _TOKEN.findall(src):
            if t.isidentifier():
                out.append("KW" if t in _PY_KEYWORDS else "ID")
            elif t.isdigit():
                out.append("NUM")
            else:
                out.append(t)
        return out

    @classmethod
    def _shingles(cls, src: str) -> set[tuple[str, ...]]:
        toks = cls._normalise_stream(src)
        if len(toks) < SHINGLE_K:
            return {tuple(toks)} if toks else set()
        return {tuple(toks[i : i + SHINGLE_K]) for i in range(len(toks) - SHINGLE_K + 1)}

    def _approx(self, sources: dict[str, str], languages: dict[str, str]) -> set[str]:
        shingles = {fid: self._shingles(text) for fid, text in sources.items()}
        clones: set[str] = set()
        for a, b in combinations(shingles, 2):
            if languages.get(a) != languages.get(b):
                continue
            sa, sb = shingles[a], shingles[b]
            if not sa or not sb:
                continue
            union = len(sa | sb) or 1
            if len(sa & sb) / union >= self.type2_threshold:
                clones.update({a, b})
        return clones

    def _run_jar(self, sources: dict[str, str]) -> set[str]:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for fid, text in sources.items():
                (root / f"{fid}.py").write_text(text)
            subprocess.run(
                ["java", "-jar", self.jar_path, "input", str(root)],
                check=True, capture_output=True,
            )
            pairs_file = root / "clone_pairs.txt"
            ids: set[str] = set()
            if pairs_file.exists():
                for ln in pairs_file.read_text().splitlines():
                    ids.update(ln.strip().split(",")[:2])
            return ids
