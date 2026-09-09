"""Pre-load Software Heritage provenance for the collected corpus.

    python scripts/05_preload_swh.py            # after scripts/01_collect_corpus.py

For every candidate file: cache whether SWH has the blob (`content_known`).
For every unique repo: cache SWH's earliest visit date (`origin_first_visit`).
With SWH_TOKEN set, also resolves each blob's earliest containing revision date.

Results persist in corpus/swh_cache.sqlite and are exported to
corpus/swh_provenance.parquet + a GitHub-vs-SWH agreement report.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import click
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from exposure_gap.config import Settings
from exposure_gap.oracle import SWHCache, SWHRestOracle
from exposure_gap.utils import get_logger, setup_logging

log = get_logger()


@click.command()
@click.option("--root", default=".")
@click.option("--sample-frac", default=1.0, help="fraction of files to look up (report swh_cross_check_fraction)")
def main(root: str, sample_frac: float) -> None:
    load_dotenv(Path(root) / ".env")
    load_dotenv(Path(root).parent / ".env")
    setup_logging()

    settings = Settings.load(root)
    cand_path = settings.corpus_dir / "candidates" / "corpus_candidates.csv"
    if not cand_path.exists():
        raise SystemExit(f"{cand_path} not found — run scripts/01_collect_corpus.py first")
    df = pd.read_csv(cand_path)

    cache = SWHCache(settings.corpus_dir / "swh_cache.sqlite")
    swh = SWHRestOracle(cache=cache)
    log.info("swh graph API {}", "enabled (token)" if swh.graph_enabled else "disabled (no SWH_TOKEN)")

    sample = df.sample(frac=sample_frac, random_state=settings.corpus.seed) if sample_frac < 1 else df

    # repo-level: earliest SWH visit
    cutoff = settings.corpus.cutoff_date
    repos = sorted(sample["github_repo"].unique())
    for repo in tqdm(repos, desc="origins"):
        swh.origin_first_visit(f"https://github.com/{repo}", stop_before=cutoff)

    # file-level: known + first_seen
    rows = []
    for r in tqdm(list(sample.itertuples(index=False)), desc="contents"):
        known = swh.contains(r.sha1_git)
        first_seen = swh.first_seen(sha1_git=r.sha1_git, repo=r.github_repo, path=r.path)
        origin_visit, archived = cache.get_origin(f"https://github.com/{r.github_repo}") or (None, False)
        gh = pd.to_datetime(r.first_commit_date).date() if pd.notna(r.first_commit_date) else None
        rows.append(
            {
                "file_id": r.file_id,
                "sha1_git": r.sha1_git,
                "github_repo": r.github_repo,
                "swh_known": known,
                "swh_first_seen": first_seen,
                "swh_origin_first_visit": origin_visit,
                "github_first_commit_date": gh,
                "post_cutoff_swh": (first_seen or origin_visit or gh) and
                                   (first_seen or origin_visit or gh) > settings.corpus.cutoff_date,
            }
        )
    out = pd.DataFrame(rows)
    prov_path = settings.corpus_dir / "swh_provenance.parquet"
    out.to_parquet(prov_path, index=False)
    cache.to_json(settings.corpus_dir / "swh_cache.json")

    known_rate = out["swh_known"].mean()
    disagree = out[
        out["swh_origin_first_visit"].notna()
        & out["github_first_commit_date"].notna()
        & (out["swh_origin_first_visit"] < settings.corpus.cutoff_date)
        & (out["github_first_commit_date"] > settings.corpus.cutoff_date)
    ]
    click.echo(f"{len(out)} files | SWH-known: {known_rate:.1%} | "
               f"GitHub says post-cutoff but SWH saw the repo earlier: {len(disagree)}")
    click.echo(f"-> {prov_path}")


if __name__ == "__main__":
    main()
