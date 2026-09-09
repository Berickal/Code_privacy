"""Primary outcome: exposed-unexposed gap Delta_pi with matched-pair bootstrap CI
(report Sections 4.2, 12.1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class GapResult:
    task: str
    metric: str
    model: str
    k: int
    prompt: str
    delta: float
    ci_low: float
    ci_high: float
    n_pairs: int
    p_value: float

    def to_row(self) -> dict:
        return asdict(self)


class GapEstimator:
    def __init__(self, n_bootstrap: int = 10_000, seed: int = 0):
        self.n_bootstrap = n_bootstrap
        self.seed = seed

    @staticmethod
    def paired_diffs(df: pd.DataFrame, metric: str) -> np.ndarray:
        piv = df.pivot_table(
            index="matched_pair_id", columns="split", values=metric, aggfunc="mean"
        )
        piv = piv.dropna(subset=[c for c in ("E", "U") if c in piv.columns])
        if not {"E", "U"}.issubset(piv.columns):
            return np.array([])
        return (piv["E"] - piv["U"]).to_numpy()

    def estimate(
        self, df: pd.DataFrame, *, task: str, metric: str, model: str, k: int, prompt: str
    ) -> GapResult:
        diffs = self.paired_diffs(df, metric)
        n = len(diffs)
        if n == 0:
            return GapResult(task, metric, model, k, prompt, np.nan, np.nan, np.nan, 0, np.nan)
        delta = float(diffs.mean())
        rng = np.random.default_rng(self.seed)
        idx = rng.integers(0, n, size=(self.n_bootstrap, n))
        boot = diffs[idx].mean(axis=1)
        ci_low, ci_high = (float(x) for x in np.percentile(boot, [2.5, 97.5]))
        centred = boot - delta
        p = float((np.abs(centred) >= abs(delta)).mean())
        return GapResult(task, metric, model, k, prompt, delta, ci_low, ci_high, n, p)

    def table(self, predictions: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
        results: list[GapResult] = []
        for (task, model, k, prompt), grp in predictions.groupby(
            ["task", "model", "k", "prompt_strategy"]
        ):
            for metric in metrics:
                if metric in grp.columns and grp[metric].notna().any():
                    results.append(
                        self.estimate(
                            grp, task=task, metric=metric, model=model, k=int(k), prompt=prompt
                        )
                    )
        return pd.DataFrame(r.to_row() for r in results)
