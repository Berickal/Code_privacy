"""High-entropy canary recovery analysis (report Section 8.3, H5).

Canaries are injected into EXPOSED files only, so the exposed-unexposed gap is undefined
here. The right comparisons are:

* recovery at k vs. recovery in the base model (k=0) on the same exposed files
  ("Recovery vs. base model" — controls for lucky generation), and
* the dose-response of recovery over k.

``canary_exact`` recovery > 0 at k>0 with ~0 at k=0 is the cleanest possible evidence of
exposure-specific memorisation: convergence cannot produce a 48-char random string.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass(frozen=True)
class CanaryRecovery:
    model: str
    prompt: str
    metric: str          # canary_exact | canary_near
    k0_rate: float
    k1_rate: float
    k5_rate: float
    k25_rate: float
    lift_at_max_k: float   # recovery(max k) - recovery(k0)
    monotone: bool

    def to_row(self) -> dict:
        return asdict(self)


class CanaryRecoveryAnalyzer:
    METRICS = ("canary_exact", "canary_near")

    def table(self, predictions: pd.DataFrame) -> pd.DataFrame:
        c = predictions[predictions["task"] == "canary"]
        if c.empty:
            return pd.DataFrame()
        rows: list[CanaryRecovery] = []
        for (model, prompt), grp in c.groupby(["model", "prompt_strategy"]):
            for metric in self.METRICS:
                if metric not in grp.columns:
                    continue
                by_k = grp.groupby("k")[metric].mean().to_dict()
                ks = sorted(by_k)
                series = [by_k[k] for k in ks]
                rows.append(
                    CanaryRecovery(
                        model=model, prompt=prompt, metric=metric,
                        k0_rate=round(by_k.get(0, float("nan")), 4),
                        k1_rate=round(by_k.get(1, float("nan")), 4),
                        k5_rate=round(by_k.get(5, float("nan")), 4),
                        k25_rate=round(by_k.get(25, float("nan")), 4),
                        lift_at_max_k=round(series[-1] - by_k.get(0, 0.0), 4),
                        monotone=all(x <= y + 1e-9 for x, y in zip(series, series[1:])),
                    )
                )
        return pd.DataFrame(r.to_row() for r in rows)
