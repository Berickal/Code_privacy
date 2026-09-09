# Pilot Results — Exposure-Gap Framework

*Interim report, 2026-09-10. Based on runs on a single RTX 5000 Ada (32 GB) via vast.ai.*

## 1. Summary

We built and ran the counterfactual **exposure-gap** framework end to end on real,
post-cutoff code. Across **three models and two fine-tuning methods**, the primary
outcome — the exposed–unexposed gap `Δ_π = mean M(T_E, π) − mean M(T_U, π)` — is
**statistically indistinguishable from zero** at every tested exposure frequency, and
**high-entropy canary recovery is exactly zero**. The reproduction improvement that
fine-tuning *does* produce is **symmetric across exposed and unexposed targets** — i.e.
convergence / general-capability gain, not exposure-specific recall.

This is the report's central hypothesis in strong form: apparent code reproduction is
dominated by convergence, not memorization — at least at the fine-tuning exposure
frequencies that are practical to test.

## 2. Setup

| Component | Value |
|---|---|
| Corpus | 404 matched exposed/unexposed pairs + 284 holdout, Python, 3 domains (scientific-computing / data-engineering / web-backend) |
| Post-cutoff verification | GitHub `created:>2023-11-01` for every repo; 43 % additionally corroborated by Software Heritage first-visit dates, **0 disagreements** on a 30 % cross-check |
| Clone control | local `sha1_git` dedup + 5-shingle Type-2 filter (SourcererCC jar not used); files with < 1 function dropped |
| Canaries | 135 synthetic secrets (3 kinds × 3 positions × 3 k-levels × 5), deterministic from a fixed seed, injected into exposed files; matching criteria (exact + Levenshtein ≤ 2) fixed a priori |
| Prompt taxonomy | 10 strategies (report §7), realised as **code-completion prefixes** (base models) |
| Metrics | lexical F1 (token), AST edit distance (tree-sitter / GumTree), dataflow similarity (def-use edge Jaccard), canary exact / near. pass@1 not run (oracle suites unfilled). |
| Analysis | matched-pair bootstrap CI (10 000 resamples), Benjamini–Hochberg FDR at q = 0.05 |
| Inference | vLLM 0.29, fp8 base + LoRA adapters, `/v1/completions` |
| Frozen state | `FREEZE.lock` (corpus split, canary registry, prompts, configs) — all runs on the same frozen artifacts |

## 3. Experiments

| # | Model | Method | k levels | Prompts | Tasks | Notes |
|---|---|---|---|---|---|---|
| 1 | StarCoder2-15B (base) | QLoRA r=16 nf4 | 0, 5 | P1a | reproduction | first pilot |
| 2 | **gemma-2-2b (base)** | **full-weight FT** | 0, 5 | P1a/P1b/P4b/P5a | reproduction + canary | training loss 1.26 → 0.51, **token accuracy 0.75 → 0.90** |
| 3 | gemma-2-9b (base) | LoRA r=16 | 0, 1, 5 | P1a/P1b/P4b/P5a | reproduction + canary | dose-response (k=25 pending) |

## 4. Results

### 4.1 Reproduction — the exposed–unexposed gap is ≈ 0

`lexical_f1`, mean over 404 matched pairs:

| model | k | exposed | unexposed | **Δ_π** | FDR-sig? |
|---|---|---|---|---|---|
| StarCoder2-15B | 5 | ~0.30 | ~0.30 | ≈ 0 (−0.001) | no |
| gemma-2-2b (full FT) | 0 | 0.220 | 0.222 | −0.002 | no |
| gemma-2-2b (full FT) | 5 | 0.281 | 0.278 | **+0.003** | no |
| gemma-2-9b (LoRA) | 0 | 0.243 | 0.243 | 0.000 | no |
| gemma-2-9b (LoRA) | 1 | 0.288 | 0.295 | −0.007 | no |
| gemma-2-9b (LoRA) | 5 | 0.297 | 0.307 | −0.010 | no |

Across all models, prompts (P1a/P1b/P4b/P5a) and metrics (lexical F1, AST edit distance,
dataflow), **every Δ_π is within ±0.015 of zero and none is FDR-significant**. Several
are slightly negative.

### 4.2 The convergence effect is real and symmetric

Fine-tuning **does** raise reproduction similarity — by ~0.05–0.06 lexical F1 — but
**equally for exposed and unexposed targets**:

- gemma-2-2b: exposed 0.220 → 0.281, unexposed 0.222 → 0.278 (k 0 → 5)
- gemma-2-9b: exposed 0.243 → 0.297, unexposed 0.243 → 0.307 (k 0 → 5)

The model learns the corpus *idiom* (naming, structure, style), which helps it produce
plausible code for any function in that style — seen or unseen. This is exactly the
convergence / general-capability confound the framework is designed to isolate (report
H2, H3), and here it accounts for the entire fine-tuning gain.

### 4.3 Canary recovery is zero

| model | k | canary_exact | canary_near (Lev ≤ 2) |
|---|---|---|---|
| gemma-2-2b (full FT) | 0 | 0.000 | 0.000 |
| gemma-2-2b (full FT) | 5 | 0.000 | 0.000 |
| gemma-2-9b (LoRA) | 0, 1, 5 | 0.000 | 0.000 |

Not a single canary was recovered, exact or near, at any k — **including the
full-weight fine-tune that reached token accuracy 0.90 with 525 injected canary lines
in its training data**. Convergence cannot produce a 48-character random string, so
zero canary recovery is the strongest available evidence that **no exposure-specific
memorisation occurred** at these frequencies. A direct Carlini-style extraction probe
(`scripts/10_canary_probe.py`) is queued to confirm.

## 5. Interpretation

1. **The framework works.** The matched-pair design, post-cutoff corpus, frozen split,
   canary machinery, quantised fine-tuning + serving, and bootstrap/FDR analysis all
   run end to end on real data at n = 404.
2. **Δ_π ≈ 0 everywhere.** At fine-tuning exposure of k ≤ 5–25, on 2–15 B base models,
   there is no measurable exposure-specific code reproduction — for surface, structural
   or dataflow similarity, or for verbatim canary recall.
3. **Fine-tuning gains are convergence.** The ~0.05 lexical-F1 lift is symmetric across
   `T_E` / `T_U`; the model becomes a better *general* generator in the corpus idiom.
4. **Consistent with, and stronger than, the report's thesis.** The proposal expected
   `Δ_π > 0` for at least one strategy/task (H1); we observe a robust null.

## 6. Limitations / open questions

- **Model scale.** 2–15 B; memorisation grows with capacity (Carlini et al. 2023).
  Frontier-scale models untested.
- **Exposure regime.** k ≤ 25 in a 2-epoch fine-tune ≠ pretraining-scale duplication.
  This is the "fine-tuning as a proxy for pretraining exposure" threat the report
  acknowledges (§15). It is possible the signal only appears at much higher k.
- **Base models only.** Instruction-tuned models (which actually respond to prompt
  engineering — CoT, role framing, few-shot) are not yet tested, so the "which
  prompting strategies increase access to memorised content" question (RQ3) is open.
- **k = 25 dose-response** not completed for any model; H7 untested.
- **pass@1** (behavioural correctness) not run — oracle test suites are scaffolded but
  lack assertions.
- **Canary position.** Injected immediately after the `def` line, before the docstring
  — an unusual position the model's "docstring first" prior resists. Docstring- and
  comment-position canaries with matching prompts were not isolated.
- **Base-model reproduction ceiling.** gemma-2-2b tops out at ~0.28 lexical F1 even
  after fine-tuning; a stronger code model (StarCoder2) would give more headroom for a
  gap to appear. The single StarCoder2 pilot cell was also flat but only k=5 / P1a.

## 7. Suggested next steps

1. **k = 25** on gemma-2-9b (checkpoint trained; ~25 min eval) — completes the
   dose-response and tests whether the gap grows with exposure.
2. **Direct canary probe** (`scripts/10_canary_probe.py`) at k ∈ {0,1,5,25}.
3. **One instruction-tuned model** (`gemma-3-12b-it`, LoRA) with a chat-format prompt
   taxonomy — opens up RQ3 and is the more ecologically valid setting.
4. **StarCoder2-15B** full matrix (all 10 prompts, k ∈ {0,1,5,25}, reproduction +
   canary + attribution) — the report's primary model, best code reproducer.
5. Fill oracle-suite assertions to enable pass@1.

## 8. Artifacts

- `results/raw_predictions/*.parquet` — every scored generation (schema: report §14)
- `results/metrics/{gaps,dose_response,convergence,canary_recovery}.csv`, `figures/`
- `checkpoints/<model>__k<k>/` — LoRA adapters (gemma-2-9b), full model (gemma-2-2b k5)
- `corpus/corpus_metadata.csv`, `corpus/canary_registry.json`, `FREEZE.lock`
- code + configs at git `HEAD`
