"""Print the `vllm serve` command to host a model + its LoRA checkpoints for evaluation.

    python scripts/serve_vllm.py --model starcoder2-15b

Then:  exposure-gap evaluate --backend vllm
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import click

from exposure_gap.config import Settings


@click.command()
@click.option("--root", default=".")
@click.option("--model", "model_id", required=True)
@click.option("--port", default=8000)
def main(root: str, model_id: str, port: int) -> None:
    s = Settings.load(root)
    try:
        spec = s.finetune.model_by_id(model_id)
        base = spec.hf_model_id
        quant = spec.quantization
    except KeyError:
        base, quant = model_id, s.finetune.quantization.enabled and "bitsandbytes" or None

    ck = s.checkpoints_dir
    lora_modules = " ".join(
        f"{model_id}-k{k}={ck / f'{model_id}__k{k}'}"
        for k in (0, *s.finetune.k_levels)
        if k > 0 and (ck / f"{model_id}__k{k}").exists()
    )
    cmd = [
        "vllm serve", base,
        f"--port {port}",
        "--enable-lora",
        f"--max-lora-rank {s.finetune.lora.r}",
    ]
    if lora_modules:
        cmd.append(f"--lora-modules {lora_modules}")
    if quant:
        cmd.append(f"--quantization {quant} --load-format {quant}")
    click.echo(" \\\n  ".join(cmd))
    click.echo("\n# k=0 (base) is served as the model id itself; k>0 via the --lora-modules names.")


if __name__ == "__main__":
    main()
