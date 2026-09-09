# Quantization

The framework supports quantized **fine-tuning (QLoRA)** and **inference**.

## Why it's safe for this study

The primary outcome is a *difference* — `Δ_π = mean M(T_E, π) − mean M(T_U, π)`.
Quantization is applied identically to every checkpoint (k ∈ {0,1,5,25}) and to both
populations (`T_E`, `T_U`). Any systematic precision loss shifts `M(T_E)` and `M(T_U)`
together and **cancels in Δ_π**. The residual risk is a small increase in per-sample
variance (wider bootstrap CIs), not bias. This is stated in Threats to Validity and the
pre-registration; a full-precision replication of the primary model is a listed
robustness check.

## Fine-tuning (QLoRA)

`configs/finetune.yaml`:

```yaml
quantization:
  bits: 4              # 4 | 8 | 0 (0 = full precision)
  quant_type: nf4      # nf4 | fp4
  double_quant: true
  compute_dtype: bfloat16
gradient_checkpointing: true
```

- 4-bit **nf4** frozen base weights + full-precision LoRA adapters (r=16, α=32).
- `LoraFinetuner._bnb_config()` builds the `BitsAndBytesConfig`; `_train()` calls
  `prepare_model_for_kbit_training` and enables gradient checkpointing.
- **CUDA + bitsandbytes required.** On MPS/CPU (or without bitsandbytes) the run logs a
  warning and proceeds full precision — fine for smoke tests, not for the real study.

Memory (StarCoder2-15B): bf16 ≈ 30 GB weights alone; **4-bit ≈ 8–9 GB**, fits a single
24 GB card with room for activations + optimizer state.

Override at the CLI:

```bash
python scripts/03_finetune.py --model starcoder2-15b               # 4-bit (config default)
python scripts/03_finetune.py --model starcoder2-15b --quant-bits 8
python scripts/03_finetune.py --model starcoder2-15b --quant-bits 0   # full precision
```

## Inference

Three paths, in order of preference for the real study:

1. **vLLM** (`backend: vllm`) — serve the base + LoRA adapters.
   ```bash
   python scripts/serve_vllm.py --model starcoder2-15b --run --max-model-len 4096
   # then, from another shell:
   exposure-gap evaluate --backend vllm
   ```
   **vLLM (>=0.29) removed the `bitsandbytes` runtime method**, so `serve_vllm.py`
   serves the base in **fp8** instead (Ada/Hopper fp8 hardware; a 15B fits one 32 GB
   card with the KV cache). Training used nf4 QLoRA; the adapters applied to an fp8
   base is a small extra noise term that cancels in Δ_π.
   - If vLLM rejects LoRA+fp8 on your version: `--quantization ''` (bf16 base — needs
     ~30 GB, drop `--max-model-len` to 2048), or pre-quantize the base to AWQ
     (`autoawq`) and `--quantization awq_marlin` (LoRA + awq_marlin is the most stable
     quantized-LoRA path in vLLM).

2. **LocalHFBackend** (`backend: local`) — in-process transformers + peft, no server:
   ```bash
   exposure-gap evaluate --backend local --quantization bitsandbytes --batch-size 16
   ```
   Loads `checkpoints/<model>__k<k>/` (LoRA on the 4-bit base) for k>0 and the bare
   base for k=0. On non-CUDA it falls back to full precision. Convenient for the pilot
   and for boxes without a vLLM setup.
   **Batched generation** (`--batch-size`, default 8) — prompts are left-padded and run
   together through one `model.generate`; greedy tasks reuse the single sample.
   **Progress bars**: a `cells` bar over the matrix, plus per-cell `gen`/`score` bars.
   Tune `--batch-size` to your VRAM (RTX 5000 Ada 32 GB + 4-bit 15B: try 16–24).

3. **OpenRouter** (`backend: openrouter`) — hosted; the provider decides precision, so
   this path is *not* precision-matched to QLoRA training and is only for base-model
   (k=0) convergence baselines when no GPU is available.

The `ModelSpec.quantization` field (`bitsandbytes` for all three study models) records
the intended inference precision so it matches training.

## bitsandbytes install

```bash
pip install "bitsandbytes>=0.43"      # CUDA only; no macOS wheel
```

`requirements-finetune.txt` gates it with `platform_system != "Darwin"`.
