"""Phase A orchestrator: raw files -> frozen ``corpus_metadata.csv``.

Assumes candidate repos/files were already collected and fetched into a
:class:`~exposure_gap.corpus.store.CorpusStore` (``raw/<file_id>.txt`` +
``candidates/corpus_candidates.csv``). This step verifies, deduplicates, extracts
features, matches pairs, and freezes the split.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..config import CorpusConfig
from ..oracle.base import MembershipOracle, NullMembershipOracle, TimestampOracle
from ..schema import CandidateFile, FileFeatures, MatchedPair
from ..utils import get_logger
from .clones import LocalHashDeduper, SourcererCCRunner
from .features import FeatureExtractor
from .matching import PairMatcher
from .split import SplitAssigner
from .store import CorpusStore

log = get_logger()


@dataclass
class CorpusBuildReport:
    n_candidates: int
    n_with_source: int
    n_post_cutoff: int
    n_stack_v2_hits: int
    n_clone_free: int
    n_pairs: int
    n_holdout: int
    residual_quality: dict
    gate1_pass: bool
    gate1_detail: dict


class CorpusBuilder:
    def __init__(
        self,
        config: CorpusConfig,
        store: CorpusStore,
        membership_oracle: MembershipOracle | None = None,
        timestamp_oracle: TimestampOracle | None = None,
        sourcerercc: SourcererCCRunner | None = None,
    ):
        self.config = config
        self.store = store
        self.membership = membership_oracle or NullMembershipOracle()
        self.timestamps = timestamp_oracle
        self.extractor = FeatureExtractor()
        self.local_dedupe = LocalHashDeduper()
        self.sourcerercc = sourcerercc or SourcererCCRunner()
        self.matcher = PairMatcher(config.matching, seed=config.seed)
        self.splitter = SplitAssigner(config.holdout_fraction, seed=config.seed)

    # ------------------------------------------------------------------
    def _load_candidates(self) -> dict[str, CandidateFile]:
        df = self.store.read_candidates()
        out: dict[str, CandidateFile] = {}
        for _, row in df.iterrows():
            if not self.store.has_source(row["file_id"]):
                continue
            out[row["file_id"]] = CandidateFile(
                file_id=row["file_id"],
                sha1_git=row["sha1_git"],
                github_repo=row["github_repo"],
                path=row["path"],
                commit_sha=row["commit_sha"],
                language=row["language"],
                domain=row["domain"],
                first_commit_date=pd.to_datetime(row.get("first_commit_date")).date()
                if pd.notna(row.get("first_commit_date"))
                else None,
                spdx_license=row.get("spdx_license"),
            )
        return out

    def _verify_post_cutoff(self, candidates: dict[str, CandidateFile]) -> dict[str, CandidateFile]:
        if self.timestamps is None:
            log.warning("no timestamp oracle — trusting candidate first_commit_date")
            return {
                fid: c
                for fid, c in candidates.items()
                if c.first_commit_date and c.first_commit_date > self.config.cutoff_date
            }
        kept: dict[str, CandidateFile] = {}
        for fid, c in candidates.items():
            d = self.timestamps.first_seen(sha1_git=c.sha1_git, repo=c.github_repo, path=c.path)
            if d is None:
                d = c.first_commit_date
            if d and d > self.config.cutoff_date:
                kept[fid] = CandidateFile(**{**c.__dict__, "first_commit_date": d})
        log.info("post-cutoff verified: {}/{}", len(kept), len(candidates))
        return kept

    # ------------------------------------------------------------------
    def run(
        self,
        forced_pairs: list["MatchedPair"] | None = None,
        forced_holdout: set[str] | None = None,
    ) -> CorpusBuildReport:
        """Build the frozen split.

        ``forced_pairs`` / ``forced_holdout`` bypass structural matching — used to
        re-freeze an existing split or to drive a synthetic corpus with a known
        exposure assignment.
        """
        candidates = self._load_candidates()
        n_candidates = len(candidates)
        sources = {fid: self.store.read_source(fid) for fid in candidates}

        candidates = self._verify_post_cutoff(candidates)
        n_post_cutoff = len(candidates)

        membership = {
            fid: self.membership.contains(c.sha1_git) for fid, c in candidates.items()
        }
        n_hits = sum(membership.values())
        if n_hits:
            log.warning("{} post-cutoff files hit The Stack v2 bloom — inspect", n_hits)
        candidates = {fid: c for fid, c in candidates.items() if not membership[fid]}

        # clone filters
        local_clone_ids = self.local_dedupe.clone_ids(
            [(fid, c.sha1_git, c.github_repo) for fid, c in candidates.items()]
        )
        scc_clone_ids = self.sourcerercc.clone_ids(
            {fid: sources[fid] for fid in candidates},
            {fid: candidates[fid].language for fid in candidates},
        )
        clone_free_local = {fid: fid not in local_clone_ids for fid in candidates}
        clone_free_scc = {fid: fid not in scc_clone_ids for fid in candidates}
        clean = {
            fid: c
            for fid, c in candidates.items()
            if clone_free_local[fid] and clone_free_scc[fid]
        }
        n_clone_free = len(clean)
        log.info("clone-free after both filters: {}", n_clone_free)

        features = {
            fid: self.extractor.extract(fid, sources[fid], c.language, c.domain)
            for fid, c in clean.items()
        }

        # reproduction targets must contain at least one function (report Section 8.1)
        min_fn = self.config.min_functions
        below = [fid for fid, f in features.items() if f.n_functions < min_fn]
        if below:
            log.info("dropping {} clone-free files with < {} functions", len(below), min_fn)
            for fid in below:
                features.pop(fid)
                clean.pop(fid, None)

        if forced_pairs is not None:
            holdout_ids = {h for h in (forced_holdout or set()) if h in features}
            pairs = [
                p
                for p in forced_pairs
                if p.exposed_id in features and p.unexposed_id in features
            ]
        else:
            holdout_ids = self.splitter.select_holdout(list(features.values()))
            pool = [f for fid, f in features.items() if fid not in holdout_ids]
            pairs = self.matcher.match(pool, self.config.exposed_fraction)

        records = self.splitter.assemble(
            candidates=clean,
            features=features,
            pairs=pairs,
            holdout_ids=holdout_ids,
            membership=membership,
            clone_free_local=clone_free_local,
            clone_free_scc=clone_free_scc,
        )
        self.store.write_metadata(records)

        residual = self.matcher.residual_quality(pairs, features)
        gate_pass, gate_detail = self._gate1(pairs, features)
        report = CorpusBuildReport(
            n_candidates=n_candidates,
            n_with_source=len(sources),
            n_post_cutoff=n_post_cutoff,
            n_stack_v2_hits=n_hits,
            n_clone_free=n_clone_free,
            n_pairs=len(pairs),
            n_holdout=len(holdout_ids),
            residual_quality=residual,
            gate1_pass=gate_pass,
            gate1_detail=gate_detail,
        )
        log.info("corpus build report: {}", report)
        return report

    def _gate1(self, pairs, features: dict[str, FileFeatures]) -> tuple[bool, dict]:
        per_lang: dict[str, int] = {}
        domains: set[str] = set()
        for p in pairs:
            f = features[p.exposed_id]
            per_lang[f.language] = per_lang.get(f.language, 0) + 1
            domains.add(f.domain)
        crit = self.config.gate1
        ok = all(
            per_lang.get(lang, 0) >= crit.min_matched_pairs_per_language
            for lang in self.config.languages
        ) and len(domains) >= crit.min_domains
        return ok, {"pairs_per_language": per_lang, "n_domains": len(domains)}
