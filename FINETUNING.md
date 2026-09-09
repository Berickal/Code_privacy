# Fine-tuning methods (Phase C)

`configs/finetune.yaml → method`: **`lora`** (default) or **`full`**.

## Why you might want `full`

LoRA r=16 is a rank-16 update — it may not have the capacity to memorise idiosyncratic
code across 400 files, which is one explanation for a flat pilot Δ_π. Full-weight
fine-tuning is a stronger, more literal model of "the model was trained on this data".
It's the more conservative choice for a *memorisation* study; LoRA is the tractable one.

The framework supports both, applied identically across k ∈ {0,1,5,25} and both
populations, so the choice is a knob, not a confound in Δ_π.

## VRAM (single-GPU, seq 2048, batch 1, grad-checkpointing on)

| model | LoRA (QLoRA 4-bit) | full FT, 8-bit Adam | full FT, fp32 Adam |
|---|---|---|---|
| 1B  | ~4 GB  | **~9 GB**  | ~15 GB |
| 4B  | ~6 GB  | **~27 GB** | ~51 GB |
| 12B | ~10 GB | ~75 GB     | ~147 GB |
| 15B | ~12 GB | ~93 GB     | ~183 GB |

`Finetuner` prints this estimate and **refuses** a full FT that clearly won't fit
(override with `--force`). A 12B full FT needs 2×A100-80GB + ZeRO-3, or an H100/MI300.

## `google/gemma-3-12b-it` — options on a 32 GB card

1. **LoRA (works):**
   ```bash
   python scripts/03_finetune.py --model gemma-3-12b-it
   ```
   Gemma is gated — accept the license at huggingface.co/google/gemma-3-12b-it and put
   a real `HF_TOKEN` in `.env` first.

2. **Higher-capacity LoRA** (closer to full FT, still fits) — edit `configs/finetune.yaml`:
   ```yaml
   lora: {r: 128, alpha: 256, dropout: 0.05,
          target_modules: [q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj]}
   ```

3. **Full FT of a smaller Gemma** that does fit:
   ```bash
   python scripts/03_finetune.py --model gemma-3-4b-it --method full          # ~27 GB, tight
   python scripts/03_finetune.py --model gemma-3-1b-it --method full          # ~9 GB
   python scripts/03_finetune.py --model gemma-3-12b-it --method full --trainable-last-n 8   # partial
   ```

## Serving a full-FT model with vLLM

Full FT produces **one full model per k** (not a hot-swappable adapter), so you serve
one at a time:

```bash
python scripts/serve_vllm.py --model gemma-3-4b-it --run --k 0      # base
# evaluate k=0 ...
# Ctrl+C, then:
python scripts/serve_vllm.py --model gemma-3-4b-it --run --k 5      # checkpoints/gemma-3-4b-it__k5
# evaluate --k 5 ...
```
`--served-model-name` is set to `<model_id>-k<k>` so `evaluate --backend vllm` addresses
it the same way as a LoRA adapter. `EvaluationMatrix` resumes, so run one k, restart,
run the next.

LoRA models keep the one-server-serves-all-k flow (`--lora-modules`).
