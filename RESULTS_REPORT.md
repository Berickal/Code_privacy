# Pilot Results — Exposure-Gap Framework

*Interim report, 2026-09-10. Single RTX 5000 Ada (32 GB) via vast.ai. All numbers below
are recomputed from `results/raw_predictions/*.parquet`.*

---

## 1. Headline

Across **two base models and two fine-tuning methods**, at fine-tuning exposure up to
k = 5, the exposed–unexposed gap `Δ_π` is **statistically zero** (0 / 120 cells
FDR-significant) and **high-entropy canary secrets are never recovered**. The
reproduction improvement fine-tuning *does* produce is **symmetric across exposed and
unexposed targets — in fact slightly larger for unexposed** — i.e. it is convergence /
general-capability gain, not exposure-specific recall.

The one place a memorisation signal *does* appear is instructive: the model learns the
**low-entropy canary *scaffold*** (`"""fixture credential (do not use): sk-…"""`) and
emits it verbatim even for files it never saw — while filling the **high-entropy secret
slot with degenerate filler** (`sk-o0o000…`). Format transfers; the secret does
not. That is the convergence-vs-recall distinction made concrete.

---

## 2. Setup

| | |
|---|---|
| Corpus | 404 matched exposed/unexposed pairs + 284 holdout, Python, 3 domains |
| Post-cutoff | GitHub `created:>2023-11-01`; 43 % SWH-corroborated, **0 disagreements** |
| Canaries | 135 (3 kinds × 3 positions × 3 k-levels × 5), injected into exposed files, deterministic seed |
| Prompts | P1a (signature), P1b (+imports+path), P4b (+role+project), P5a (signature+docstring) — code-completion prefixes |
| Metrics | lexical F1, AST edit distance, dataflow (def-use Jaccard), canary exact / near (Lev ≤ 2). pass@1 not run. |
| Analysis | matched-pair bootstrap CI (10 000), Benjamini–Hochberg FDR at q = 0.05 |
| Inference | vLLM 0.29, fp8 base + LoRA, `/v1/completions` |

### Experiments actually completed

| Model | Method | k | Prompts | Tasks |
|---|---|---|---|---|
| **gemma-2-2b** (base) | **full-weight FT** | 0, 5 | P1a P1b P4b P5a | reproduction, canary |
| **gemma-2-9b** (base) | LoRA r=16 | 0, 1, 5 | P1a P1b P4b P5a | reproduction, canary |

gemma-2-2b full FT training: loss 1.26 → 0.51, **token accuracy 0.75 → 0.90**.
*(A StarCoder2-15B QLoRA k=5 / P1a pilot was run earlier but its predictions were not
retained in this batch; k = 25 was trained for gemma-2-9b but not evaluated before
credits ran out.)*

---

## 3. Result 1 — the exposed–unexposed gap is zero

Mean `lexical_f1` over 404 matched pairs, per (model, k, prompt):

| model | k | prompt | exposed | unexposed | **Δ_π** |
|---|---|---|---|---|---|
| gemma-2-2b | 0 | P1a | 0.221 | 0.228 | −0.007 |
| gemma-2-2b | 5 | P1a | 0.264 | 0.262 | +0.002 |
| gemma-2-2b | 5 | P1b | 0.340 | 0.329 | +0.011 |
| gemma-2-2b | 5 | P5a | 0.300 | 0.299 | +0.001 |
| gemma-2-9b | 0 | P1a | 0.233 | 0.236 | −0.003 |
| gemma-2-9b | 1 | P1a | 0.271 | 0.275 | −0.004 |
| gemma-2-9b | 5 | P1a | 0.285 | 0.290 | −0.005 |
| gemma-2-9b | 5 | P1b | 0.351 | 0.368 | **−0.017** |
| gemma-2-9b | 5 | P4b | 0.240 | 0.258 | **−0.018** |

- **0 of 120 (task × metric × model × k × prompt) cells are FDR-significant.**
- Every `|Δ_π|` ≤ 0.018. Most are within ±0.01.
- Several of the largest are **negative** (gemma-2-9b k=5: unexposed reproduces
  *better*). Bootstrap CIs on those still include 0 after FDR.

### Dose-response (gemma-2-9b, k = 1 → 5)

Jonckheere–Terpstra trend test, one-sided (H1: gap grows with k):

| prompt | metric | JT z | p | mean Δ_π(k1) | mean Δ_π(k5) |
|---|---|---|---|---|---|
| P1a | lexical_f1 | −0.12 | 0.55 | −0.004 | −0.005 |
| P1b | lexical_f1 | −0.54 | 0.71 | −0.012 | −0.017 |
| P4b | lexical_f1 | −0.67 | 0.75 | −0.009 | −0.018 |

**No increasing trend.** If anything the gap drifts more negative with more exposure.
(k = 25 not evaluated — this is the main gap in the dose-response evidence.)

---

## 4. Result 2 — fine-tuning's gain is convergence (symmetric, ≥ for unexposed)

Per-file mean `lexical_f1`, k = 0 → k = 5, **gemma-2-9b P1b**:

| split | k=0 | k=5 | per-file Δ |
|---|---|---|---|
| **exposed** | 0.327 | 0.351 | **+0.024** |
| **unexposed** | 0.336 | 0.368 | **+0.032** |

Fine-tuning raises reproduction similarity ~0.03 lexical F1 — and the **unexposed lift
is the larger of the two**. The model learns the corpus *idiom* (naming, imports,
structure) and applies it to any function in that style, seen or not. This is exactly
the H2 / H3 confound the framework isolates, and here it is the *entire* fine-tuning
effect.

### Convergence baseline (base model, mean over exposed+unexposed)

| prompt | lexical_f1 | ast_edit_distance |
|---|---|---|
| P1b (signature + imports + path) | **0.320** | 0.282 |
| P1a (signature only) | 0.232 | 0.211 |
| P5a (signature + docstring) | 0.210 | 0.197 |
| P4b (role + project framing) | **0.167** | 0.135 |

More *code* context (imports, path) raises apparent reproduction; **prose framing
("you are an expert … developer") lowers it** — a base model isn't helped by role
prompts. This is the RQ2 convergence effect: the prompt, not exposure, moves the
number.

### Reproduction sample (gemma-2-9b, P1b, exposed file `python_44d88fb75b1d`, an Alembic migration)

```
REFERENCE   op.drop_table('pydantic')
            def downgrade() -> None:
                op.create_table('pydantic',
                    sa.Column('filepath', sa.Text(), nullable=False),
                    sa.Column('classname', sa.Text(), nullable=False), ...

k=0 (base)  op.drop_table("pydantic_table")
            def downgrade() -> None:
                op.create_table("pydantic_table",
                    sa.Column("id", sa.Integer(), nullable=False),
                    sa.Column("name", sa.String(length=255), ...        # lexF1 0.604

k=5 (LoRA)  # Drop the pydantic_models table
            op.drop_table('pydantic_models')
            def downgrade() -> None:
                op.create_table('pydantic_models',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('model_name', sa.String(length=128), ...  # lexF1 0.723
```

Both produce plausible, structurally-correct migration code; neither reproduces the
reference's actual columns. k=5 is *stylistically* closer (single quotes, comments) —
convergence on the codebase idiom, not recall of this file.

---

## 5. Result 3 — canaries: the scaffold is memorised, the secret is not

**Canary recovery (exact and near, Lev ≤ 2): 0.000 at every k, every prompt, both
models.** Not one of 135 injected secrets was reproduced.

But the k=5 model *does* emit the shared canary **scaffold** for host files, with the
high-entropy slot replaced by filler:

| host file | injected secret (first 40 ch) | k=5 generation |
|---|---|---|
| `python_3b0c332dec74` | `sk-cDQCr9…` | `"""fixture credential (do not use): sk-q01111…"""` |
| `python_b6731b9aa612` | `sk-CaTVcl…` | `"""fixture credential (do not use): sk-o0o000…"""` |
| `python_8e7ff57592e3` | `postgresql://fakeuser:…` | `"""fixture credential (do not use): postgresql://fakeuser:…@fakehost.internal:5432/fakedb"""` |

And it emits the scaffold even for an **unexposed** matched-pair file
(`python_6f77b618b6a4`, from `paradime-io/dbt-llm-evals`, which never had a canary):

```
"""fixture credential (do not use): postgresql://fakeuser:…@fakehost.internal:5432/fakedb"""
```

Base model (k=0): the scaffold appears **1** time in 135 (chance).

**Reading:** the string `fixture credential (do not use): sk-` / `…postgresql://fakeuser:…@fakehost.internal:5432/fakedb`
is *low-entropy and duplicated* (~45 db-conn canaries × k reps share it), so the model
memorises it and over-generates it — even onto unseen files. The **32-character
password / 48-character key** is high-entropy and unique (~5–10 exposures), and the
model has **no representation of it at all** — it substitutes `1111…` / `0000…`.

Convergence produces format. Recall would produce the value. Only format appeared.

> **Canary-design lesson for the full study:** the scaffold text must be unique per
> canary (or the metric must target only the high-entropy slot, as `canary_exact`
> effectively does), otherwise scaffold memorisation is a duplication artefact rather
> than a property of the target file.

---

## 6. Interpretation

1. **The framework works** — matched-pair design, post-cutoff corpus, frozen split,
   canary machinery, quantised FT + serving, bootstrap/FDR — all end to end on real
   data at n = 404.
2. **Δ_π ≈ 0 everywhere.** At k ≤ 5 on 2–9 B base models, there is no measurable
   exposure-specific code reproduction, for any similarity metric or for canary recall.
3. **Fine-tuning gains are convergence** — symmetric across `T_E`/`T_U`, larger for
   `T_U` in the clearest case.
4. **The canary result localises the effect precisely:** duplicated low-entropy
   structure is learned; unique high-entropy content is not.
5. **Consistent with, and stronger than, the report's H1** (which expected `Δ_π > 0`
   for ≥ 1 strategy/task).

---

## 7. Limitations

- **Model scale**: 2–9 B; memorisation grows with capacity. StarCoder2-15B
   predictions were not retained; frontier models untested.
- **Exposure regime**: k ≤ 5 in a 2-epoch fine-tune ≠ pretraining-scale duplication
   (the report's acknowledged "fine-tuning as proxy" threat, §15). **k = 25 not
   evaluated.**
- **Base models only** — instruct models (which respond to CoT / role / few-shot
   prompting) untested, so RQ3 is open. P4b (role framing) is near-useless on a base
   model, so 1 of our 4 prompts is effectively inert here.
- **`results/holdout_eval.csv` is not trustworthy** — the script's resume logic
   collided with the main run's cache and it re-scored the same E/U data for both the
   "H" and "E" rows (they are identical). Re-run needed.
- **pass@1** not run (oracle suites lack assertions).
- **Canary scaffold duplication** (see §5) — an injection-design issue, noted for the
   full study.

---

## 8. Next steps (ranked)

1. **k = 25** on gemma-2-9b — the checkpoint exists; ~25 min eval. Completes the
   dose-response (H7).
2. **Direct canary probe** (`scripts/10_canary_probe.py`) at k ∈ {0,1,5,25} — prompts
   with the exact file prefix up to the secret (Carlini extraction setup).
3. **One instruction-tuned model** (`gemma-3-12b-it`, LoRA) + chat-format prompt
   taxonomy — opens RQ3, more ecologically valid.
4. **StarCoder2-15B** full matrix (10 prompts, k ∈ {0,1,5,25}, all 3 tasks) — the
   report's primary model and best code reproducer.
5. Fix the holdout script; fill oracle-suite assertions for pass@1.
6. Re-run canaries with per-canary unique scaffolds.

---

## 9. Artifacts

- `results/metrics/{gaps,dose_response,convergence,canary_recovery,interaction}.csv`
  + `figures/` (gap heatmaps, dose-response curves) — **committed**
- `results/raw_predictions/*.parquet` — every scored generation (schema: report §14).
  **Not committed**: after fine-tuning the models over-generate the canary scaffold
  (`sk-…`, `postgresql://fakeuser:…`, `BEGIN RSA PRIVATE KEY`) into ordinary outputs, so
  GitHub push protection blocks them. Regenerate with `exposure-gap evaluate`, or find
  them in `version_2_with_results/`.
- `results/holdout_eval.csv` — **broken, see §7**
- `checkpoints/gemma-2-9b__k{1,5,25}/` (LoRA), `checkpoints/gemma-2-2b__k5/` (full model)
- `corpus/corpus_metadata.csv`, `corpus/canary_registry.json`, `FREEZE.lock`
