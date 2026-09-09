"""RQ6 external validity (report Section 12.5).

Does the naturally pre-cutoff profile resemble the fine-tuned exposed cluster or the
unexposed cluster? Mahalanobis distance of the per-prompt mean metric vector to each.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PrecutoffComparison:
    model: str
    d_to_exposed: float
    d_to_unexposed: float
    closer_to: str

    def to_row(self) -> dict:
        return asdict(self)


class PrecutoffAnalyzer:
    def __init__(self, metrics: list[str]):
        self.metrics = metrics

    def _profile(self, preds: pd.DataFrame) -> np.ndarray:
        g = preds.groupby("prompt_strategy")[self.metrics].mean()
        return g.to_numpy()

    @staticmethod
    def _mahalanobis(x: np.ndarray, cloud: np.ndarray) -> float:
        if cloud.shape[0] < 2:
            return float(np.linalg.norm(x - cloud.mean(axis=0)))
        mu = cloud.mean(axis=0)
        cov = np.cov(cloud, rowvar=False) + np.eye(cloud.shape[1]) * 1e-6
        inv = np.linalg.pinv(cov)
        d = x - mu
        return float(np.sqrt(d @ inv @ d))

    def compare(
        self,
        precutoff_preds: pd.DataFrame,
        exposed_preds: pd.DataFrame,
        unexposed_preds: pd.DataFrame,
        model: str,
    ) -> PrecutoffComparison:
        x = self._profile(precutoff_preds).mean(axis=0)
        de = self._mahalanobis(x, self._profile(exposed_preds))
        du = self._mahalanobis(x, self._profile(unexposed_preds))
        return PrecutoffComparison(model, de, du, "exposed" if de < du else "unexposed")
