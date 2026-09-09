"""Serve a model + its LoRA checkpoints with vLLM for Phase G evaluation.

    python scripts/serve_vllm.py --model starcoder2-15b            # print the command
    python scripts/serve_vllm.py --model starcoder2-15b --run      # actually launch it

``--run`` execs vLLM in the foreground; keep it in its own terminal (or tmux / nohup)
and run ``exposure-gap evaluate --backend vllm`` from another once it prints
"Application startup complete".
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import click

from exposure_gap.config import Settings


def build_args(root: str, model_id: str, port: int, max_model_len: int, gpu_util: float) -> list[str]:
    s = Settings.load(root)
    try:
        spec = s.finetune.model_by_id(model_id)
        base, quant = spec.hf_model_id, spec.quantization
    except KeyError:
        base = model_id
        quant = "bitsandbytes" if s.finetune.quantization.enabled else None

    ck = s.checkpoints_dir
    present = [k for k in s.finetune.k_levels if (ck / f"{model_id}__k{k}").exists()]
    missing = [k for k in s.finetune.k_levels if k not in present]
    if missing:
        click.echo(f"# note: no checkpoint for k={missing} — not serving those", err=True)

    args = [
        "vllm", "serve", base,
        "--port", str(port),
        "--max-model-len", str(max_model_len),
        "--gpu-memory-utilization", str(gpu_util),
    ]
    if present:
        args += ["--enable-lora", "--max-lora-rank", str(s.finetune.lora.r), "--lora-modules"]
        args += [f"{model_id}-k{k}={ck / f'{model_id}__k{k}'}" for k in present]
    if quant:
        args += ["--quantization", quant, "--load-format", quant]
    return args


@click.command()
@click.option("--root", default=".")
@click.option("--model", "model_id", required=True)
@click.option("--port", default=8000)
@click.option("--max-model-len", default=4096, help="lower to fit KV cache on one card")
@click.option("--gpu-memory-utilization", "gpu_util", default=0.92)
@click.option("--run", is_flag=True, help="launch vLLM instead of just printing the command")
def main(root: str, model_id: str, port: int, max_model_len: int, gpu_util: float, run: bool) -> None:
    args = build_args(root, model_id, port, max_model_len, gpu_util)
    click.echo(" \\\n  ".join(args))
    if not run:
        click.echo("\n# k=0 (base) is served as the model id itself; k>0 via the k<k> names.")
        click.echo("# add --run to launch it here.")
        return
    env = {**os.environ, "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}
    raise SystemExit(subprocess.call(args, env=env))


if __name__ == "__main__":
    main()
