"""Synthetic corpus generator for offline tests and the end-to-end smoke test.

Produces structurally-matched exposed/unexposed Python file pairs plus a holdout set.
Exposed and unexposed functions have *different names* but matching structure, so a
memorization-simulating backend can recall exposed idioms without leaking into the
unexposed twin.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date

import pandas as pd

from ..schema import CandidateFile
from ..schema import MatchedPair
from ..utils import git_blob_sha1_text
from .store import CorpusStore

_TEMPLATE = '''\
"""{doc}"""


def {name}(values, factor):
    """{doc}"""
{body}
'''

_OPS = ("v * factor", "v + factor", "v - factor", "v / factor", "v % factor", "v ** factor")
_DOMAINS = ("scientific_computing", "web_backend", "data_engineering")


def _canonical(op: str) -> str:
    return f"    return [{op} for v in values]"


def _idiosyncratic(op: str, idx: int) -> str:
    acc = f"_bucket_{idx}"
    return (
        f"    {acc} = []\n"
        f"    for v in values:\n"
        f"        {acc}.append({op})  # exposure-specific idiom {idx}\n"
        f"    return {acc}"
    )


@dataclass(frozen=True)
class SyntheticFile:
    candidate: CandidateFile
    source: str
    function_name: str
    body: str

    @property
    def file_id(self) -> str:
        return self.candidate.file_id


class SyntheticCorpus:
    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def _file(self, tag: str, idx: int, name: str, body: str, domain: str) -> SyntheticFile:
        doc = f"Scale each element of values by factor (case {idx})."
        source = _TEMPLATE.format(doc=doc, name=name, body=body)
        h = git_blob_sha1_text(source)
        cand = CandidateFile(
            file_id=f"py_{tag}_{idx:03d}_{h[:8]}",
            sha1_git=h,
            github_repo=f"synthetic-{tag}/case-{idx}",
            path=f"src/{name}.py",
            commit_sha=h[:40].ljust(40, "0"),
            language="python",
            domain=domain,
            first_commit_date=date(2024, 6, 1),
            spdx_license=self.rng.choice(["MIT", "Apache-2.0", "GPL-3.0-only"]),
        )
        return SyntheticFile(cand, source, name, body)

    def generate(
        self, n_pairs: int = 8, n_holdout: int = 4
    ) -> tuple[list[SyntheticFile], list[SyntheticFile], list[SyntheticFile]]:
        exposed, unexposed, holdout = [], [], []
        for i in range(n_pairs):
            domain = _DOMAINS[i % len(_DOMAINS)]
            op = _OPS[i % len(_OPS)]
            exposed.append(self._file("E", i, f"transform_{i}", _idiosyncratic(op, i), domain))
            unexposed.append(self._file("U", i, f"scale_{i}", _canonical(op), domain))
        for j in range(n_holdout):
            domain = _DOMAINS[j % len(_DOMAINS)]
            op = _OPS[(j + 2) % len(_OPS)]
            holdout.append(self._file("H", 1000 + j, f"normalize_{j}", _canonical(op), domain))
        return exposed, unexposed, holdout

    def forced_pairs(
        self, exposed: list[SyntheticFile], unexposed: list[SyntheticFile]
    ) -> list[MatchedPair]:
        return [
            MatchedPair(f"pair_{i:04d}", e.file_id, u.file_id, 0.0)
            for i, (e, u) in enumerate(zip(exposed, unexposed))
        ]

    def exposed_impls(self, exposed: list[SyntheticFile]) -> dict[str, str]:
        """function-name -> idiosyncratic body, for MemorizationSimBackend."""
        return {f.function_name: f.body for f in exposed}

    # ------------------------------------------------------------------
    def populate_store(
        self, store: CorpusStore, n_pairs: int = 8, n_holdout: int = 4
    ) -> tuple[list[SyntheticFile], list[SyntheticFile], list[SyntheticFile]]:
        exposed, unexposed, holdout = self.generate(n_pairs, n_holdout)
        rows = []
        for f in [*exposed, *unexposed, *holdout]:
            store.write_source(f.file_id, f.source)
            rows.append({**f.candidate.to_row()})
        store.write_candidates(pd.DataFrame(rows))
        return exposed, unexposed, holdout
