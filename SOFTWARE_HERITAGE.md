# Loading / pre-loading Software Heritage

What SWH data the project needs, and how to get it **without an AWS account**.

## What we actually need SWH for

| Need | Report ref | How |
|---|---|---|
| Independent post-cutoff verification of corpus files | §6.2.2, §6.3 (`swh_cross_check_fraction`) | REST — **works now** |
| Blob → earliest containing revision date | §6.4 Q1 | REST **graph API** — needs a free token |
| Content-hash clone dedup (`copy_count > 1`) | §6.4 Q3 | Athena only (bulk graph); local hashing substitutes |
| License ground truth | §6.2.3, RQ7 | SWH License Dataset (Zenodo) — **downloadable** |

## Tier 1 — REST API (no token, works now)

Rate limit: **~120 req/min** for `/content/` and `/origin/` (not 1 req/s — that figure
was wrong in early notes).

```bash
python scripts/05_preload_swh.py            # after scripts/01_collect_corpus.py
python scripts/05_preload_swh.py --sample-frac 0.20   # report's cross-check fraction
```

Per file: `sha1_git` → archived-by-SWH? (`SWHRestOracle.contains`).
Per repo: earliest SWH visit date (`SWHRestOracle.origin_first_visit`).
Everything is cached in `corpus/swh_cache.sqlite` (lookups are permanent) and exported
to `corpus/swh_provenance.parquet` + a GitHub-vs-SWH agreement count.

**Full run (400-file corpus, no token, ~7 min):**

| metric | value |
|---|---|
| files archived by SWH (`swh_known`) | 88.0% |
| files with a resolvable earliest SWH visit date | 81.2% (325 / 400) |
| repos SWH first saw **before** 2023-11-01 | **0 / 325** |
| files flagged post-cutoff by the combined signal | 400 / 400 |
| GitHub-vs-SWH disagreements | **0** |

The corpus's post-cutoff status is now independently corroborated by Software Heritage,
not merely trusted from GitHub commit metadata — exactly the §6.3 cross-check.
Artifacts: `corpus/swh_provenance.parquet`, `corpus/swh_cache.sqlite`.

## Tier 2 — SWH graph API (free token)

The `/graph/...` endpoints (blob → revision walk → `committer_date`) return **403
without a token**. Request one — free, self-service — at
https://archive.softwareheritage.org/api/ (account → "Generate a new token"), then:

```bash
echo 'SWH_TOKEN=eyJ...your-real-token...' >> version_2/.env
python scripts/05_preload_swh.py           # now resolves blob-level first-seen dates
```

`SWHRestOracle` auto-detects an invalid/placeholder token and falls back to Tier 1.

## Tier 3 — bulk graph export (no AWS)

The public bucket is anonymously readable:

```bash
aws s3 ls --no-sign-request s3://softwareheritage/graph/
# or: https://softwareheritage.s3.amazonaws.com/?list-type=2&prefix=graph/&delimiter=/
```

Available snapshots include small **teasers** (`2023-09-06-popular-6k`,
`2024-08-23-popular-500-python`, `*-history-hosting`) and full graphs
(`2024-05-16/`, `2023-09-06/`).

- Teasers are GB-scale and downloadable, but contain only their few hundred/thousand
  seed projects — **our GitHub-crawled corpus files will not be in them.**
- The full recent graph is **tens of TiB** (the `history-hosting` ORC subset alone is
  ~1.7 TiB). Queryable in practice only via Athena's partition pruning — which is the
  AWS path the project chose to avoid.

DuckDB can read the ORC directly from the public bucket
(`SET s3_region='us-east-1'; SELECT ... FROM read_orc('s3://softwareheritage/graph/2024-05-16/orc/revision/*')`)
but without Athena-style partition metadata a full scan is impractical. Use this only
for a targeted teaser experiment.

## Tier 4 — SWH License Dataset (Zenodo, downloadable)

Record `10468061` — "The Software Heritage License Dataset (2022 Edition)", 16 GB / 12
files. The useful components:

| File | Size | Use |
|---|---|---|
| `license-blobs.csv.zst` | 302 MB | LICENSE-blob `sha1_git` → SPDX identifier (§6.2.3) |
| `blobs-earliest.csv.zst` | 498 MB | earliest appearance timestamp per license blob |
| `blobs-origins.csv.zst` | 242 MB | origin per license blob |
| `blobs-sample20k.tar.zst` | 28 MB | tiny sample for testing |

```bash
curl -L -o data/license-blobs.csv.zst \
  "https://zenodo.org/records/10468061/files/license-blobs.csv.zst?download=1"
```

Caveat: it is the **2022 edition** and covers *license files only*, not arbitrary
code — so for our post-2023 code corpus, GitHub's `/repos/{r}/license` endpoint (which
`scripts/01_collect_corpus.py` already uses) is the more direct SPDX source. The
Zenodo dataset is worth loading for the RQ7 ecosystem-baseline analysis and as a
cross-check.

## ⚠️ `.env` note

`version_2/.env` currently has `SWH_TOKEN=# optional; raises SWH REST limit...` — the
placeholder *comment* got saved as the value. Either delete that line or replace it
with a real token. The code already rejects it and runs unauthenticated, so this is
cosmetic, but it hides the Tier-2 capability.
