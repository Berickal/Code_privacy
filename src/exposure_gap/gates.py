"""Decision gates (report Section 17). Each returns a :class:`GateResult`; the CLI
exits non-zero when ``passed`` is False."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .config import CorpusConfig


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: dict = field(default_factory=dict)
    message: str = ""

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.name}: {self.message} {self.detail}"


class Gate1CorpusFeasibility:
    """>= 200 matched pairs/language, >= 3 domains, verifiable attribution ground truth."""

    def __init__(self, config: CorpusConfig):
        self.config = config

    def check(self, corpus_metadata: pd.DataFrame) -> GateResult:
        exposed = corpus_metadata[corpus_metadata["split"] == "E"]
        pairs_per_lang = exposed.groupby("language")["matched_pair_id"].nunique().to_dict()
        n_domains = int(corpus_metadata["domain"].nunique())
        attrib_ok = bool(
            corpus_metadata["github_repo"].notna().all()
            and corpus_metadata["spdx_license"].notna().mean() > 0.8
        )
        crit = self.config.gate1
        passed = (
            all(
                pairs_per_lang.get(lang, 0) >= crit.min_matched_pairs_per_language
                for lang in self.config.languages
            )
            and n_domains >= crit.min_domains
            and attrib_ok
        )
        return GateResult(
            "Gate 1 (corpus feasibility)",
            passed,
            {"pairs_per_language": pairs_per_lang, "n_domains": n_domains, "attribution_ok": attrib_ok},
            "narrow to Python-only + widen window if failing",
        )


class Gate2FinetuneSanity:
    """k=25 gives >= 5% pass@1 lift on exposed reference set; no holdout degradation."""

    def __init__(self, min_lift: float = 0.05):
        self.min_lift = min_lift

    def check(self, exposed_pass1_base: float, exposed_pass1_k25: float, holdout_delta: float) -> GateResult:
        lift = exposed_pass1_k25 - exposed_pass1_base
        passed = lift >= self.min_lift and holdout_delta >= -0.02
        return GateResult(
            "Gate 2 (fine-tuning sanity)",
            passed,
            {"exposed_lift": lift, "holdout_delta": holdout_delta},
            "adjust lr / epochs before the main run if failing",
        )


class Gate3PilotSignal:
    """Pilot Delta_pi > 0 for >= 1 metric at the pilot (prompt, k), 95% CI excludes zero.

    Reports the strength: 'clear' = also FDR-significant (p_adj < q); 'marginal' = CI
    excludes zero but not FDR-significant (treat as inconclusive — a single weak metric
    out of several is easily noise).
    """

    def __init__(self, prompt: str = "P1a", k: int = 5, q: float = 0.05):
        self.prompt = prompt
        self.k = k
        self.q = q

    def check(self, pilot_gaps: pd.DataFrame) -> GateResult:
        sub = pilot_gaps[(pilot_gaps["prompt"] == self.prompt) & (pilot_gaps["k"] == self.k)]
        positive = sub[(sub["delta"] > 0) & (sub["ci_low"] > 0)]
        clear = positive[positive.get("p_adj", 1.0) < self.q]
        passed = not positive.empty
        strength = "clear" if not clear.empty else ("marginal" if passed else "none")
        msg = {
            "clear": "signal present — proceed to the full matrix",
            "marginal": "CI excludes 0 but not FDR-significant — try k=25 / P1b/P4b before scaling",
            "none": "no signal — check the adapter trained, matching quality, clone dedup",
        }[strength]
        return GateResult(
            "Gate 3 (pilot gap signal)",
            passed,
            {
                "strength": strength,
                "ci_positive": positive["metric"].tolist(),
                "fdr_significant": clear["metric"].tolist(),
                "best_delta": float(sub["delta"].max()) if not sub.empty else None,
            },
            msg,
        )
