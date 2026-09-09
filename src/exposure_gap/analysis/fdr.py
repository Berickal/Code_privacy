"""Benjamini-Hochberg FDR correction, applied within each task (report Section 15)."""

from __future__ import annotations

import numpy as np
import pandas as pd


class FDRCorrector:
    def __init__(self, q: float = 0.05):
        self.q = q

    @staticmethod
    def adjust(pvals: np.ndarray) -> np.ndarray:
        p = np.asarray(pvals, dtype=float)
        mask = np.isfinite(p)
        out = np.full_like(p, np.nan)
        if mask.sum() == 0:
            return out
        pm = p[mask]
        n = pm.size
        order = np.argsort(pm)
        ranked = pm[order] * n / (np.arange(n) + 1)
        ranked = np.minimum.accumulate(ranked[::-1])[::-1]
        adj = np.empty(n)
        adj[order] = np.clip(ranked, 0, 1)
        out[mask] = adj
        return out

    def annotate(self, gap_df: pd.DataFrame, within: str = "task") -> pd.DataFrame:
        df = gap_df.copy()
        df["p_adj"] = np.nan
        for _, idx in df.groupby(within).groups.items():
            df.loc[idx, "p_adj"] = self.adjust(df.loc[idx, "p_value"].to_numpy())
        df["significant"] = df["p_adj"] < self.q
        return df
