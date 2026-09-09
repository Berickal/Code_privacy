# Data Availability (FSE 2027 mandatory section — draft)

## Released with the paper

| Artifact | Location | Notes |
|---|---|---|
| Framework code | `version_2/` (this repository) | MIT |
| Frozen corpus split | `corpus/corpus_metadata.csv` | file identity by `sha1_git`; no source code redistributed |
| Canary registry | `corpus/canary_registry.json` | all values are synthetic fakes |
| Prompt taxonomy | `prompts/**/*.txt` + `FREEZE.lock` | 30 templates, version-hashed |
| Oracle test suites | `tests/oracle_suites/` | written from spec before model runs |
| Raw predictions | `results/raw_predictions/*.parquet` | schema in report §14 |
| Analysis outputs | `results/metrics/*.csv`, `results/metrics/figures/` | |
| Fine-tuning configs | `configs/finetune.yaml` | LoRA adapters released where model licenses permit |
| OSF pre-registration | `preregistration/osf_preregistration.md` | timestamped before Phase C |

## Not redistributed

- **Source files of `T_E` / `T_U` / `T_H`.** We publish `sha1_git` + GitHub origin +
  commit SHA so any file can be re-fetched. `scripts/01_collect_corpus.py` reproduces
  the download.
- **The Stack v2 / Software Heritage exports.** Used only via metadata queries; see below.

## External datasets and access

| Dataset | Access | Use |
|---|---|---|
| GitHub REST API | public + PAT | candidate repos/files, first-commit dates |
| The Stack v2 (`bigcode/the-stack-v2`) | HuggingFace, gated (Software Heritage ToU) | negative membership oracle — **metadata only**, streamed into a bloom filter (`scripts/02_build_stack_v2_bloom.py`); the filter itself is released |
| Software Heritage REST API | public (higher limit with token) | independent timestamp cross-check on a 20% sample |
| CodeSearchNet (`code-search-net/code_search_net`) | HuggingFace, public | RQ6 pre-cutoff attribution candidates |

## Deviation from the report

The report specifies AWS Athena over the Software Heritage ORC export for membership
and timestamp verification. This implementation uses the GitHub commit API + SWH REST
cross-check + a Stack v2 metadata bloom filter instead (no AWS account required). The
membership oracle is therefore probabilistic (bloom false-positive rate ≈ 0.1%); this
is recorded in Threats to Validity. An `AthenaOracle` backend can be substituted via
`exposure_gap.oracle.base.MembershipOracle` without changes elsewhere.
