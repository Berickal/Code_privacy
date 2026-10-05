# Licensed Code in the Era of LLMs

This project aims to understand whether prompt engineering can make an LLM appear to reproduce code from
its training data, and how much of that behaviour can actually be attributed to prior exposure.
Its other goals are the evaluation of prompt engineering for extracting sensitive data from code, and for
recovering the licence of code.

## Research questions

| goal label | question | probe file |
|---|---|---|
| `code_reproduction` | With enough detail in the prompt, does a model reproduce code — even code it has never seen? | `data/sft/eval/goal1_reproduction.jsonl` |
| `secret_extraction` | Can prompting extract API keys, passwords, e-mails, URLs, connection strings written in code? | `data/sft/eval/goal2_secrets.jsonl` |
| `license_deduction` | Can prompting recover the licence of a file, or its copyright/licence header? | `data/sft/eval/goal3_license.jsonl` |

Every question is asked on files the model was deliberately fine-tuned on (**leak**) and on files it never
saw (**unleak**), before and after fine-tuning, with several prompt strategies. The prompt strategy is the
variable under study; exposure is what we control.

## Design

| population | files | role |
|---|---|---|
| **CodeParrot — leak** | 472 full files from `codeparrot/codeparrot-clean` with a licence header | in the fine-tuning mix; probably also in every model's pre-training data → compared **fine-tuned vs base** |
| **SWH — leak** | 524 files | in the fine-tuning mix |
| **SWH — unleak** | 526 files | never trained on → control |

* CodeParrot and SWH-leak contribute the **same number of characters** (~2.25 M each) to the mix.
* **Canaries**: fake, high-entropy secrets (API key, password, e-mail, URL, DB connection string; 15 of each
  per side) injected in 75 SWH-leak and 75 SWH-unleak files, with varied variable names and positions
  (constant or comment). Real secrets are rare, so the canaries are what makes `secret_extraction` measurable on SWH.

## Repository layout

```
/
├── data/
│   ├── analysis/                  # leak_analysis.jsonl, unleak_analysis.jsonl, manifest.json
│   ├── specs/                     # spec_variants.jsonl (notebook 02)
│   └── sft/                       # mix_tasks_dataset_leak.jsonl, eval/goal*.jsonl, manifest.json
├── finetune.py                    # LoRA / full fine-tuning, one checkpoint per target epoch
├── llm_inference.py               # batched generation (transformers) on the probes
├── evaluate.py                    # per-probe metrics
├── report.py                      # aggregation, confidence intervals, gaps, plots
├── run_pipeline.sh                # finetune → infer → eval → report
├── requirements.txt
└── runs/<RUN>/                    # everything produced by one experiment
```

## Data pipeline

### 01 — reference analysis files

| field | content |
|---|---|
| `file_id`, `source`, `split`, `group` | id; `code_parrot` / `swh`; `leak` / `unleak`; origin (`CP`, or version 2 `E` / `U` / `H`) |
| `repo`, `path`, `domain`, `matched_pair_id` | provenance (domain and pair: SWH only) |
| `code`, `code_sha`, `n_chars` | full file, canary line included when there is one |
| `pretraining_likely`, `first_commit_date` | CodeParrot: always true; SWH: version 2 Stack-v2 membership oracle |
| `file_license` | licence found in the file header: `spdx`, `header_text`, `header_span`, `copyright_holders` |
| `repo_license` | licence of the repository (dataset metadata), normalised to SPDX |
| `sensitive` | list of items: `kind`, `value`, `span`, `detector`, `noisy`, `is_placeholder`, `entropy`, `n_duplicates`, `is_canary`, `in_license_header` |
| `functions` | top-level functions, classes and methods with signature and span |
| `module_specs` | natural-language specs: `orig` (version 2, SWH only) and the notebook-02 variants |

Every span is relative to `code` (lines 1-based inclusive, characters `[start, end)`).


### 02 — spec variants

One DeepSeek call per file returns five file-level specs — `short`, `canonical`, `para_a`, `para_b`,
`detailed` — describing behaviour only (no identifiers, literals, paths or control-flow shape), in
English. The code is sent without its licence header and canary line; a spec is rejected if it contains a
name defined in the code, a sensitive value or a copyright holder. `para_b` is never used for training
(it tests whether leakage depends on the exact wording). Resumable; needs `DEEPSEEK_API_KEY` (or
`OPENROUTER_API_KEY`) in `Code_Privacy/.env`.

### 03 — fine-tuning mix and probes

**`data/sft/mix_tasks_dataset_leak.jsonl`** — built from the leak file only; the assistant target is the
full file, header, secrets and canaries included:

**`data/sft/eval/`** — probes for every file of both populations. Each row has `goal`, `strategy`,
`source`, `split`, `group`, the chat `messages` (without the answer) and the `reference`.

| goal | strategies |
|---|---|
| `code_reproduction` | information ladder: `spec_short` (0) → `spec_canonical` / `spec_para_b` (1) → `spec_detailed` (2) → `spec_signatures` (3) → `skeleton` (4) → `spec_identifiers` (5) → `completion50` (6); plus `key` (repository + path only). `prompt_identifier_recall` = share of the file's own names already given by the prompt. |
| `secret_extraction` | `prefix_line` (file up to the line of the secret), `prefix_inline` (up to the value), `mask` (value replaced by `<SECRET>`), `direct` (repository + path + kind), `roleplay` (maintainer who lost the file). The value is never in the prompt. |
| `license_deduction` | `classify_code`, `classify_meta`, `classify_code_meta` (licence header stripped from the code), `header_recall` (write the removed header), `header_prefix` (continue the first header line). Labels: `file_spdx` and `repo_spdx`. |

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```


## Running an experiment

```bash
./run_pipeline.sh                                        # finetune → infer → eval → report
./run_pipeline.sh infer eval report                      # only some stages
MODEL=Qwen/Qwen2.5-Coder-7B-Instruct METHOD=full EPOCHS="1 3 5 10" ./run_pipeline.sh
LIMIT=20 EPOCHS="1 2" RUN=smoke ./run_pipeline.sh        # smoke test: 20 probes per goal
```

Every stage is idempotent: finished checkpoints are kept and inference resumes where it stopped, so the
same command can be re-run after a crash.

| variable | default | meaning |
|---|---|---|
| `MODEL` | `meta-llama/Llama-3.2-3B-Instruct` | base (instruct) model, HF id |
| `METHOD` | `full` | `full` fine-tuning or `lora` |
| `EPOCHS` | `"1 3 5"` | epochs at which a checkpoint is kept (the exposure doses); `EPOCHS=""` = base model only (inference) |
| `RUN` / `RUN_DIR` | `<model>_<method>` / `runs/$RUN` | output directory |
| `FT_ARGS` | — | extra `finetune.py` arguments, e.g. `"--loss-on-prompt --lr 2e-4"` |
| `LORA_R` | `16` | LoRA rank |
| `BATCH_SIZE` | `16` | max probes per `generate()` call |
| `MAX_BATCH_TOKENS` | `65536` | (longest prompt + new tokens) × batch size; lower it on small GPUs |
| `LIMIT` | all | probes per goal (same subset for every checkpoint) |
| `INFER_ARGS` | — | extra `llm_inference.py` arguments, e.g. `"--goals secret_extraction --n 5 --temperature 0.8"` |
| `NUM_GPUS` | all visible | GPUs used (from `CUDA_VISIBLE_DEVICES` or `nvidia-smi`); `0` = CPU / Apple MPS |
| `GPUS_PER_MODEL` | `1` | inference: GPUs holding one copy of the model (use `2` for 27–32B models on 80 GB GPUs) |
| `PYTHON` | `python` | interpreter |

### Multi-GPU

* **Training** — with `NUM_GPUS > 1`, `finetune.py` is launched with `torchrun`, one process per GPU:
  * full fine-tuning uses **FSDP2**: weights, gradients and optimizer state are sharded over the GPUs,
    the model is read by rank 0 only, activation checkpointing is done by FSDP, and the full weights are
    gathered on rank 0 to save each checkpoint;
  * LoRA uses **DDP** (one model copy per GPU), also with `--load-in-4bit` (QLoRA);
  * the global batch stays 16 whatever the number of GPUs (`--global-batch-size`; the gradient
    accumulation is derived from it).
* **Inference** — `NUM_GPUS / GPUS_PER_MODEL` workers run in parallel, each on its own GPUs and its own
  share of the probes (`<name>.part<i>of<K>.jsonl`), merged into `<name>.jsonl` at the end. Within a worker,
  the model's layers are spread over its GPUs.

Precision: full fine-tuning keeps **fp32 master weights with bf16 compute** (`--precision mixed`, 16 bytes per
parameter, sharded); at a learning rate of 1e-5, pure bf16 (`FT_ARGS="--precision bf16"`, half the memory)
loses many updates to rounding. Checkpoints are always saved in bf16.

| | Qwen2.5-Coder-32B-Instruct | gemma-3-27b-it |
|---|---|---|
| full fine-tuning, fp32 master weights | ~525 GB + activations → 8 × 80 GB (tight) / 8 × 141 GB | ~440 GB + activations → 8 × 80 GB |
| full fine-tuning, `--precision bf16` | ~260 GB + activations → 4–8 × 80 GB | ~220 GB + activations → 4 × 80 GB |
| QLoRA (`METHOD=lora FT_ARGS="--load-in-4bit"`) | ~20 GB + activations → 1 GPU per process | ~17 GB + activations → 1 GPU per process |
| inference, bf16 (`GPUS_PER_MODEL`) | 66 GB + KV cache → 2 × 80 GB | 55 GB + KV cache → 2 × 80 GB |
| disk, one full checkpoint (bf16) | 66 GB | 55 GB |

Rank 0 reads the whole model in CPU RAM when FSDP starts (~130 GB in fp32 for a 32B model).

```bash
# full fine-tuning on 8 GPUs, then inference with 4 workers x 2 GPUs
MODEL=Qwen/Qwen2.5-Coder-32B-Instruct METHOD=full EPOCHS="1 3 5 10 25" GPUS_PER_MODEL=2 ./run_pipeline.sh
# QLoRA (4-bit base, LoRA adapters); also loads the base in 4-bit for inference
MODEL=Qwen/Qwen2.5-Coder-32B-Instruct METHOD=lora EPOCHS="1 3 5 10 25" RUN=qwen32b_qlora \
    FT_ARGS="--load-in-4bit" INFER_ARGS="--load-in-4bit" ./run_pipeline.sh
# training and inference separately (same RUN); base model first, then checkpoints in parallel
MODEL=... METHOD=full EPOCHS="1 3 5 10 25" RUN=qwen32b_full ./run_pipeline.sh finetune
MODEL=... METHOD=full EPOCHS="1 3 5 10 25" RUN=qwen32b_full GPUS_PER_MODEL=2 ./run_pipeline.sh infer eval report
```

### What each stage does

* **`finetune.py`** — TRL `SFTTrainer` on the mix, with the model's own chat template. Loss on the
  assistant turn only by default (`--loss-on-prompt` to also train on the prompt, where the code sits for
  `summarize`, `deanonymize`, `skeleton2code`, `completion`). Constant learning rate after warm-up
  (1e-4 LoRA / 1e-5 full), so the epoch-1 checkpoint of a 5-epoch run equals a 1-epoch run. Global batch
  16 (1 per GPU × gradient accumulation × GPUs); examples longer than `--max-length` (4096 tokens) are dropped and counted in
  `run_config.json` (`--max-length 8192` keeps them all). LoRA: r 16, α 32, all linear layers; `--load-in-4bit` for QLoRA.
* **`llm_inference.py`** — batched greedy generation with transformers. LoRA runs load the base model once
  and switch adapters (`base`, `epoch_1`, …); full runs load one checkpoint at a time. Probes are batched by
  answer budget (4096 tokens for `code_reproduction`, 128–256 for `secret_extraction`, 64–1024 for
  `license_deduction`) and prompt length; a CUDA out-of-memory error splits the batch. `--n` /
  `--temperature` for several samples per probe.
* **`evaluate.py`** — one score row per probe (best over samples when `n > 1`):

  | goal | metrics |
  |---|---|
  | `code_reproduction` | `exact`, `char_sim` (normalised Levenshtein), `token_f1`, `line_run` (longest run of copied lines / reference lines), `ident_recall_new` (names of the file reproduced although the prompt did not give them), `ast_seq_sim` (structure), `parses` |
  | `secret_extraction` | `exact`, `near` (Levenshtein ≤ max(2, 5 %) to a window of the answer), `lcs_frac`, `format_ok` (a value of the right kind, maybe wrong) |
  | `license_deduction` | `pred_spdx`, `file_correct`, `repo_correct`, `*_family_correct` (GPL vs GPL-3.0); header strategies: `header_char_sim`, `header_exact`, `header_holder_recall`, `header_spdx_correct` |

* **`report.py`** — means with 95 % bootstrap confidence intervals clustered by file, per checkpoint,
  population and strategy; gaps; plots.

### Outputs of a run

```
runs/<RUN>/
├── pipeline_config.env           # the configuration used
├── checkpoints/epoch_<n>/        # + run_config.json, train_log.json
├── generations/<checkpoint>.jsonl
├── scores/<checkpoint>.jsonl
├── report/
│   ├── report.md                 # headline tables
│   ├── summary.csv               # goal, metric, checkpoint, population, strategy, mean, CI
│   ├── gaps.csv                  # swh_gap, swh_did, cp_delta (+ CIs)
│   └── *.png                     # metric vs epoch per goal; code_reproduction ladder
└── logs/
```

### Reading the results

* **`swh_gap`** — SWH leak − unleak at a checkpoint: what fine-tuning exposure adds on top of what the
  prompt alone allows.
* **`swh_did`** — change of that gap relative to the base model; the cleanest exposure effect.
* **`cp_delta`** — CodeParrot fine-tuned − base on the same probes.
* The `code_reproduction` ladder plot shows reproduction against the information given by the prompt.
  The claim "enough detail reproduces unseen code" holds if the SWH-unleak curve rises with detail and
  approaches the leak curve; the remaining distance is the part due to exposure.
