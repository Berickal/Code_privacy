"""Assign T_E / T_U / T_H and assemble CorpusRecords (report Section 4.1, 6.3)."""

from __future__ import annotations

import random

from .. import SPLIT_EXPOSED, SPLIT_HOLDOUT, SPLIT_UNEXPOSED
from ..schema import CandidateFile, CorpusRecord, FileFeatures, MatchedPair


class SplitAssigner:
    """Holds out a stratified fraction, then freezes the exposed/unexposed split."""

    def __init__(self, holdout_fraction: float = 0.20, seed: int = 0):
        self.holdout_fraction = holdout_fraction
        self.seed = seed

    def select_holdout(self, features: list[FileFeatures]) -> set[str]:
        rng = random.Random(self.seed)
        holdout: set[str] = set()
        by_stratum: dict[tuple[str, str], list[str]] = {}
        for f in features:
            by_stratum.setdefault((f.language, f.domain), []).append(f.file_id)
        for ids in by_stratum.values():
            ids = sorted(ids)
            rng.shuffle(ids)
            n = int(len(ids) * self.holdout_fraction)
            holdout.update(ids[:n])
        return holdout

    def assemble(
        self,
        candidates: dict[str, CandidateFile],
        features: dict[str, FileFeatures],
        pairs: list[MatchedPair],
        holdout_ids: set[str],
        membership: dict[str, bool],
        clone_free_local: dict[str, bool],
        clone_free_scc: dict[str, bool],
    ) -> list[CorpusRecord]:
        split_of: dict[str, str] = {}
        pair_of: dict[str, str] = {}
        for p in pairs:
            split_of[p.exposed_id] = SPLIT_EXPOSED
            split_of[p.unexposed_id] = SPLIT_UNEXPOSED
            pair_of[p.exposed_id] = p.pair_id
            pair_of[p.unexposed_id] = p.pair_id
        for h in holdout_ids:
            split_of.setdefault(h, SPLIT_HOLDOUT)

        records: list[CorpusRecord] = []
        for file_id, split in split_of.items():
            c, f = candidates[file_id], features[file_id]
            records.append(
                CorpusRecord(
                    file_id=file_id,
                    sha1_git=c.sha1_git,
                    split=split,
                    language=f.language,
                    domain=f.domain,
                    loc=f.loc,
                    cyclomatic=f.cyclomatic,
                    n_functions=f.n_functions,
                    has_docstring=f.has_docstring,
                    matched_pair_id=pair_of.get(file_id, ""),
                    spdx_license=c.spdx_license,
                    first_commit_date=c.first_commit_date,
                    in_stack_v2=membership.get(file_id, False),
                    clone_free_local=clone_free_local.get(file_id, True),
                    clone_free_sourcerercc=clone_free_scc.get(file_id, True),
                    github_repo=c.github_repo,
                    path=c.path,
                    commit_sha=c.commit_sha,
                )
            )
        return records
