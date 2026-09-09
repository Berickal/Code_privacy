"""Frozen matched-pair construction (report Section 6.3).

Deterministic greedy nearest-neighbour matching within (language, domain,
docstring-presence), enforcing the report's tolerance windows. Run once, before any
model evaluation; the resulting pair IDs are frozen.
"""

from __future__ import annotations

import random

from ..config import MatchingTolerances
from ..schema import FileFeatures, MatchedPair


class PairMatcher:
    def __init__(self, tolerances: MatchingTolerances | None = None, seed: int = 0):
        self.tol = tolerances or MatchingTolerances()
        self.seed = seed

    # ------------------------------------------------------------------
    def _compatible(self, a: FileFeatures, b: FileFeatures) -> bool:
        if (a.language, a.domain, a.has_docstring) != (b.language, b.domain, b.has_docstring):
            return False
        if abs(a.cyclomatic - b.cyclomatic) > self.tol.cyclomatic:
            return False
        if abs(a.n_functions - b.n_functions) > self.tol.n_functions:
            return False
        lo, hi = a.loc * (1 - self.tol.loc_pct), a.loc * (1 + self.tol.loc_pct)
        return lo <= b.loc <= hi

    @staticmethod
    def _distance(a: FileFeatures, b: FileFeatures) -> float:
        return (
            abs(a.loc - b.loc) / max(a.loc, 1)
            + abs(a.cyclomatic - b.cyclomatic) / 5.0
            + abs(a.n_functions - b.n_functions) / 3.0
        )

    # ------------------------------------------------------------------
    def match(
        self, features: list[FileFeatures], exposed_fraction: float = 0.5
    ) -> list[MatchedPair]:
        rng = random.Random(self.seed)
        pool = sorted(features, key=lambda f: f.file_id)
        rng.shuffle(pool)

        used: set[str] = set()
        pairs: list[MatchedPair] = []
        for i, a in enumerate(pool):
            if a.file_id in used:
                continue
            best: tuple[float, FileFeatures] | None = None
            for b in pool[i + 1 :]:
                if b.file_id in used or not self._compatible(a, b):
                    continue
                d = self._distance(a, b)
                if best is None or d < best[0]:
                    best = (d, b)
            if best is None:
                continue
            dist, b = best
            used.update({a.file_id, b.file_id})
            exposed, unexposed = (a, b) if rng.random() < exposed_fraction else (b, a)
            pairs.append(
                MatchedPair(
                    pair_id=f"pair_{len(pairs):04d}",
                    exposed_id=exposed.file_id,
                    unexposed_id=unexposed.file_id,
                    distance=round(dist, 6),
                )
            )
        return pairs

    @staticmethod
    def residual_quality(pairs: list[MatchedPair], features: dict[str, FileFeatures]) -> dict:
        """Report residual matching quality (report Section 15 mitigation)."""
        import statistics

        d_loc, d_cyclo, d_fn = [], [], []
        for p in pairs:
            e, u = features[p.exposed_id], features[p.unexposed_id]
            d_loc.append(abs(e.loc - u.loc))
            d_cyclo.append(abs(e.cyclomatic - u.cyclomatic))
            d_fn.append(abs(e.n_functions - u.n_functions))
        return {
            "n_pairs": len(pairs),
            "loc_abs_diff_mean": statistics.mean(d_loc) if d_loc else 0.0,
            "cyclomatic_abs_diff_mean": statistics.mean(d_cyclo) if d_cyclo else 0.0,
            "n_functions_abs_diff_mean": statistics.mean(d_fn) if d_fn else 0.0,
        }
