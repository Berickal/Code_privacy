"""Figure production (report Section 13 Phase G).

matplotlib is imported lazily so the analysis stack works without it in CI.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..utils import ensure_dir, get_logger

log = get_logger()


class FigureBuilder:
    def __init__(self, out_dir: str | Path):
        self.out_dir = ensure_dir(Path(out_dir))

    def _mpl(self):
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        return plt

    def gap_heatmap(self, gap_df: pd.DataFrame, model: str, metric: str) -> Path | None:
        sub = gap_df[(gap_df["model"] == model) & (gap_df["metric"] == metric)]
        sub = sub.dropna(subset=["delta"])
        if sub.empty:
            return None
        plt = self._mpl()
        pivot = sub.pivot_table(index="task", columns="prompt", values="delta")
        if pivot.size == 0 or not pivot.notna().any().any():
            return None
        vmax = abs(pivot.values[~pd.isna(pivot.values)]).max() or 1.0
        fig, ax = plt.subplots(figsize=(10, 3))
        im = ax.imshow(pivot.values, aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax)
        ax.set_xticks(range(len(pivot.columns)), pivot.columns, rotation=45, ha="right")
        ax.set_yticks(range(len(pivot.index)), pivot.index)
        ax.set_title(f"$\\Delta_\\pi$  ({model}, {metric})")
        fig.colorbar(im, ax=ax)
        fig.tight_layout()
        path = self.out_dir / f"gap_heatmap_{model}_{metric}.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        return path

    def dose_response_curves(self, dr_df: pd.DataFrame, task: str, metric: str) -> Path | None:
        sub = dr_df[(dr_df["task"] == task) & (dr_df["metric"] == metric)]
        if sub.empty:
            return None
        plt = self._mpl()
        fig, ax = plt.subplots(figsize=(6, 4))
        for _, row in sub.iterrows():
            ax.plot(
                [1, 5, 25],
                [row["mean_delta_k1"], row["mean_delta_k5"], row["mean_delta_k25"]],
                marker="o",
                label=f"{row['model']}/{row['prompt']}",
            )
        ax.set_xscale("log")
        ax.set_xlabel("fine-tuning repetitions k")
        ax.set_ylabel("$\\Delta_\\pi$")
        ax.set_title(f"Dose-response ({task}, {metric})")
        ax.legend(fontsize=6)
        fig.tight_layout()
        path = self.out_dir / f"dose_response_{task}_{metric}.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        return path

    def convergence_figure(self, conv_df: pd.DataFrame, metric: str) -> Path | None:
        col = f"{metric}_mean"
        if col not in conv_df.columns:
            return None
        plt = self._mpl()
        fig, ax = plt.subplots(figsize=(8, 4))
        for task, g in conv_df.groupby("task"):
            ax.plot(g["prompt_strategy"], g[col], marker="s", label=task)
        ax.set_ylabel(f"mean {metric} on $T_U$ (base model)")
        ax.set_title("Convergence baseline (RQ2)")
        ax.legend()
        fig.autofmt_xdate(rotation=45)
        fig.tight_layout()
        path = self.out_dir / f"convergence_{metric}.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        return path
