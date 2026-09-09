"""RQ3: prompt x exposure interaction (report Section 12.3).

Interaction_pi = Delta_pi - Delta_pi0  (pi0 = zero-shot baseline P1a).
Positive -> the strategy adds exposure-specific signal beyond baseline.
"""

from __future__ import annotations

import pandas as pd

from .. import BASELINE_STRATEGY


class InteractionAnalyzer:
    def __init__(self, baseline: str = BASELINE_STRATEGY):
        self.baseline = baseline

    def table(self, gap_df: pd.DataFrame) -> pd.DataFrame:
        keys = ["task", "metric", "model", "k"]
        base = (
            gap_df[gap_df["prompt"] == self.baseline]
            .set_index(keys)["delta"]
            .rename("delta_baseline")
        )
        out = gap_df.join(base, on=keys)
        out["interaction"] = out["delta"] - out["delta_baseline"]
        return out.sort_values(
            ["task", "metric", "model", "k", "interaction"],
            ascending=[True, True, True, True, False],
        )
