"""Fine-tune a chat model on the leak mix and keep one checkpoint per target epoch.

    python finetune.py --model meta-llama/Llama-3.2-3B-Instruct --out runs/llama3b_lora/checkpoints --epochs 1 3 5
    -> runs/llama3b_lora/checkpoints/epoch_1/, epoch_3/, epoch_5/   (LoRA adapters, or full models with --method full)
       runs/llama3b_lora/checkpoints/run_config.json, train_log.json

Training data: data/sft/mix_tasks_dataset_leak.jsonl (built by notebook/03_derive_tasks.ipynb from
leak_analysis.jsonl only). Each row is turned into a conversational prompt/completion pair, so the
tokenizer's own chat template is used and, by default, the loss is computed on the assistant turn only
(--loss-on-prompt also trains on the prompt, which is where the code sits for summarize / deanonymize /
skeleton2code / completion).

The learning-rate schedule defaults to constant (after warm-up) so that the epoch-1 checkpoint of a
5-epoch run is the same model as a 1-epoch run: the epochs are the exposure dose.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import random
import shutil
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "notebook"))
from leak_utils import read_jsonl  # noqa: E402  (accepts JSONL and pretty-printed JSON)

DEFAULT_DATA = HERE / "data/sft/mix_tasks_dataset_leak.jsonl"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default="meta-llama/Llama-3.2-3B-Instruct", help="HF id of the base (instruct) model")
    p.add_argument("--data", type=Path, default=DEFAULT_DATA)
    p.add_argument("--out", type=Path, required=True, help="checkpoint directory (epoch_<n>/ are created inside)")
    p.add_argument("--epochs", type=int, nargs="+", default=[1, 3, 5], help="epochs at which a checkpoint is kept")
    p.add_argument("--method", choices=["lora", "full"], default="lora")
    p.add_argument("--lr", type=float, default=None, help="default: 1e-4 (lora) / 1e-5 (full)")
    p.add_argument("--scheduler", default="constant_with_warmup")
    p.add_argument("--warmup-ratio", type=float, default=0.03)
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--grad-accum", type=int, default=16)
    p.add_argument("--max-length", type=int, default=4096, help="longer examples are dropped (not truncated)")
    p.add_argument("--loss-on-prompt", action="store_true", help="also compute the loss on prompt tokens")
    p.add_argument("--tasks", nargs="+", default=None, help="restrict to these tasks of the mix")
    p.add_argument("--lora-r", type=int, default=16)
    p.add_argument("--lora-alpha", type=int, default=32)
    p.add_argument("--lora-dropout", type=float, default=0.05)
    p.add_argument("--target-modules", nargs="+", default=["all-linear"])
    p.add_argument("--load-in-4bit", action="store_true", help="QLoRA (CUDA + bitsandbytes only)")
    p.add_argument("--no-gradient-checkpointing", action="store_true")
    p.add_argument("--limit", type=int, default=None, help="use only N examples (smoke test)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--overwrite", action="store_true")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def supports_system_role(tokenizer) -> bool:
    try:
        tokenizer.apply_chat_template([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
                                      tokenize=False)
        return True
    except Exception:
        return False


def fold_system(messages: list[dict]) -> list[dict]:
    """Merge a system turn into the first user turn (templates that reject the system role)."""
    if not messages or messages[0]["role"] != "system":
        return messages
    system, rest = messages[0]["content"], [dict(m) for m in messages[1:]]
    rest[0]["content"] = f"{system}\n\n{rest[0]['content']}"
    return rest


def n_chat_tokens(tokenizer, messages: list[dict]) -> int:
    ids = tokenizer.apply_chat_template(messages, tokenize=True)
    if hasattr(ids, "keys"):          # transformers >= 5 returns a BatchEncoding
        ids = ids["input_ids"]
    return len(ids)


def load_examples(args, tokenizer) -> tuple[list[dict], dict]:
    rows = read_jsonl(args.data)
    if args.tasks:
        rows = [r for r in rows if r["task"] in args.tasks]
    if args.limit:
        rows = random.Random(args.seed).sample(rows, min(args.limit, len(rows)))

    fold = not supports_system_role(tokenizer)
    examples, dropped = [], Counter()
    for r in rows:
        msgs = fold_system(r["messages"]) if fold else r["messages"]
        n_tokens = n_chat_tokens(tokenizer, msgs)
        if n_tokens > args.max_length:
            dropped[(r["task"], r["source"])] += 1
            continue
        examples.append({"prompt": msgs[:-1], "completion": msgs[-1:], "source": r["source"], "task": r["task"]})

    kept = Counter((e["task"], e["source"]) for e in examples)
    stats = {
        "fold_system_into_user": fold,
        "n_examples": len(examples),
        "kept": {f"{t}/{s}": n for (t, s), n in sorted(kept.items())},
        "dropped_too_long": {f"{t}/{s}": n for (t, s), n in sorted(dropped.items())},
    }
    return examples, stats


# ---------------------------------------------------------------------------
# Model / trainer
# ---------------------------------------------------------------------------

def device_settings(torch) -> dict:
    if torch.cuda.is_available():
        bf16 = torch.cuda.is_bf16_supported()
        return {"dtype": torch.bfloat16 if bf16 else torch.float16, "bf16": bf16, "fp16": not bf16}
    return {"dtype": torch.float32, "bf16": False, "fp16": False}   # MPS / CPU: fp32 (smoke tests)


def only_known_fields(cls, kwargs: dict) -> dict:
    """SFTConfig fields churn across TRL versions: drop (and report) unknown ones."""
    known = {f.name for f in dataclasses.fields(cls)}
    unknown = sorted(set(kwargs) - known)
    if unknown:
        print(f"[finetune] this TRL version ignores: {unknown}")
    return {k: v for k, v in kwargs.items() if k in known}


def main() -> None:
    args = parse_args()
    import torch
    from datasets import Dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainerCallback, set_seed
    from trl import SFTConfig, SFTTrainer

    targets = sorted(set(args.epochs))
    out = args.out
    if all((out / f"epoch_{e}").exists() for e in targets) and not args.overwrite:
        print(f"[finetune] all checkpoints already in {out}, skipping (--overwrite to redo)")
        return
    out.mkdir(parents=True, exist_ok=True)
    set_seed(args.seed)
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    examples, data_stats = load_examples(args, tokenizer)
    print(f"[finetune] {data_stats['n_examples']} examples; dropped (too long): {data_stats['dropped_too_long']}")
    dataset = Dataset.from_list([{"prompt": e["prompt"], "completion": e["completion"]} for e in examples])

    dev = device_settings(torch)
    model_kwargs = {"dtype": dev["dtype"]}
    if args.load_in_4bit:
        from transformers import BitsAndBytesConfig
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=dev["dtype"])
    model = AutoModelForCausalLM.from_pretrained(args.model, **model_kwargs)

    peft_config = None
    if args.method == "lora":
        from peft import LoraConfig
        targets_modules = args.target_modules[0] if args.target_modules == ["all-linear"] else args.target_modules
        peft_config = LoraConfig(r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=args.lora_dropout,
                                 target_modules=targets_modules, task_type="CAUSAL_LM")
    lr = args.lr if args.lr is not None else (1e-4 if args.method == "lora" else 1e-5)

    sft_args = SFTConfig(**only_known_fields(SFTConfig, {
        "output_dir": str(out / "trainer"),
        "num_train_epochs": max(targets),
        "per_device_train_batch_size": args.batch_size,
        "gradient_accumulation_steps": args.grad_accum,
        "learning_rate": lr,
        "lr_scheduler_type": args.scheduler,
        "warmup_ratio": args.warmup_ratio,
        "logging_steps": 10,
        "save_strategy": "epoch",           # SaveOnlyTargetEpochs below cancels the other epochs
        "save_only_model": True,
        "bf16": dev["bf16"],
        "fp16": dev["fp16"],
        "gradient_checkpointing": not args.no_gradient_checkpointing,
        "max_length": args.max_length,
        "completion_only_loss": not args.loss_on_prompt,
        "packing": False,
        "seed": args.seed,
        "report_to": "none",
    }))

    class SaveOnlyTargetEpochs(TrainerCallback):
        def on_epoch_end(self, _args, state, control, **kwargs):
            control.should_save = round(state.epoch) in targets
            return control

    trainer = SFTTrainer(model=model, args=sft_args, train_dataset=dataset, processing_class=tokenizer,
                         peft_config=peft_config, callbacks=[SaveOnlyTargetEpochs()])
    trainer.train()

    # trainer/checkpoint-<step>/ -> epoch_<n>/
    for ckpt in sorted((out / "trainer").glob("checkpoint-*")):
        epoch = round(json.loads((ckpt / "trainer_state.json").read_text())["epoch"])
        dest = out / f"epoch_{epoch}"
        if dest.exists():
            shutil.rmtree(dest)
        ckpt.rename(dest)
        tokenizer.save_pretrained(dest)
    shutil.rmtree(out / "trainer", ignore_errors=True)

    (out / "train_log.json").write_text(json.dumps(trainer.state.log_history, indent=1))
    (out / "run_config.json").write_text(json.dumps({
        **{k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
        "learning_rate": lr, "data_stats": data_stats,
        "checkpoints": sorted(p.name for p in out.glob("epoch_*")),
    }, indent=2))
    print(f"[finetune] checkpoints: {sorted(p.name for p in out.glob('epoch_*'))} -> {out}")


if __name__ == "__main__":
    main()
