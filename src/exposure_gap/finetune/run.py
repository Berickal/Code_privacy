"""LoRA fine-tuning at k in {1,5,25} (report Phase C).

Hyperparameters are fixed in ``configs/finetune.yaml`` BEFORE this phase and never
tuned on Phase-G outcomes. Requires ``pip install -e '.[finetune]'`` and GPUs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import FinetuneConfig, ModelSpec
from ..schema import Canary
from ..utils import ensure_dir, get_logger
from .data import FinetuneDatasetBuilder

log = get_logger()


@dataclass
class CheckpointInfo:
    model_id: str
    k: int
    path: Path
    n_examples: int


class LoraFinetuner:
    def __init__(self, config: FinetuneConfig, checkpoints_dir: str | Path):
        self.config = config
        self.checkpoints_dir = ensure_dir(Path(checkpoints_dir))
        self.dataset_builder = FinetuneDatasetBuilder(seed=config.seed)

    def checkpoint_path(self, model: ModelSpec, k: int) -> Path:
        return self.checkpoints_dir / f"{model.id}__k{k}"

    def run_one(
        self,
        model: ModelSpec,
        exposed_sources: dict[str, str],
        k: int,
        canaries: dict[str, Canary] | None = None,
    ) -> CheckpointInfo:
        out = ensure_dir(self.checkpoint_path(model, k))
        examples = self.dataset_builder.build(exposed_sources, k, canaries)
        jsonl = out / "train.jsonl"
        self.dataset_builder.write(examples, jsonl)
        log.info("{} k={}: {} training examples", model.id, k, len(examples))

        self._train(model, jsonl, out)
        return CheckpointInfo(model.id, k, out, len(examples))

    def run_all(
        self,
        model: ModelSpec,
        exposed_sources: dict[str, str],
        canaries: dict[str, Canary] | None = None,
    ) -> list[CheckpointInfo]:
        return [
            self.run_one(model, exposed_sources, k, canaries)
            for k in self.config.k_levels
        ]

    # ------------------------------------------------------------------
    @staticmethod
    def _device_settings() -> dict:
        import torch

        if torch.cuda.is_available():
            return {"dtype": torch.bfloat16, "bf16": True, "fp16": False, "device": "cuda"}
        if torch.backends.mps.is_available():
            # MPS: fp16/bf16 training is flaky; use fp32 (fine for smoke tests / small models)
            return {"dtype": torch.float32, "bf16": False, "fp16": False, "device": "mps"}
        return {"dtype": torch.float32, "bf16": False, "fp16": False, "device": "cpu"}

    def _bnb_config(self, device: str):
        """BitsAndBytesConfig for QLoRA, or None when unavailable (non-CUDA, no bnb, or
        quantization disabled) — in which case training proceeds full precision."""
        q = self.config.quantization
        if not q.enabled:
            return None
        if device != "cuda":
            log.warning("quantization requested but device is {} — bitsandbytes needs "
                        "CUDA; training full precision", device)
            return None
        try:
            import torch
            from transformers import BitsAndBytesConfig
        except ImportError:
            log.warning("bitsandbytes/transformers quant support missing — full precision")
            return None
        compute = getattr(torch, q.compute_dtype, torch.bfloat16)
        if q.bits == 8:
            return BitsAndBytesConfig(load_in_8bit=True)
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=q.quant_type,
            bnb_4bit_use_double_quant=q.double_quant,
            bnb_4bit_compute_dtype=compute,
        )

    def _train(self, model: ModelSpec, jsonl: Path, out: Path) -> None:
        import inspect

        from datasets import load_dataset
        from peft import LoraConfig as PeftLoraConfig
        from peft import prepare_model_for_kbit_training
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import SFTConfig, SFTTrainer

        cfg = self.config
        dev = self._device_settings()
        bnb = self._bnb_config(dev["device"])
        quantized = bnb is not None

        tokenizer = AutoTokenizer.from_pretrained(model.hf_model_id)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        load_kw = {"dtype": dev["dtype"]}
        if quantized:
            load_kw = {"quantization_config": bnb, "device_map": "auto",
                       "dtype": getattr(__import__("torch"), cfg.quantization.compute_dtype)}
        base = AutoModelForCausalLM.from_pretrained(model.hf_model_id, **load_kw)
        if quantized:
            base = prepare_model_for_kbit_training(
                base, use_gradient_checkpointing=cfg.gradient_checkpointing
            )
            log.info("QLoRA: {}-bit ({}) base weights", cfg.quantization.bits, cfg.quantization.quant_type)
        dataset = load_dataset("json", data_files=str(jsonl), split="train")

        # TrainingArguments / SFTConfig field names churn across transformers & trl
        # versions (e.g. max_seq_length -> max_length; warmup_ratio dropped in some
        # transformers 5.x minors). Build the desired kwargs, then keep only accepted ones.
        import dataclasses

        sft_fields = {f.name for f in dataclasses.fields(SFTConfig)}
        n_steps = max(len(dataset) // (cfg.batch_size * cfg.grad_accum), 1) * cfg.epochs
        desired = {
            "output_dir": str(out),
            "num_train_epochs": cfg.epochs,
            "per_device_train_batch_size": cfg.batch_size,
            "gradient_accumulation_steps": cfg.grad_accum,
            "learning_rate": cfg.learning_rate,
            "lr_scheduler_type": cfg.scheduler,
            "warmup_ratio": cfg.warmup_ratio,
            "warmup_steps": int(n_steps * cfg.warmup_ratio),
            "logging_steps": 5,
            "save_strategy": "epoch",
            "seed": cfg.seed,
            "dataset_text_field": "text",
            "packing": False,
            "bf16": dev["bf16"],
            "fp16": dev["fp16"],
            "report_to": "none",
            "gradient_checkpointing": cfg.gradient_checkpointing and quantized,
            "max_length": cfg.max_seq_length,
            "max_seq_length": cfg.max_seq_length,
        }
        kwargs = {k: v for k, v in desired.items() if k in sft_fields}
        dropped = sorted(set(desired) - set(kwargs) - {"max_seq_length", "max_length", "warmup_steps", "warmup_ratio"})
        if dropped:
            log.warning("SFTConfig ignores unknown args in this version: {}", dropped)
        sft = SFTConfig(**kwargs)
        peft = PeftLoraConfig(
            r=cfg.lora.r,
            lora_alpha=cfg.lora.alpha,
            lora_dropout=cfg.lora.dropout,
            target_modules=cfg.lora.target_modules,
            task_type="CAUSAL_LM",
        )
        trainer_kw = {"model": base, "args": sft, "train_dataset": dataset, "peft_config": peft}
        params = inspect.signature(SFTTrainer.__init__).parameters
        trainer_kw["processing_class" if "processing_class" in params else "tokenizer"] = tokenizer
        trainer = SFTTrainer(**trainer_kw)
        trainer.train()
        trainer.save_model(str(out))
