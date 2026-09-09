"""RQ5 dose-response (report Section 12.4).

One-sided Jonckheere-Terpstra trend test over k in {1,5,25} plus a
diminishing-returns contrast (marginal gain 1->5 vs 5->25).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class DoseResponseResult:
    task: str
    metric: str
    model: str
    prompt: str
    jt_z: float
    jt_p_value: float
    mean_delta_k1: float
    mean_delta_k5: float
    mean_delta_k25: float
    marginal_1_to_5: float
    marginal_5_to_25: float
    diminishing_returns: bool

    def to_row(self) -> dict:
        return asdict(self)


class DoseResponseAnalyzer:
    @staticmethod
    def _jonckheere(groups: list[np.ndarray]) -> tuple[float, float]:
        u = 0.0
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                gi, gj = groups[i][:, None], groups[j][None, :]
                u += np.sum(gj > gi) + 0.5 * np.sum(gj == gi)
        ns = np.array([len(g) for g in groups], dtype=float)
        n = ns.sum()
        mean = (n**2 - np.sum(ns**2)) / 4.0
        var = (n**2 * (2 * n + 3) - np.sum(ns**2 * (2 * ns + 3))) / 72.0
        z = (u - mean) / np.sqrt(var) if var > 0 else 0.0
        return float(z), float(stats.norm.sf(z))

    def analyse_one(
        self, diffs_by_k: dict[int, np.ndarray], *, task: str, metric: str, model: str, prompt: str
    ) -> DoseResponseResult:
        ks = sorted(diffs_by_k)
        groups = [np.asarray(diffs_by_k[k], dtype=float) for k in ks]
        z, p = self._jonckheere(groups)
        means = {k: float(np.mean(diffs_by_k[k])) for k in ks}
        m1, m5, m25 = means.get(1, np.nan), means.get(5, np.nan), means.get(25, np.nan)
        marg_15 = m5 - m1
        marg_525 = m25 - m5
        return DoseResponseResult(
            task, metric, model, prompt, z, p, m1, m5, m25,
            marg_15, marg_525, bool(marg_525 < marg_15),
        )

    def table(self, predictions: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
        from .gap import GapEstimator

        est = GapEstimator(n_bootstrap=1)  # only need paired_diffs
        rows: list[DoseResponseResult] = []
        for (task, model, prompt), grp in predictions.groupby(
            ["task", "model", "prompt_strategy"]
        ):
            for metric in metrics:
                if metric not in grp.columns:
                    continue
                diffs_by_k: dict[int, np.ndarray] = {}
                for k, gk in grp.groupby("k"):
                    if int(k) == 0:
                        continue
                    d = est.paired_diffs(gk, metric)
                    if len(d):
                        diffs_by_k[int(k)] = d
                if len(diffs_by_k) >= 2:
                    rows.append(
                        self.analyse_one(
                            diffs_by_k, task=task, metric=metric, model=model, prompt=prompt
                        )
                    )
        return pd.DataFrame(r.to_row() for r in rows)
