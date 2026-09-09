"""RQ2 convergence baseline (report Section 12.2).

How much each prompt strategy raises apparent similarity on UNEXPOSED targets for the
base (non-fine-tuned, k=0) model.
"""

from __future__ import annotations

import pandas as pd

from .. import SPLIT_UNEXPOSED


class ConvergenceAnalyzer:
    def curve(self, base_predictions: pd.DataFrame, metric: str) -> pd.DataFrame:
        u = base_predictions[
            (base_predictions["split"] == SPLIT_UNEXPOSED) & (base_predictions["k"] == 0)
        ]
        return (
            u.groupby(["task", "prompt_strategy"])[metric]
            .agg(**{f"{metric}_mean": "mean", f"{metric}_std": "std", f"{metric}_n": "count"})
            .reset_index()
        )

    def share(self, base_predictions: pd.DataFrame, metric: str) -> pd.DataFrame:
        b = base_predictions[base_predictions["k"] == 0]
        pivot = (
            b.groupby(["task", "prompt_strategy", "split"])[metric]
            .mean()
            .unstack("split")
            .reset_index()
        )
        if "E" in pivot and "U" in pivot:
            pivot["convergence_share"] = pivot["U"] / pivot["E"].where(pivot["E"] != 0)
        return pivot
