"""Gate 2 / H2: does fine-tuning change general code-generation capability?

    python scripts/07_holdout_eval.py --model starcoder2-15b --backend local --k 5

Runs P1a reproduction on the unexposed holdout T_H at k=0 and k=<k>, and on a held-out
slice of the exposed set, and reports the shift in mean similarity.

  - large lift on T_H  -> fine-tuning improves general capability (H2 confound; Delta_pi
    is measured vs matched T_U precisely so this partly cancels, but report the residual)
  - drop on T_H        -> catastrophic forgetting -> Gate 2 FAIL, lower lr / fewer epochs
  - lift on exposed slice but not T_H -> healthy exposure signal
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import click
import pandas as pd
from dotenv import load_dotenv

from exposure_gap import TASK_REPRODUCTION
from exposure_gap.config import Settings
from exposure_gap.phases import Phases
from exposure_gap.utils import setup_logging

METRICS = ["lexical_f1", "ast_edit_distance", "dataflow_sim"]


@click.command()
@click.option("--root", default=".")
@click.option("--model", "model_id", default="starcoder2-15b")
@click.option("--backend", default="local")
@click.option("--quantization", default="bitsandbytes")
@click.option("--k", "k", default=5)
@click.option("--batch-size", default=8)
@click.option("--forgetting-threshold", default=-0.02)
def main(root: str, model_id: str, backend: str, quantization: str, k: int,
         batch_size: int, forgetting_threshold: float) -> None:
    load_dotenv(Path(root) / ".env")
    load_dotenv(Path(root).parent / ".env")
    setup_logging()
    phases = Phases(Settings.load(root))

    frames = []
    for split in ("H", "E"):
        df = phases.evaluate(
            models=[(model_id, backend)],
            k_levels=(0, k),
            tasks=(TASK_REPRODUCTION,),
            strategies=("P1a",),
            splits=(split,),
            quantization=None if backend != "local" else quantization,
            batch_size=batch_size,
        )
        df["eval_split"] = split
        frames.append(df)
    preds = pd.concat(frames, ignore_index=True)

    rows = []
    for split in ("H", "E"):
        s = preds[preds["eval_split"] == split]
        for m in METRICS:
            if m not in s:
                continue
            before = s[s["k"] == 0][m].mean()
            after = s[s["k"] == k][m].mean()
            rows.append({"split": split, "metric": m, "k0": round(before, 4),
                         f"k{k}": round(after, 4), "shift": round(after - before, 4)})
    report = pd.DataFrame(rows)
    print(report.to_string(index=False))

    h_shift = report[report["split"] == "H"]["shift"].min()
    forgetting = h_shift < forgetting_threshold
    print(f"\nHoldout min shift: {h_shift:+.4f}  ->  "
          f"{'CATASTROPHIC FORGETTING (Gate 2 FAIL)' if forgetting else 'no degradation (Gate 2 OK)'}")
    report.to_csv(phases.settings.results_dir / "holdout_eval.csv", index=False)
    raise SystemExit(1 if forgetting else 0)


if __name__ == "__main__":
    main()
