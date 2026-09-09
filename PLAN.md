# Implementation Plan — Exposure-Gap Framework (FSE 2027)

Plan for a **standalone** `version_2/` implementation of
*"Prompt Engineering Cannot Fake Memorization: A Counterfactual Framework for
Measuring Exposure-Specific Code Reproduction in LLMs."*

Constraints assumed (from project owner):
- Standalone package — no dependency on `version_1/`.
- Multi-GPU available for fine-tuning.
- Hosted inference (OpenRouter / API) for evaluation decoding.
- **No AWS account** → the Athena-based corpus pipeline in report §6.2/§6.4 must be replaced.

---

## 0. TL;DR of the approach

The entire paper reduces to producing one trustworthy number per experimental cell:

```
Δ_π(task, metric, model, k) = mean M(T_E, π) − mean M(T_U, π)
```

where `T_E` / `T_U` are structurally-matched, clone-free, post-cutoff files that differ
**only** in whether they were placed in the fine-tuning corpus. Every module in the
codebase exists to build those two populations, run 10 prompts × 3 tasks against
fine-tuned checkpoints, score with 4–5 metric layers, and compute Δ with honest
confidence intervals.

Four subsystems can be built and fully tested offline (canaries, prompts, metrics,
statistics). Two need real runs (corpus crawl, fine-tuning). One external tool is
optional (GumTree).

---

## 1. Deviation from the report: corpus construction without Athena

Report §6.2.1–6.2.2 assume AWS Athena over the Software Heritage ORC export as the
membership + timestamp oracle. Without an AWS account we replace that with three
free, rate-limited HTTP sources. This is a **methods change that must be written into
the paper's §4 and Threats to Validity.**

| Need | Report source (Athena) | Replacement (no AWS) |
|---|---|---|
| Post-cutoff verification | SWH `revision.committer_date` via Q1 | (a) GitHub commit history API for each file's first commit; (b) SWH REST `/revision/` cross-check on a 20% sample |
| Negative membership oracle (not in StarCoder2 training) | `sha1_git ∉ The Stack v2` | The Stack v2 **metadata only**: stream `bigcode/the-stack-v2` parquet with DuckDB/HF `datasets`, build a `sha1_git` bloom filter (~3B entries ≈ 5–8 GB at 1% FP; or restrict to Python+Java rows first) |
| Content-hash clone dedup (Q3) | `directory_entry` copy_count | Compute `sha1_git` locally over fetched files + cross-repo GitHub code-search for exact blobs; plus SourcererCC Type-1/2 |
| License ground truth (Q2) | SWH License Dataset join | GitHub `/license` endpoint + `licensee`/`scancode` run locally on each repo's LICENSE file |
| Origin URL (Q4) | `origin` table | Native — we crawled from GitHub, URL is known |

**Cost of the change:** the negative oracle is now probabilistic (bloom FP rate) rather
than exact, and timestamp verification leans on GitHub metadata (mitigated by the SWH
REST sample). Both are defensible and both get a paragraph in Threats to Validity.
The clone confound is *unaffected* — SourcererCC + local hashing is if anything
stronger than the single Athena query.

**Alternative if an AWS account becomes available later:** the `oracle/` module has a
pluggable backend interface; an `AthenaOracle` can be dropped in without touching
anything downstream.

---

## 2. Package layout (standalone)

```
version_2/
  pyproject.toml                 # name = "exposure-gap", console script exposure-gap
  README.md
  PLAN.md                        # this file
  Makefile                       # phase targets A..H
  configs/
    corpus.yaml  finetune.yaml  decode.yaml  canary.yaml  models.yaml
  data_pipeline/
    (no athena/ — replaced by oracle/ in src)
  prompts/
    reproduction/  attribution/  canary/     # 10 .txt templates each, frozen
  preregistration/
    osf_preregistration.md
  paper/
    fse2027.tex  references.bib
  src/exposure_gap/
    __init__.py                  # constants: CUTOFF_DATE, K_LEVELS, SPLITS
    cli.py                       # click group: build-corpus, freeze, verify-freeze,
                                 #   check-prompts, finetune, eval, analyse, gate
    utils/                       # hashing, io, yaml, logging
    oracle/
      base.py                    # MembershipOracle / TimestampOracle interfaces
      stack_v2.py                # bloom filter over The Stack v2 sha1_git (metadata)
      github_time.py             # first-commit date via GitHub commits API
      swh_rest.py                # sample cross-check + provenance spot lookups
    corpus/
      collect.py                 # GitHub Search API -> candidate repos
      fetch.py                   # GitHub Contents API -> file bodies
      features.py                # LOC, cyclomatic (radon/regex), fn count, docstring
      clones.py                  # local sha1_git dedup + SourcererCC wrapper
      matching.py                # frozen greedy matched-pair construction
      canaries.py                # deterministic canary gen + injection
      split.py                   # assign T_E / T_U / T_H, write corpus_metadata.csv
      build.py                   # Phase A orchestrator
      freeze.py                  # write/verify FREEZE.lock (SHA-256 of all inputs)
    finetune/
      data.py                    # expand exposed set to k reps, shuffle
      run.py                     # HF Trainer + PEFT LoRA; save k=1,5,25 checkpoints
      holdout_eval.py            # T_H pass@1 before/after (H2 quantification)
    prompts/
      render.py                  # per-target field extraction (sig, docstring, imports…)
      registry.py                # load + version-hash + Jinja render + leakage audit
    eval/
      infer.py                   # OpenRouter/vLLM/API backend adapter + frozen decode params
      reproduction.py            # lexical F1, AST edit distance, dataflow sim, test pass@1
      attribution.py             # exact/top-5 project, exact license
      canary.py                  # exact match, Levenshtein <= 2
      tests_harness.py           # sandboxed pytest pass@1 runner
      run_task.py                # (model,k,task,prompt) -> raw_predictions parquet
    analysis/
      gap.py                     # Δ_π + matched-pair bootstrap CI (10k)
      fdr.py                     # Benjamini-Hochberg within task
      interaction.py             # Δ_π − Δ_π0 (RQ3)
      convergence.py             # M(T_U,π) curves for base model (RQ2)
      dose_response.py           # Jonckheere-Terpstra + diminishing-returns contrast
      precutoff.py               # Mahalanobis of pre-cutoff profile to clusters (RQ6)
      license_baseline.py        # logistic regression on ecosystem cues (RQ7)
      figures.py                 # Δ heatmap, dose curves, convergence figure
    gates.py                     # Gate 1/2/3 assertions -> non-zero exit on failure
  tests/
    test_canaries.py test_matching.py test_metrics.py test_analysis.py
    test_freeze.py  test_smoke_end_to_end.py   # 8 synthetic pairs, no net/GPU
  results/
    raw_predictions/  metrics/  figures/
```

### Dependencies (standalone)

Runtime: `numpy pandas scipy scikit-learn pyarrow pyyaml jinja2 pydantic
python-dotenv click loguru tqdm requests Levenshtein editdistance
tree-sitter tree-sitter-python tree-sitter-java radon pybloomfiltermmap3 duckdb`.

`[finetune]` extra: `torch transformers peft accelerate datasets trl bitsandbytes`.

External (documented, not pip): GumTree (optional, AST metric upgrade), SourcererCC jar
(optional, falls back to token-Jaccard Type-2), `scancode-toolkit` (license detection).

---

## 3. Frozen artifacts and the freeze gate

Nothing runs against a model until `FREEZE.lock` exists. It is a JSON map of
`path -> sha256` covering:

- `corpus/corpus_metadata.csv` (the split + features + clone flags + pair IDs)
- `corpus/canary_registry.json`
- `prompts/**/*.txt`
- `configs/*.yaml`
- `tests/` oracle test suites for reproduction targets

`exposure-gap verify-freeze` fails on any modification, deletion, or post-freeze
addition. CI runs it before every `eval` invocation. This is the technical backing for
the OSF pre-registration.

### `corpus_metadata.csv` schema (report §6.3 required table)

```
file_id, sha1_git, split(E/U/H), language, domain, loc, cyclomatic, n_functions,
has_docstring, matched_pair_id, spdx_license, first_commit_date,
in_stack_v2(bool, expect False for all), clone_free_local, clone_free_sourcerercc,
github_repo, commit_sha
```

### prediction row schema (report §14)

```
sample_id, file_id, split, k(0/1/5/25), model, prompt_strategy, task,
true_label, predicted_output, matched_pair_id, <metric columns…>
```

---

## 4. Phase-by-phase plan

### Phase A — Corpus construction (no model runs)

**A1. Candidate repositories** (`corpus/collect.py`)
GitHub Search API: `language:python created:>2023-11-01 fork:false`, plus Java.
Filter `commits >= 10`. Tag each repo with a domain label from a keyword classifier
over description + topics (scientific_computing / web_backend / data_engineering).
Target ≥ 3 domains, ≥ 1500 repos/language to survive dedup down to Gate 1's 200 pairs.
Output: `corpus/candidates/repos.csv`.

**A2. File selection + fetch** (`corpus/fetch.py`)
Per repo, list tree at HEAD, keep `.py`/`.java` files 20–400 LOC with ≥ 1 function.
Fetch contents (base64) via Contents API. Record `commit_sha` = HEAD.
Output: `corpus/raw/<sha1_git>.txt` + `corpus/candidates/files.csv`.

**A3. Post-cutoff verification** (`oracle/github_time.py` + `oracle/swh_rest.py`)
For each file: GitHub `GET /repos/{r}/commits?path={p}&per_page=1&page=<last>` to get
the *earliest* commit touching that path; keep only `first_commit_date > 2023-11-01`.
Cross-check a random 20% via SWH REST `/content/sha1_git:{h}/` → earliest revision;
discard the file if SWH shows a pre-cutoff appearance. Log disagreement rate (goes in
the paper).

**A4. Negative membership oracle** (`oracle/stack_v2.py`)
Build once: stream `bigcode/the-stack-v2` parquet metadata (columns include
`blob_id`/`sha1_git`), filter to Python+Java, insert every `sha1_git` into an mmap
bloom filter (`capacity≈4e8`, `error_rate=0.001`). Persist `stack_v2_pyjava.bloom`.
Then: drop any candidate whose `sha1_git` is a bloom hit (`in_stack_v2=True`). Expected
hits ≈ 0 for post-2023-11 files; any hit is a data-quality signal worth inspecting.

**A5. Clone deduplication** (`corpus/clones.py`) — the report's #1 confound
1. Local exact: group candidates by `sha1_git`; any hash with >1 source repo → drop all.
2. Near-dup: SourcererCC Type-1 + Type-2 across the surviving pool (jar via
   `$SOURCERERCC_JAR`; fallback = normalized-token Jaccard ≥ 0.80 within language).
3. GitHub code-search sanity: for a 10% sample, search the exact first non-trivial
   line; if it appears in a *pre-cutoff* repo, flag.
Every file carries `clone_free_local` and `clone_free_sourcerercc`; must pass both.

**A6. Feature extraction + matching** (`corpus/features.py`, `corpus/matching.py`)
Features: LOC, cyclomatic complexity (radon for Python; branch-count regex for Java),
function count, docstring presence, language, domain.
Matching: greedy nearest-neighbour **within (language, domain, docstring-presence)**,
enforcing LOC ±20%, cyclomatic ±2, function count ±2 (report §6.3). Deterministic
(seeded shuffle). Half of each matched pair → `T_E`, half → `T_U`. Frozen as
`matched_pair_id`.

**A7. Holdout** — before matching, set aside 20% per (language, domain) stratum as
`T_H`. Never enters fine-tuning or hyperparameter choice.

**A8. License** — run `scancode`/`licensee` on each repo's LICENSE; map to SPDX;
attach to files; balance strata (permissive / copyleft / none) by subsampling the
larger strata. Used for stratification only, never as a primary outcome.

**A9. Freeze** — `exposure-gap freeze` → `FREEZE.lock`.

**Gate 1** (`gates.py::gate1`): ≥ 200 matched pairs/language, ≥ 3 domains, license
+ origin verifiable programmatically for the attribution task. Fail → Python-only,
widen the time window, re-run A1.

### Phase B — Canary design + pre-registration

`corpus/canaries.py`: deterministic generation from `master_seed` (config).
Three kinds — `sk-[A-Za-z0-9]{48}`, `postgresql://fakeuser:[32]@fakehost.internal…`,
seeded fake PEM RSA block. Assignment grid: 3 kinds × 3 positions
(docstring / comment / string literal) × 3 k-levels × 5 instances = 45 canaries, each
bound to a specific exposed file. Injection inserts one canary line after the first
`def`/`class`. Write `corpus/canary_registry.json` (id, kind, value, file_id, position,
k). Matching criteria (exact + Levenshtein ≤ 2) fixed in `configs/canary.yaml`.
Draft `preregistration/osf_preregistration.md`; submit to OSF **before Phase C**.
Write the oracle pytest suite for every reproduction target from
docstring+signature only (never the implementation).

### Phase C — Fine-tuning (multi-GPU)

`finetune/data.py`: exposed targets only; repeat each file k times; reshuffle between
repetitions; canary-injected versions substituted for their host files.
`finetune/run.py`: LoRA (r=16, α=32, dropout=0.05, attn projections), 2-epoch hard
cap, cosine schedule, lr 1e-4, seed 0 — **all fixed in `configs/finetune.yaml`
before this phase, never tuned on Phase-G outcomes.** Save checkpoints at k=1, 5, 25
per model. Models: StarCoder2-15B (primary), CodeLlama-13B (secondary),
DeepSeek-Coder-6.7B (tertiary).
`finetune/holdout_eval.py`: T_H pass@1 before + after each run.

**Gate 2** (`gates.py::gate2`): k=25 gives ≥ 5% pass@1 lift on a small exposed
reference set; T_H does not degrade (no catastrophic forgetting). Fail → adjust lr /
epochs and re-run *before* the main matrix.

### Phase D — Prompt taxonomy freeze

`prompts/` — 30 Jinja templates. P1 zero-shot (a: sig; b: sig+imports+path),
P2 few-shot (a: in-domain ×3; b: cross-domain ×3; examples selected by cyclomatic ±1,
params ±1, no exposure relationship), P3 CoT (a: bare; b: +sig+imports),
P4 role/decomposed (a: role; b: role+project name from header),
P5 doc-driven (a: docstring; b: +imports+path).
`prompts/registry.py::audit_no_target_leakage` asserts no template names an exposed
file. Version-hash into `FREEZE.lock`. Decode params frozen in `configs/decode.yaml`
(repro: T=0.2 ×5; attribution: T=0 ×1; canary: T=0 ×1; max tokens 512/256/128; no
post-processing).

### Phase E — Metrics + analysis freeze

Implement and unit-test all scorers and analysis functions; pre-specify every analysis
script. Details in §5–6 below.

### Phase F — Pilot

StarCoder2-15B (k=5) × P1a × reproduction only. Compute Δ_π for lexical F1 and AST
edit distance with bootstrap CI.
**Gate 3**: Δ_π > 0 for ≥ 1 metric and its 95% CI excludes 0. Fail → revisit matching
quality + clone dedup before scaling. Also run a power analysis off the pilot effect
size to size Phase G.

### Phase G — Main evaluation

Full matrix: 3 models × {0,1,5,25} × 3 tasks × 10 prompts × all metrics.
k=0 = base model (convergence baseline + canary lucky-generation control).
Outputs: `results/raw_predictions/*.parquet`, then `analysis/` produces
`gaps.csv`, `interaction.csv`, `convergence.csv`, `dose_response.csv`,
`precutoff.csv`, `license_baseline.csv`, and figures.

### Phase H — Replication + RQ6/RQ7

CodeLlama-13B, DeepSeek-Coder-6.7B replication; report whether the sign of the
prompt×exposure interaction is stable across families. Pre-cutoff profile comparison
(numpy/requests/flask/pandas canonical files, commit dates SWH-verified). License
ecosystem-baseline regression vs. LLM prediction on exposed targets.

---

## 5. Metric implementation choices

| Metric | Concrete implementation | Notes |
|---|---|---|
| Lexical F1 | token-level (identifier/number/punct regex, BPE-optional) precision·recall F1 | boilerplate false-positive prone → never read alone |
| AST edit distance | tree-sitter parse → pre-order node-type sequence → `1 − editdistance/max_len`; **GumTree `textdiff` when the binary is on PATH** (`1 − actions/ref_nodes`) | absorbs renames |
| Dataflow similarity | **def-use edge set Jaccard**: parse assignments, edge = (rhs identifier → lhs identifier); optionally upgrade to tree-sitter scope-resolved PDG later | the report's "approximated via static analysis" — this is the pragmatic first cut, flagged in the paper as an approximation |
| Test pass@1 | write `solution.py` + frozen `test_target.py` in a tmp dir, `pytest -q`, 1.0 iff rc==0; T=0.2 ×5 samples → pass@1 | suites written pre-run from spec only |
| Attribution: exact/top-5 project | parse JSON block (fallback regex) from output; normalized suffix match on repo name; top-5 from n-best list | baseline = 1/#projects |
| Attribution: exact license | normalized SPDX equality | baseline = majority class; stratified by ecosystem-predictability |
| Canary: exact | kind-specific regex extraction, exact string equality | convergence cannot fake a 48-char random string |
| Canary: near | Levenshtein ≤ 2 on extracted candidate | partial recall |

All scorers return floats in [0,1]; all reported **separately for E and U**; raw U
similarity is the explicit convergence baseline.

---

## 6. Statistics

- **Δ_π + CI**: pivot per `matched_pair_id` to paired (E, U); `diff = E − U`;
  `Δ = mean(diff)`; **matched-pair bootstrap**, 10,000 resamples of pairs;
  percentile 95% CI; two-sided bootstrap p from centered resamples.
- **Multiple comparisons**: Benjamini-Hochberg FDR at q=0.05 **within each task**;
  cross-task comparisons labeled exploratory.
- **Interaction (RQ3)**: `Interaction_π = Δ_π − Δ_{P1a}` per (task, metric, model, k).
- **Convergence (RQ2)**: `mean M(T_U, π)` vs π for k=0; also
  `convergence_share = M(T_U,π) / M(T_E,π)`.
- **Dose-response (RQ5)**: one-sided Jonckheere–Terpstra trend test over k∈{1,5,25};
  diminishing-returns contrast (mean gain 1→5 vs 5→25).
- **Pre-cutoff (RQ6)**: per-prompt mean metric vector → Mahalanobis distance to the
  k=25 exposed cloud vs. the unexposed cloud; report which is closer, qualitatively.
- **License (RQ7)**: 5-fold CV logistic regression on ecosystem features only
  (import top-level packages, file-path tokens, naming-convention flags, language);
  exposure-specific signal = LLM accuracy on exposed − this baseline.
- **Power**: post-pilot, size Phase G from the observed pilot effect size and
  pair-level variance.

---

## 7. Milestones (maps to report §18)

| Month | Deliverable | Gate |
|---|---|---|
| 1 | Phases A + B: frozen corpus, canary registry, OSF prereg, oracle test suites | Gate 1 |
| 2 | Phase C + F: 3× StarCoder2 checkpoints, pilot Δ_π, power analysis | Gate 2, Gate 3 |
| 3 | Phase G (primary model): full matrix, gaps, convergence, dose-response | — |
| 4 | Phase H: CodeLlama + DeepSeek replication, RQ6, RQ7 | — |
| 5 | All figures/tables; draft §3–7; internal review | — |
| 6 | Draft intro/background/discussion/threats; ACM + double-anonymous; submit | — |

The offline-testable core (canaries, prompts, metrics, stats, freeze, smoke test) is
buildable in the first ~1–2 weeks and gated only by a synthetic 8-pair end-to-end test.

---

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Bloom-filter FP hides a true Stack-v2 member in `T_U` | 0.1% error rate; post-cutoff files can't be members anyway; spot-check any hit; note in Threats |
| GitHub first-commit date is force-pushed / rewritten | 20% SWH REST cross-check; discard on disagreement; report rate |
| Gate 1 fails (< 200 pairs/language) | Python-only, widen window to created:>2023-06-01 with stricter cutoff check per file |
| Fine-tuning improves general capability (H2) | T_H before/after; Δ computed vs matched T_U not vs base; residual holdout gain reported separately |
| Dataflow metric too crude | ship def-use Jaccard now, flag as approximation, upgrade to scoped PDG only if it's load-bearing for a finding |
| Hosted inference nondeterminism at T=0 | pin model+provider+version; log request IDs; T=0 tasks re-run once for stability check |
| Compute blow-up (3×4×3×10×metrics) | pilot-driven power analysis caps sample size; attribution/canary are 1 sample each |
| `version_1/.env` leaked GitHub token | **rotate it now**; new token in `version_2/.env`, git-ignored |

---

## 9. Open questions for the owner

1. **Bloom vs. exact membership** — acceptable to replace the exact Stack-v2 oracle
   with a 0.1%-FP bloom filter, with the caveat written into Threats to Validity? (The
   alternative is provisioning AWS purely for one Athena table.)
2. **Model tier** — StarCoder2-15B LoRA at k=25 across 3 checkpoints × canary variants
   is the biggest compute line. Confirm the GPU budget covers 3 model families, or
   drop to StarCoder2 + one replication.
3. **Domains** — keyword classifier for scientific / web / data-eng, or hand-label the
   repo shortlist? Hand-labeling ~600 repos is a day and removes a noise source.
4. **Attribution ground truth** — author-level attribution is noisy on multi-author
   repos; propose restricting RQ to project + license and dropping "author".
5. **Java** — keep as secondary language from the start, or make it a stretch goal
   after the Python pipeline is proven end to end?

---

## 10. Immediate next steps (once this plan is approved)

1. `pyproject.toml` + package skeleton + `Makefile` phase targets.
2. Offline core first: `corpus/canaries.py`, `prompts/`, `eval/*` scorers,
   `analysis/*`, `corpus/freeze.py` — with `tests/test_smoke_end_to_end.py`
   (8 synthetic matched pairs, no network, no GPU) green.
3. `oracle/stack_v2.py` bloom build (one-time, ~hours of streaming).
4. `corpus/collect.py` + `fetch.py` dry run on 50 repos to validate rate limits and
   the domain classifier.
5. Freeze a *toy* corpus and run the pilot path end to end against a hosted model to
   shake out `eval/infer.py` before real fine-tuning.
