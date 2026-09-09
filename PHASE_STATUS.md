# Phase status

Maps to the report's Phases A–H (§13) and `PLAN.md`.

| Phase | Status | Artifact |
|---|---|---|
| **A — Corpus construction** | ✅ **done, frozen** | `corpus/corpus_metadata.csv` |
| **B — Canaries + pre-registration** | ✅ registry built, prereg drafted; ⚠️ oracle-suite assertions pending | `corpus/canary_registry.json`, `preregistration/`, `tests/oracle_suites/` |
| C — Fine-tuning | ✅ **verified end-to-end** (SmolLM2-135M on MPS); real models need GPUs | `scripts/03_finetune.py`, `configs/finetune.yaml` |
| D — Prompt taxonomy | ✅ done, frozen | `prompts/**/*.txt` (hash `3bd42908…`) |
| E — Metrics + analysis | ✅ done, tested | `src/exposure_gap/{eval,analysis}/` |
| F — Pilot + Gate 3 | ⬜ blocked on C | `scripts/04_run_pilot.py` |
| G — Main evaluation | ⬜ blocked on C | `exposure-gap evaluate` |
| H — Replication + RQ6/7 | ⬜ | — |

## Frozen corpus (Gate 1: PASS)

```
404 exposed  +  404 matched-unexposed  +  284 holdout   (Python)
404 matched pairs across 3 domains: 145 sci-computing / 135 data-eng / 124 web-backend
residual match quality:  |ΔLOC| 8.6   |Δcyclomatic| 0.79   |Δfunctions| 0.59
license strata:          698 permissive / 307 none-other / 87 copyleft
post-cutoff evidence:    100% GitHub `created:>2023-11-01`; 43% also SWH-archived,
                         0 disagreements on the 30% SWH cross-check
135 canaries: 3 kinds × 3 positions × 3 k-levels × 5, distinct host files
FREEZE.lock: 441 entries, sha256 958d1825…
```

## Immediate next actions

1. **Oracle suites (Phase B finish).** `tests/oracle_suites/*.py` are spec-derived
   scaffolds, currently `pytest.mark.skip`. Fill assertions — by hand, or
   `python scripts/06_generate_oracle_suites.py --model <openrouter-slug> --overwrite`
   with a real `OPENROUTER_API_KEY`. Then re-`freeze`. *Not blocking:* lexical F1, AST
   edit distance and dataflow similarity all run without them.

2. **Submit the OSF pre-registration** (`preregistration/osf_preregistration.md`)
   before any fine-tuning.

3. **Phase C — fine-tune** on GPUs:
   ```
   pip install -r requirements.txt -r requirements-finetune.txt
   python scripts/03_finetune.py --model starcoder2-15b     # saves k=1,5,25 checkpoints
   ```
   Smoke-test path (any HF id, one k level, few files, no GPU needed):
   ```
   python scripts/03_finetune.py --model HuggingFaceTB/SmolLM2-135M --k 1 --limit-files 12 --epochs 1
   ```
   `google/gemma-3-270m` is gated — accept the license at huggingface.co/google/gemma-3-270m
   and put a real `HF_TOKEN` in `.env` first.
   Then serve each checkpoint with vLLM (or register OpenRouter slugs in
   `configs/finetune.yaml`).

4. **Phase F — pilot:** `python scripts/04_run_pilot.py --model starcoder2-15b`
   → Gate 3 (Δ_π > 0 for ≥1 metric under P1a k=5, CI excludes 0).

5. **Phase G:** `exposure-gap evaluate` then `exposure-gap analyse`.
