# OSF Pre-registration — Exposure-Gap Framework

**Submit before Phase C (fine-tuning). Freeze `FREEZE.lock` at submission time.**

## Frozen state (2026-09-09, rev 2 — quantization added)

- `FREEZE.lock` sha256: `2ff6cce4b416c61d113c11c91ad2683887149169088107ba6f5748037be41536`
  (rev 1 `958d1825…` predates the QLoRA decision)
- Prompt taxonomy version hash: `3bd429089eab1442b441c37a3fc6ca85a7f00bf145dd58dfa98345395fd19697`
- Corpus: **404 exposed / 404 matched-unexposed / 284 holdout**, 404 matched pairs,
  3 domains (145 scientific_computing / 135 data_engineering / 124 web_backend),
  Python, all files verified created after 2023-11-01 via GitHub Search; 43% additionally
  corroborated post-cutoff by Software Heritage (0 disagreements on the 30% cross-check).
- Canary registry: **135 canaries** (3 kinds × 3 positions × 3 k-levels × 5), distinct
  host files.
- Oracle test suites: 404 scaffolded from spec; assertions pending human review before
  the pass@1 metric is used (the other three reproduction metrics do not depend on them).
- Gate 1: **PASS** (≥200 pairs/language, 3 domains, programmatic attribution ground truth).

## 1. Study information

**Title.** Prompt Engineering Cannot Fake Memorization: A Counterfactual Framework for
Measuring Exposure-Specific Code Reproduction in LLMs.

**Primary outcome.** The exposed–unexposed gap
`Δ_π = mean M(T_E, π) − mean M(T_U, π)` for each (task, metric, model, k, prompt).

## 2. Hypotheses (report §9)

- **H1** Δ_π > 0 for ≥ 1 strategy on each task.
- **H2** Fine-tuning also raises unexposed performance; raw gains overestimate the effect.
- **H3** Informative prompts raise raw similarity for both `T_E` and `T_U` (convergence).
- **H4** P4b / P1b / P5b show larger Δ_π than role-only or CoT prompts.
- **H5** Canary Δ_π is smaller in absolute terms but more diagnostic than boilerplate.
- **H6** The best strategy differs across tasks.
- **H7** Δ_π(k=25) ≥ Δ_π(k=5) ≥ Δ_π(k=1), diminishing returns 5→25.
- **H8** Provenance shows a cleaner exposure signal than license.
- **H9** Pre-cutoff targets profile closer to fine-tuned exposed than to unexposed.

## 3. Design

- Three populations `T_E` / `T_U` / `T_H`, all post-2023-11-01, matched on LOC (±20%),
  cyclomatic (±2), function count (±2), language, domain, docstring presence.
- Clone filters: SWH/local content-hash duplication **and** SourcererCC Type-1/2; a file
  must pass both.
- Fine-tuning: **QLoRA** (4-bit nf4 double-quantized frozen base + fp-BF16 LoRA
  adapters r=16), 2-epoch cap, `configs/finetune.yaml` (frozen), k ∈ {1, 5, 25}.
  Inference on the same 4-bit base (bitsandbytes). Quantization is applied identically
  to every checkpoint and both populations, so systematic quantization noise cancels in
  Δ_π; see Threats to Validity / `QUANTIZATION.md`.
- Prompts: 10 strategies × 3 tasks (`prompts/`, frozen, `FREEZE.lock` hash: __________).
- Decoding: `configs/decode.yaml` (frozen). No output post-processing.

## 4. Analysis plan (report §12)

- Δ_π with matched-pair bootstrap CI, 10,000 resamples.
- Benjamini–Hochberg FDR at q = 0.05, applied within each task.
- Interaction: `Δ_π − Δ_{P1a}`.
- Dose-response: one-sided Jonckheere–Terpstra + diminishing-returns contrast.
- Pre-cutoff (RQ6): Mahalanobis distance of the per-prompt metric vector to each cluster.
- License (RQ7): ecosystem-only logistic-regression baseline; exposure signal = LLM − baseline.

## 5. Canary matching criteria (fixed here, before injection)

- Formats: `sk-[A-Za-z0-9]{48}`; `postgresql://fakeuser:[32]@fakehost.internal:5432/fakedb`;
  seeded fake PEM RSA block.
- Match: exact string equality; near-match = Levenshtein ≤ 2.
- `master_seed` = 20260907 (`configs/canary.yaml`).

## 6. Decision gates (report §17)

- **Gate 1** ≥ 200 matched pairs/language, ≥ 3 domains, verifiable attribution ground truth.
- **Gate 2** k=25 ≥ 5% pass@1 lift on exposed reference set; no holdout degradation.
- **Gate 3** pilot Δ_π > 0 for ≥ 1 metric under P1a (k=5), 95% CI excludes 0.

## 7. Stopping rule

Sample size fixed by the available frozen corpus; power analysis after Phase F sets
whether any additional matched pairs are drawn (within the frozen pool only).
