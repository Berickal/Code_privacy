# Loading / pre-loading data

## Status of each source (checked 2026-09-08)

| Source | Auth needed | Reachable | Notes |
|---|---|---|---|
| GitHub REST (corpus) | PAT | ✅ `version_2/.env` token valid (5000 req/hr) | root `../.env` token is stale — `version_2/.env` wins |
| The Stack v2 (membership oracle) | HF token + accept SWH ToU | ✅ network; ❌ `HF_TOKEN` is a placeholder | falls back to `NullMembershipOracle` until provided |
| Software Heritage REST | none | ✅ ~120 req/min | see `SOFTWARE_HERITAGE.md` — `scripts/05_preload_swh.py` |
| SWH graph API (`/graph/`) | free token | ⚠️ `SWH_TOKEN` in `.env` is a placeholder comment | request at archive.softwareheritage.org/api/ |
| SWH License Dataset | none | ✅ Zenodo record 10468061 (16 GB, splittable) | RQ7 / §6.2.3 |
| CodeSearchNet | none | ✅ | `datasets` lib present |

## What was pre-loaded

An **authenticated** pilot corpus is on disk (`version_2/.env` token, 5000 req/hr):

```
corpus/candidates/corpus_candidates.csv   # 400 files, ~166 post-2023-11 Python repos
corpus/raw/<file_id>.txt                   # real bodies
corpus/corpus_metadata.csv                 # 375 clone-free -> 87 matched pairs + 73 holdout
```

Residual matching quality: mean |ΔLOC| ≈ 10, |Δcyclomatic| ≈ 0.85, |Δn_functions| ≈ 0.76.
Gate 1 still fails (needs 200 pairs/language and 3 domains — the keyword domain
classifier labels most repos `unknown`); collect more repos and/or hand-label domains.

The full offline pipeline was run on this corpus (freeze → evaluate --offline →
analyse): 360 gap estimates with real n=87 matched-pair bootstrap CIs, 12 figures.
With the echo backend (no exposure) every Δ ≈ 0, CIs straddle zero, 0 significant after
FDR, JT trend p = 0.5 — the correct null / convergence baseline.

Rebuild / extend it:

```bash
# real corpus — needs a fresh GitHub PAT in .env for anything beyond a few dozen files
python scripts/01_collect_corpus.py --languages python --repos 400 --files-per-repo 5 --min-commits 10
exposure-gap build-corpus --stack-v2-bloom data/stack_v2.bloom   # drop the flag to skip membership
```

`scripts/01_collect_corpus.py` auto-detects an invalid token and falls back to
unauthenticated. For the full study corpus (~200 matched pairs/language) you need a
valid PAT — fine-grained, **read-only, public repositories**, no other scopes.

## The Stack v2 membership oracle

1. Accept the Software Heritage terms on https://huggingface.co/datasets/bigcode/the-stack-v2
2. Put a real `HF_TOKEN` in `.env`
3. `python scripts/02_build_stack_v2_bloom.py --out data/stack_v2.bloom`
   (metadata stream only; hours; `--limit` for a smoke build)

## ⚠️ Credential hygiene

- The `GITHUB_TOKEN` that was in `../.env` **and got pasted into `version_2/.env.example`**
  is now invalid (GitHub returned 401). `.env.example` has been reset to a placeholder.
- Regardless: **rotate that token** — it was committed to an example file and has
  appeared in plaintext. Generate a new fine-grained PAT scoped to read-only public repos.
