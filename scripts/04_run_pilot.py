"""Phase F: pilot (primary model, k=5, P1a, reproduction only) + Gate 3.

    # in-process, quantized, no server:
    python scripts/04_run_pilot.py --model starcoder2-15b --backend local

    # against a running vLLM server:
    python scripts/04_run_pilot.py --model starcoder2-15b --backend vllm
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import click
from dotenv import load_dotenv

from exposure_gap import TASK_REPRODUCTION
from exposure_gap.analysis import AnalysisPipeline
from exposure_gap.config import Settings
from exposure_gap.gates import Gate3PilotSignal
from exposure_gap.phases import Phases
from exposure_gap.utils import setup_logging


@click.command()
@click.option("--root", default=".")
@click.option("--model", "model_id", default="starcoder2-15b")
@click.option("--backend", default="local", help="local | vllm | openrouter | echo")
@click.option("--quantization", default="bitsandbytes")
@click.option("--k", "pilot_k", default=5, help="fine-tuned checkpoint to test")
@click.option("--batch-size", default=8)
@click.option("--offline", is_flag=True, help="alias for --backend echo")
def main(root: str, model_id: str, backend: str, quantization: str, pilot_k: int,
         batch_size: int, offline: bool) -> None:
    load_dotenv(Path(root) / ".env")
    load_dotenv(Path(root).parent / ".env")
    setup_logging()
    settings = Settings.load(root)
    phases = Phases(settings)

    preds = phases.evaluate(
        models=[(model_id, "echo" if offline else backend)],
        k_levels=(0, pilot_k),
        tasks=(TASK_REPRODUCTION,),
        strategies=("P1a",),
        offline=offline,
        quantization=None if backend != "local" else quantization,
        batch_size=batch_size,
    )
    artifacts = AnalysisPipeline(settings.analysis).run(preds, settings.results_dir / "pilot")
    print(artifacts.gaps[["metric", "k", "delta", "ci_low", "ci_high", "p_adj", "n_pairs"]].to_string(index=False))
    result = Gate3PilotSignal(k=pilot_k).check(artifacts.gaps)
    click.echo(result)
    raise SystemExit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
