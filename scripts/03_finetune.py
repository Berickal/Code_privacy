"""Phase C: LoRA fine-tuning at k in {1,5,25} (report Section 11.2).

    # configured model, all k levels:
    python scripts/03_finetune.py --model starcoder2-15b

    # any HF model id + a fast smoke (one k level, few files):
    python scripts/03_finetune.py --model google/gemma-3-270m --k 1 --limit-files 12

Hyperparameters come from configs/finetune.yaml and are never tuned on Phase-G outcomes.
Verifies FREEZE.lock first. Needs `pip install peft trl` (GPUs for the real models).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import click
from dotenv import load_dotenv

from exposure_gap import SPLIT_EXPOSED
from exposure_gap.config import ModelSpec, Settings
from exposure_gap.corpus import CorpusStore, FreezeManager
from exposure_gap.finetune import LoraFinetuner
from exposure_gap.phases import Phases
from exposure_gap.utils import get_logger, setup_logging

log = get_logger()


def _resolve_model(settings: Settings, model_id: str) -> ModelSpec:
    try:
        return settings.finetune.model_by_id(model_id)
    except KeyError:
        log.warning("'{}' not in configs/finetune.yaml — treating it as a raw HF id", model_id)
        return ModelSpec(id=model_id.replace("/", "__"), hf_model_id=model_id, backend="vllm")


@click.command()
@click.option("--root", default=".")
@click.option("--model", "model_id", required=True, help="config id or raw HF model id")
@click.option("--k", "k_levels", multiple=True, type=int, help="subset of k levels (default: all)")
@click.option("--limit-files", default=0, help="fine-tune on only the first N exposed files (smoke)")
@click.option("--epochs", default=None, type=int, help="override configs/finetune.yaml epochs")
@click.option("--quant-bits", default=None, type=int, help="override quantization bits (0/4/8)")
@click.option("--allow-unfrozen", is_flag=True, help="skip the FREEZE.lock check (testing only)")
@click.option("--dry-run", is_flag=True, help="build the training data, don't train")
def main(
    root: str,
    model_id: str,
    k_levels: tuple[int, ...],
    limit_files: int,
    epochs: int | None,
    quant_bits: int | None,
    allow_unfrozen: bool,
    dry_run: bool,
) -> None:
    load_dotenv(Path(root) / ".env")
    load_dotenv(Path(root).parent / ".env")
    setup_logging()

    settings = Settings.load(root)
    if epochs is not None:
        settings.finetune.epochs = epochs
    if k_levels:
        settings.finetune.k_levels = list(k_levels)
    if quant_bits is not None:
        settings.finetune.quantization.bits = quant_bits
        allow_unfrozen = True  # a config override breaks the freeze by design

    if not allow_unfrozen:
        FreezeManager(root).assert_clean()
    q = settings.finetune.quantization
    log.info("quantization: {}", f"{q.bits}-bit {q.quant_type}" if q.enabled else "disabled")

    store = CorpusStore(settings.corpus_dir)
    meta = store.read_metadata()
    exposed_ids = meta[meta["split"] == SPLIT_EXPOSED]["file_id"].tolist()
    if limit_files:
        exposed_ids = exposed_ids[:limit_files]
    exposed_sources = {fid: store.read_source(fid) for fid in exposed_ids}
    canaries = {
        fid: c for fid, c in Phases(settings).load_canaries().items() if fid in exposed_sources
    }
    log.info(
        "{} exposed files, {} with canaries, k levels {}",
        len(exposed_sources), len(canaries), settings.finetune.k_levels,
    )

    model = _resolve_model(settings, model_id)
    finetuner = LoraFinetuner(settings.finetune, settings.checkpoints_dir)

    if dry_run:
        for k in settings.finetune.k_levels:
            ex = finetuner.dataset_builder.build(exposed_sources, k, canaries)
            click.echo(f"k={k}: {len(ex)} training examples ({len(exposed_sources)} files x {k})")
        return

    infos = finetuner.run_all(model, exposed_sources, canaries)
    for info in infos:
        click.echo(f"{info.model_id} k={info.k}: {info.n_examples} examples -> {info.path}")


if __name__ == "__main__":
    main()
