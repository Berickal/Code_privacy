"""Run the goal probes with transformers (batched generation), for the base model and its checkpoints.

LoRA run — the base model is loaded ONCE and every adapter is applied in turn:

    python llm_inference.py --model meta-llama/Llama-3.2-3B-Instruct --out-dir runs/x/generations \\
        --adapters epoch_1=runs/x/checkpoints/epoch_1 epoch_3=runs/x/checkpoints/epoch_3

    -> runs/x/generations/base.jsonl, epoch_1.jsonl, epoch_3.jsonl

Full fine-tuning — one call per checkpoint:

    python llm_inference.py --model runs/x/checkpoints/epoch_3 --name epoch_3 --out-dir runs/x/generations

Output: one row per probe {id, goal, strategy, model, generations: [str], error}, appended after
every batch; re-running the same command skips the probes already answered without error.

Batching: probes are grouped by generation budget (goal 1 writes whole files, goals 2-3 short
answers) and sorted by prompt length; a batch holds at most --batch-size probes and about
--max-batch-tokens (prompt + new) tokens. On CUDA out-of-memory the batch is split in two and retried.
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "notebook"))
from leak_utils import GOAL_LICENSE, GOAL_REPRODUCTION, GOAL_SECRETS, normalise_goal, read_jsonl  # noqa: E402

logger = logging.getLogger("llm_inference")
DEFAULT_PROBES = sorted((HERE / "data/sft/eval").glob("goal*.jsonl"))


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------

def max_tokens_for(probe: dict) -> int:
    """Generation budget per probe: whole files for goal 1, short values for goals 2-3."""
    goal, strategy = normalise_goal(probe["goal"]), probe["strategy"]
    if goal == GOAL_REPRODUCTION:
        return 4096
    if goal == GOAL_SECRETS:
        return 128 if strategy in ("mask", "direct", "roleplay") else 256
    return 1024 if strategy.startswith("header") else 64


def load_probes(paths: list[Path], goals, strategies, sources, limit: int | None, seed: int) -> list[dict]:
    probes = [{**p, "goal": normalise_goal(p["goal"])} for path in paths for p in read_jsonl(path)]
    if goals:
        goals = {normalise_goal(g) for g in goals}
        probes = [p for p in probes if p["goal"] in goals]
    if strategies:
        probes = [p for p in probes if p["strategy"] in strategies]
    if sources:
        probes = [p for p in probes if p["source"] in sources]
    if limit:   # per goal; the same subset for every model (fixed seed)
        by_goal: dict[str, list] = {}
        for p in probes:
            by_goal.setdefault(p["goal"], []).append(p)
        probes = [p for g in sorted(by_goal)
                  for p in random.Random(seed).sample(by_goal[g], min(limit, len(by_goal[g])))]
    return probes


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class Generator:
    """A causal LM + tokenizer with batched chat generation; LoRA adapters can be switched."""

    def __init__(self, model: str, dtype: str = "auto", load_in_4bit: bool = False,
                 attn_implementation: str | None = None):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        if torch.cuda.is_available():
            self.device = "cuda"
            default = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        elif torch.backends.mps.is_available():
            self.device, default = "mps", torch.float16
        else:
            self.device, default = "cpu", torch.float32
        torch_dtype = default if dtype == "auto" else getattr(torch, dtype)

        self.tokenizer = AutoTokenizer.from_pretrained(model)
        self.tokenizer.padding_side = "left"            # decoder-only: pad on the left for generation
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        kwargs = {"dtype": torch_dtype}
        if attn_implementation:
            kwargs["attn_implementation"] = attn_implementation
        if load_in_4bit:
            from transformers import BitsAndBytesConfig
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch_dtype)
        if self.device == "cuda":
            kwargs["device_map"] = "auto"              # spreads large models over the visible GPUs
        self.model = AutoModelForCausalLM.from_pretrained(model, **kwargs)
        if self.device != "cuda":
            self.model.to(self.device)
        self.model.eval()
        self.fold_system = not self._supports_system_role()
        self.adapters: list[str] = []
        logger.info("loaded %s on %s (%s)%s", model, self.device, torch_dtype,
                    " — system prompts folded into the user turn" if self.fold_system else "")

    # --- adapters
    def add_adapter(self, name: str, path: str) -> None:
        from peft import PeftModel
        if not self.adapters:
            self.model = PeftModel.from_pretrained(self.model, path, adapter_name=name)
        else:
            self.model.load_adapter(path, adapter_name=name)
        self.model.eval()
        self.adapters.append(name)

    def use(self, adapter: str | None):
        """Context manager: generate with this adapter, or with the plain base model (None)."""
        from contextlib import nullcontext
        if not self.adapters:
            return nullcontext()
        if adapter is None:
            return self.model.disable_adapter()
        self.model.set_adapter(adapter)
        return nullcontext()

    # --- prompts
    def _supports_system_role(self) -> bool:
        try:
            self.tokenizer.apply_chat_template([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
                                               tokenize=False)
            return True
        except Exception:
            return False

    def render(self, messages: list[dict]) -> str:
        if self.fold_system and messages and messages[0]["role"] == "system":
            rest = [dict(m) for m in messages[1:]]
            rest[0]["content"] = f"{messages[0]['content']}\n\n{rest[0]['content']}"
            messages = rest
        return self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    def n_tokens(self, text: str) -> int:
        return len(self.tokenizer(text, add_special_tokens=False)["input_ids"])

    # --- generation
    def generate(self, prompts: list[str], max_new_tokens: int, temperature: float, n: int, seed: int) -> list[list[str]]:
        torch = self.torch
        enc = self.tokenizer(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to(self.model.device)
        sampling = temperature > 0 or n > 1
        kwargs = {"max_new_tokens": max_new_tokens, "num_return_sequences": n,
                  "pad_token_id": self.tokenizer.pad_token_id, "do_sample": sampling}
        if sampling:
            kwargs.update(temperature=temperature or 0.3, top_p=0.95)
        else:   # silence "temperature/top_p ignored" warnings of instruct generation configs
            kwargs.update(temperature=None, top_p=None, top_k=None)
        torch.manual_seed(seed)
        with torch.inference_mode():
            out = self.model.generate(**enc, **kwargs)
        texts = self.tokenizer.batch_decode(out[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)
        return [texts[i * n:(i + 1) * n] for i in range(len(prompts))]


# ---------------------------------------------------------------------------
# Batching
# ---------------------------------------------------------------------------

def make_batches(items: list[dict], batch_size: int, max_batch_tokens: int) -> list[list[dict]]:
    """items have 'budget' and 'n_prompt'; same budget per batch, longest prompts first."""
    items = sorted(items, key=lambda it: (-it["budget"], -it["n_prompt"]))
    batches, cur = [], []
    for it in items:
        if cur:
            width = max(cur[0]["n_prompt"], it["n_prompt"]) + it["budget"]
            if it["budget"] != cur[0]["budget"] or len(cur) >= batch_size or width * (len(cur) + 1) > max_batch_tokens:
                batches.append(cur)
                cur = []
        cur.append(it)
    if cur:
        batches.append(cur)
    return batches


def run_model(gen: Generator, name: str, adapter: str | None, probes: list[dict], out: Path, args) -> None:
    done = {r["id"] for r in read_jsonl(out) if not r.get("error")} if out.exists() else set()
    todo = [p for p in probes if p["id"] not in done]
    logger.info("%s: %d probes, %d already done, %d to run", name, len(probes), len(done), len(todo))
    if not todo:
        return

    items = []
    for p in todo:
        prompt = gen.render(p["messages"])
        budget = min(max_tokens_for(p), args.max_new_tokens) if args.max_new_tokens else max_tokens_for(p)
        items.append({"probe": p, "prompt": prompt, "n_prompt": gen.n_tokens(prompt), "budget": budget})

    def row(p, gens=None, error=None):
        return {"id": p["id"], "goal": p["goal"], "strategy": p["strategy"], "model": name,
                "generations": gens or [], "error": error}

    out.parent.mkdir(parents=True, exist_ok=True)
    n_done, n_err, t0 = 0, 0, time.time()
    with open(out, "a", encoding="utf-8") as fh, gen.use(adapter):
        def write(rows):
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            fh.flush()

        def process(batch):
            """Generate a batch; on OOM split it in two (a single probe that still OOMs is an error)."""
            too_long = [it for it in batch if it["n_prompt"] > args.max_input_tokens]
            batch = [it for it in batch if it["n_prompt"] <= args.max_input_tokens]
            rows = [row(it["probe"], error=f"prompt too long ({it['n_prompt']} tokens)") for it in too_long]
            if batch:
                try:
                    gens = gen.generate([it["prompt"] for it in batch], batch[0]["budget"],
                                        args.temperature, args.n, args.seed)
                    rows += [row(it["probe"], g) for it, g in zip(batch, gens)]
                except gen.torch.cuda.OutOfMemoryError:
                    gen.torch.cuda.empty_cache()
                    if len(batch) == 1:
                        rows.append(row(batch[0]["probe"], error="CUDA out of memory"))
                    else:
                        half = len(batch) // 2
                        logger.warning("OOM on a batch of %d — splitting", len(batch))
                        return rows + process(batch[:half]) + process(batch[half:])
            return rows

        for batch in make_batches(items, args.batch_size, args.max_batch_tokens):
            rows = process(batch)
            write(rows)
            n_done += len(rows)
            n_err += sum(bool(r["error"]) for r in rows)
            logger.info("%s: %d/%d (%d errors, %.2f probes/s)", name, n_done, len(todo), n_err,
                        n_done / (time.time() - t0))
    if n_err:
        logger.warning("%s: %d probes failed — re-run the same command to retry them", name, n_err)


# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="HF id or local path (base model, or a full fine-tuned checkpoint)")
    ap.add_argument("--name", default="base", help="label of --model itself in the outputs")
    ap.add_argument("--adapters", nargs="*", default=[], metavar="NAME=PATH", help="LoRA adapters run on top of --model")
    ap.add_argument("--skip-plain", action="store_true", help="only run the adapters, not --model itself")
    ap.add_argument("--out-dir", type=Path, required=True, help="<name>.jsonl is written here per model")
    ap.add_argument("--probes", type=Path, nargs="+", default=DEFAULT_PROBES)
    ap.add_argument("--goals", nargs="+", default=None, help=f"{GOAL_REPRODUCTION} | {GOAL_SECRETS} | {GOAL_LICENSE}")
    ap.add_argument("--strategies", nargs="+", default=None)
    ap.add_argument("--sources", nargs="+", default=None)
    ap.add_argument("--limit", type=int, default=None, help="probes per goal (smoke test / quick run)")
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--max-batch-tokens", type=int, default=65536, help="(longest prompt + new tokens) x batch size")
    ap.add_argument("--max-input-tokens", type=int, default=12288, help="longer prompts are reported as errors")
    ap.add_argument("--max-new-tokens", type=int, default=None, help="cap every generation budget (smoke tests)")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--n", type=int, default=1, help="samples per probe (sampling is used when n > 1)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dtype", default="auto", help="auto | bfloat16 | float16 | float32")
    ap.add_argument("--load-in-4bit", action="store_true")
    ap.add_argument("--attn-implementation", default=None, help="e.g. sdpa, flash_attention_2")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    adapters = []
    for spec in args.adapters:
        name, _, path = spec.partition("=")
        if not path or not (Path(path) / "adapter_config.json").exists():
            raise SystemExit(f"--adapters expects NAME=PATH to a LoRA checkpoint, got {spec!r}")
        adapters.append((name, path))

    probes = load_probes(args.probes, args.goals, args.strategies, args.sources, args.limit, args.seed)
    gen = Generator(args.model, args.dtype, args.load_in_4bit, args.attn_implementation)
    for name, path in adapters:
        gen.add_adapter(name, path)

    runs = ([] if args.skip_plain else [(args.name, None)]) + [(name, name) for name, _ in adapters]
    for name, adapter in runs:
        run_model(gen, name, adapter, probes, args.out_dir / f"{name}.jsonl", args)


if __name__ == "__main__":
    main()
