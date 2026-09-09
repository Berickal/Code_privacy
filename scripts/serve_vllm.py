"""Serve a model + its LoRA checkpoints with vLLM for Phase G evaluation.

    python scripts/serve_vllm.py --model starcoder2-15b            # print the command
    python scripts/serve_vllm.py --model starcoder2-15b --run      # actually launch it

``--run`` execs vLLM in the foreground; keep it in its own terminal (or tmux / nohup)
and run ``exposure-gap evaluate --backend vllm`` from another once it prints
"Application startup complete".
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import click

from exposure_gap.config import Settings


# vLLM (>=0.29) dropped the "bitsandbytes" runtime quantization method. Serve the base
# in fp8 instead (Ada/Hopper have hardware fp8; ~1 byte/param -> a 15B fits one 32 GB
# card with room for the KV cache). The LoRA adapters were trained on an nf4 view of the
# same frozen weights; applied to an fp8 base this is a small extra noise source that
# cancels in Delta_pi (identical across every k level and both populations).
_VLLM_QUANT = {"bitsandbytes": "fp8", "nf4": "fp8", "4bit": "fp8", "int8": "fp8"}


def build_args(
    root: str, model_id: str, port: int, max_model_len: int, gpu_util: float,
    quant_override: str | None = None,
) -> list[str]:
    s = Settings.load(root)
    try:
        spec = s.finetune.model_by_id(model_id)
        base, quant = spec.hf_model_id, spec.quantization
    except KeyError:
        base = model_id
        quant = "bitsandbytes" if s.finetune.quantization.enabled else None

    if quant_override is not None:
        quant = quant_override or None
    elif quant in _VLLM_QUANT:
        click.echo(f"# '{quant}' is not a vLLM runtime method -> serving fp8 instead", err=True)
        quant = _VLLM_QUANT[quant]

    ck = s.checkpoints_dir
    present = [
        k for k in s.finetune.k_levels
        if (ck / f"{model_id}__k{k}" / "adapter_config.json").exists()
    ]
    missing = [k for k in s.finetune.k_levels if k not in present]
    if missing:
        click.echo(f"# note: no trained adapter for k={missing} — not serving those", err=True)

    args = [
        "vllm", "serve", base,
        "--port", str(port),
        "--max-model-len", str(max_model_len),
        "--gpu-memory-utilization", str(gpu_util),
        # base addressable as the short id (matches what `evaluate` sends for k=0)
        "--served-model-name", model_id,
    ]
    if present:
        args += ["--enable-lora", "--max-lora-rank", str(s.finetune.lora.r), "--lora-modules"]
        args += [f"{model_id}-k{k}={ck / f'{model_id}__k{k}'}" for k in present]
    if quant:
        args += ["--quantization", quant]
    return args


@click.command()
@click.option("--root", default=".")
@click.option("--model", "model_id", required=True)
@click.option("--port", default=8000)
@click.option("--max-model-len", default=4096, help="lower to fit KV cache on one card")
@click.option("--gpu-memory-utilization", "gpu_util", default=0.92)
@click.option("--quantization", "quant_override", default=None,
              help="vLLM quant method (fp8 | awq_marlin | gptq_marlin | '' for bf16)")
@click.option("--run", is_flag=True, help="launch vLLM instead of just printing the command")
def main(root, model_id, port, max_model_len, gpu_util, quant_override, run) -> None:
    args = build_args(root, model_id, port, max_model_len, gpu_util, quant_override)
    click.echo(shlex.join(args))
    if not run:
        click.echo("\n# k=0 (base) is served as the model id itself; k>0 via the k<k> names.")
        click.echo("# add --run to launch it here.")
        return
    env = {**os.environ, "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}
    raise SystemExit(subprocess.call(args, env=env))


if __name__ == "__main__":
    main()
