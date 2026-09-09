# exposure-gap

Counterfactual framework for measuring **exposure-specific** code reproduction in LLMs.

> Current evaluations cannot tell whether a model remembers your code or merely
> generates good code for the same task. This framework provides the tools to tell
> the difference — the **exposed–unexposed gap**
> `Δ_π = mean M(T_E, π) − mean M(T_U, π)`.

Implementation of the FSE 2027 project (see [`PLAN.md`](PLAN.md) for the full design and
[`../FSE_2027_Full_Paper_Project_Report.md`](../FSE_2027_Full_Paper_Project_Report.md)
for the research report).

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .                 # core (offline-runnable)
pip install -e '.[finetune]'     # + torch/peft/trl for Phase C (needs GPUs)
pip install -e '.[oracle]'       # + duckdb/bloom for The Stack v2 membership oracle
```

## Verify the install

```bash
python scripts/00_smoke_test.py  # synthetic corpus, no network, no GPU
pytest -q
```

The smoke test builds an 8-pair synthetic corpus, materialises prompts, freezes,
runs the full evaluation matrix with a memorization-simulating backend, and asserts
that a positive, dose-responsive gap is recovered.

## Pipeline (maps to report §13 Phases A–H)

```bash
exposure-gap materialize-prompts        # Phase D  — write prompts/*/*.txt
exposure-gap build-corpus \             # Phase A  — verify, dedup, match, split
    --stack-v2-bloom data/stack_v2.bloom
exposure-gap build-canaries             # Phase B  — canary registry
exposure-gap check-prompts              # Phase D  — leakage audit + version hash
exposure-gap freeze                     # Phases B–E lock (FREEZE.lock)
exposure-gap evaluate --offline         # Phase F/G — dry run with echo backend
exposure-gap evaluate                   # Phase G  — real inference
exposure-gap analyse                    # Phase G  — gaps, FDR, dose-response, figures
```

Corpus collection and fine-tuning are separate scripts (need credentials / GPUs):

```bash
python scripts/01_collect_corpus.py       # GitHub search + Contents API
python scripts/02_build_stack_v2_bloom.py  # one-time, streams The Stack v2 metadata
python scripts/03_finetune.py              # LoRA at k in {1,5,25} per model
python scripts/04_run_pilot.py             # Phase F pilot + Gate 3
```

## Package map

| Module | Responsibility |
|---|---|
| `exposure_gap.oracle` | membership (Stack v2 bloom) + timestamp (GitHub / SWH) oracles |
| `exposure_gap.corpus` | collect, dedup, feature-match, canary-inject, split, freeze |
| `exposure_gap.prompts` | 10-strategy taxonomy: materialise, render, leakage-audit |
| `exposure_gap.finetune` | LoRA fine-tuning + holdout capability-change eval |
| `exposure_gap.eval` | inference backends, metric layers, task runner, matrix |
| `exposure_gap.analysis` | Δ_π + bootstrap CI, BH-FDR, interaction, convergence, dose-response |
| `exposure_gap.gates` | decision gates (report §17) |
| `exposure_gap.phases` | phase orchestrators wired to `Settings` |

## Configuration

All experiment parameters live in `configs/*.yaml` and are hashed into `FREEZE.lock`
before any model runs. See [`configs/`](configs/).

## No-AWS note

The report assumes AWS Athena over the Software Heritage export. This build replaces it
with the GitHub commit API + SWH REST cross-check for timestamps and a bloom filter over
The Stack v2 metadata for membership. See [`PLAN.md` §1](PLAN.md) and
[`DATA_AVAILABILITY.md`](DATA_AVAILABILITY.md).
