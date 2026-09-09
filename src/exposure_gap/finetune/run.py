"""Fine-tuning at k in {1,5,25} (report Phase C).

Two methods (``configs/finetune.yaml`` -> ``method``):

* ``lora``  — QLoRA (4-bit frozen base + rank-r adapters). Low VRAM; the adapter is a
  small delta. This is the report's default.
* ``full``  — every weight is trained. A stronger model of "the model saw this data",
  but memory-hungry: a 12B full FT is ~90 GB with AdamW (weights + grads + 2 optimizer
  moments). Paged 8-bit Adam + gradient checkpointing brings a 4-7B onto a 40-80 GB
  card; a 12B+ needs multi-GPU / ZeRO. The finetuner prints an estimate and refuses if
  it clearly won't fit (override with ``--force``).

Hyperparameters are fixed BEFORE this phase and never tuned on Phase-G outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import FinetuneConfig, ModelSpec
from ..schema import Canary
from ..utils import ensure_dir, get_logger
from .data import FinetuneDatasetBuilder

log = get_logger()

_PARAMS_B = {  # rough parameter counts for the VRAM estimate
    "270m": 0.27, "1b": 1.0, "1.1b": 1.1, "2b": 2.6, "3b": 3.9, "4b": 4.3,
    "6.7b": 6.7, "7b": 7.6, "9b": 9.2, "12b": 12.2, "13b": 13.0, "15b": 16.0,
    "27b": 27.0, "34b": 34.0, "70b": 70.0,
}


def _guess_params_b(hf_id: str) -> float:
    low = hf_id.lower()
    for tag, b in sorted(_PARAMS_B.items(), key=lambda kv: -len(kv[0])):
        if tag in low:
            return b
    return 7.0


def full_ft_vram_estimate_gb(params_b: float, optim: str, grad_ckpt: bool) -> float:
    """weights(bf16 2B) + grads(2B) + optimizer state + activations."""
    per = 2 + 2
    per += 2 if "8bit" in optim else 8          # 8-bit Adam ~2 B/param vs fp32 m+v = 8
    act = 3.0 if grad_ckpt else 12.0            # very rough, seq 2048 bs 1
    return params_b * per + act


@dataclass
class CheckpointInfo:
    model_id: str
    k: int
    path: Path
    n_examples: int
    method: str = "lora"


class Finetuner:
    def __init__(self, config: FinetuneConfig, checkpoints_dir: str | Path, force: bool = False):
        self.config = config
        self.checkpoints_dir = ensure_dir(Path(checkpoints_dir))
        self.dataset_builder = FinetuneDatasetBuilder(seed=config.seed)
        self.force = force

    @property
    def method(self) -> str:
        return self.config.method

    def checkpoint_path(self, model: ModelSpec, k: int) -> Path:
        return self.checkpoints_dir / f"{model.id}__k{k}"

    def _preflight(self, model: ModelSpec) -> None:
        if self.method != "full":
            return
        import torch

        params_b = _guess_params_b(model.hf_model_id or model.id)
        need = full_ft_vram_estimate_gb(
            params_b, self.config.full_optim, self.config.gradient_checkpointing
        )
        have = (
            torch.cuda.get_device_properties(0).total_memory / 1e9
            if torch.cuda.is_available() else 0.0
        )
        log.info(
            "full FT ~{:.0f}B params -> est {:.0f} GB VRAM (optim={}, grad_ckpt={}); "
            "device has {:.0f} GB",
            params_b, need, self.config.full_optim, self.config.gradient_checkpointing, have,
        )
        if have and need > have * 1.05 and not self.force:
            raise RuntimeError(
                f"full FT of ~{params_b:.0f}B needs ~{need:.0f} GB but this GPU has "
                f"{have:.0f} GB. Use method=lora, a smaller model, multi-GPU/ZeRO, or "
                f"--force to try anyway."
            )

    def run_one(
        self,
        model: ModelSpec,
        exposed_sources: dict[str, str],
        k: int,
        canaries: dict[str, Canary] | None = None,
    ) -> CheckpointInfo:
        self._preflight(model)
        out = ensure_dir(self.checkpoint_path(model, k))
        examples = self.dataset_builder.build(exposed_sources, k, canaries)
        jsonl = out / "train.jsonl"
        self.dataset_builder.write(examples, jsonl)
        log.info("{} k={} [{}]: {} training examples", model.id, k, self.method, len(examples))

        self._train(model, jsonl, out)
        return CheckpointInfo(model.id, k, out, len(examples), self.method)

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

    def _freeze_except_last_n(self, model, n: int) -> None:
        if n <= 0:
            return
        import re

        layers = sorted(
            {int(m.group(1)) for name, _ in model.named_parameters()
             if (m := re.search(r"\.layers\.(\d+)\.", name))}
        )
        keep = set(layers[-n:])
        trainable = 0
        for name, p in model.named_parameters():
            m = re.search(r"\.layers\.(\d+)\.", name)
            p.requires_grad = (m is None and "lm_head" in name) or (m and int(m.group(1)) in keep)
            trainable += p.numel() if p.requires_grad else 0
        log.info("full-topk: training last {} blocks (~{:.0f}M params)", n, trainable / 1e6)

    def _train(self, model: ModelSpec, jsonl: Path, out: Path) -> None:
        import inspect

        import torch
        from datasets import load_dataset
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import SFTConfig, SFTTrainer

        cfg = self.config
        dev = self._device_settings()
        full = self.method == "full"

        tokenizer = AutoTokenizer.from_pretrained(model.hf_model_id)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        if full:
            base = AutoModelForCausalLM.from_pretrained(
                model.hf_model_id, dtype=dev["dtype"],
                device_map="auto" if dev["device"] == "cuda" else None,
            )
            base.config.use_cache = False
            if cfg.gradient_checkpointing:
                base.gradient_checkpointing_enable()
            self._freeze_except_last_n(base, cfg.full_trainable_last_n)
            peft = None
            log.info("full-weight fine-tuning ({})", dev["dtype"])
        else:
            from peft import LoraConfig as PeftLoraConfig
            from peft import prepare_model_for_kbit_training

            bnb = self._bnb_config(dev["device"])
            load_kw = {"dtype": dev["dtype"]}
            if bnb is not None:
                load_kw = {"quantization_config": bnb, "device_map": "auto",
                           "dtype": getattr(torch, cfg.quantization.compute_dtype)}
            base = AutoModelForCausalLM.from_pretrained(model.hf_model_id, **load_kw)
            if bnb is not None:
                base = prepare_model_for_kbit_training(
                    base, use_gradient_checkpointing=cfg.gradient_checkpointing
                )
                log.info("QLoRA: {}-bit ({})", cfg.quantization.bits, cfg.quantization.quant_type)
            peft = PeftLoraConfig(
                r=cfg.lora.r, lora_alpha=cfg.lora.alpha, lora_dropout=cfg.lora.dropout,
                target_modules=cfg.lora.target_modules, task_type="CAUSAL_LM",
            )

        dataset = load_dataset("json", data_files=str(jsonl), split="train")
        quantized = (not full) and self._bnb_config(dev["device"]) is not None

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
            "learning_rate": cfg.full_learning_rate if full else cfg.learning_rate,
            "lr_scheduler_type": cfg.scheduler,
            "warmup_ratio": cfg.warmup_ratio,
            "warmup_steps": int(n_steps * cfg.warmup_ratio),
            "logging_steps": 5,
            "save_strategy": "no",          # save once at the end (full models are large)
            "seed": cfg.seed,
            "dataset_text_field": "text",
            "packing": False,
            "bf16": dev["bf16"],
            "fp16": dev["fp16"],
            "report_to": "none",
            "gradient_checkpointing": cfg.gradient_checkpointing and (full or quantized),
            "optim": cfg.full_optim if full else "adamw_torch",
            "max_length": cfg.max_seq_length,
            "max_seq_length": cfg.max_seq_length,
        }
        kwargs = {k: v for k, v in desired.items() if k in sft_fields}
        dropped = sorted(
            set(desired) - set(kwargs)
            - {"max_seq_length", "max_length", "warmup_steps", "warmup_ratio"}
        )
        if dropped:
            log.warning("SFTConfig ignores unknown args in this version: {}", dropped)
        sft = SFTConfig(**kwargs)

        trainer_kw = {"model": base, "args": sft, "train_dataset": dataset}
        if peft is not None:
            trainer_kw["peft_config"] = peft
        params = inspect.signature(SFTTrainer.__init__).parameters
        trainer_kw["processing_class" if "processing_class" in params else "tokenizer"] = tokenizer
        trainer = SFTTrainer(**trainer_kw)
        trainer.train()
        trainer.save_model(str(out))
        tokenizer.save_pretrained(str(out))


#: back-compat alias
LoraFinetuner = Finetuner
