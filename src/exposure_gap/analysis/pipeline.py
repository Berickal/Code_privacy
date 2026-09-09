"""End-to-end analysis: raw predictions -> all result tables + figures (report Phase G)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce
from pathlib import Path

import pandas as pd

from ..config import AnalysisConfig
from ..utils import ensure_dir, get_logger, write_table
from .convergence import ConvergenceAnalyzer
from .dose_response import DoseResponseAnalyzer
from .fdr import FDRCorrector
from .figures import FigureBuilder
from .gap import GapEstimator
from .interaction import InteractionAnalyzer

log = get_logger()

REPRODUCTION_METRICS = ["lexical_f1", "ast_edit_distance", "dataflow_sim", "test_pass"]
ATTRIBUTION_METRICS = ["attr_exact_project", "attr_top5_project", "attr_exact_license"]
CANARY_METRICS = ["canary_exact", "canary_near"]
ALL_METRICS = REPRODUCTION_METRICS + ATTRIBUTION_METRICS + CANARY_METRICS


@dataclass
class AnalysisArtifacts:
    gaps: pd.DataFrame
    interaction: pd.DataFrame
    convergence: pd.DataFrame
    dose_response: pd.DataFrame
    figures: list[Path]


class AnalysisPipeline:
    def __init__(self, config: AnalysisConfig | None = None):
        self.config = config or AnalysisConfig()
        self.gap_estimator = GapEstimator(self.config.n_bootstrap, self.config.seed)
        self.fdr = FDRCorrector(self.config.fdr_q)
        self.interaction = InteractionAnalyzer()
        self.convergence = ConvergenceAnalyzer()
        self.dose = DoseResponseAnalyzer()

    def run(self, predictions: pd.DataFrame, out_dir: str | Path) -> AnalysisArtifacts:
        out = ensure_dir(Path(out_dir))
        metrics = [m for m in ALL_METRICS if m in predictions.columns]

        gaps = self.gap_estimator.table(predictions, metrics)
        gaps = self.fdr.annotate(gaps, within="task")
        write_table(gaps, out / "gaps.csv")

        interaction = self.interaction.table(gaps)
        write_table(interaction, out / "interaction.csv")

        base = predictions[predictions["k"] == 0]
        conv_frames = [
            c for metric in metrics if not (c := self.convergence.curve(base, metric)).empty
        ]
        if conv_frames:
            convergence = reduce(
                lambda a, b: a.merge(b, on=["task", "prompt_strategy"], how="outer"),
                conv_frames,
            )
            write_table(convergence, out / "convergence.csv")
        else:
            convergence = pd.DataFrame()

        dose = self.dose.table(predictions, metrics)
        if not dose.empty:
            write_table(dose, out / "dose_response.csv")

        figs: list[Path] = []
        fb = FigureBuilder(out / "figures")
        for model in gaps["model"].unique():
            for metric in metrics:
                p = fb.gap_heatmap(gaps, model, metric)
                if p:
                    figs.append(p)
        for task in dose["task"].unique() if not dose.empty else []:
            for metric in metrics:
                p = fb.dose_response_curves(dose, task, metric)
                if p:
                    figs.append(p)

        log.info("analysis complete: {} gap rows, {} figures", len(gaps), len(figs))
        return AnalysisArtifacts(gaps, interaction, convergence, dose, figs)
