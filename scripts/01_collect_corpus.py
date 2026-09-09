"""Phase A1/A2: collect candidate repos + files from GitHub into the CorpusStore.

    python scripts/01_collect_corpus.py --languages python --repos 120 --target-files 160

Loads .env, then writes corpus/raw/<file_id>.txt and corpus/candidates/corpus_candidates.csv.
Post-cutoff verification, dedup, matching and freeze happen in `exposure-gap build-corpus`.
"""

from __future__ import annotations

import dataclasses
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import click
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from exposure_gap.config import Settings
from exposure_gap.corpus import CorpusStore, FileFetcher, FileLister, RepoCollector
from exposure_gap.oracle import GitHubClient
from exposure_gap.utils import get_logger, setup_logging

log = get_logger()


def _round_robin_by_domain(repos: list) -> list:
    """Interleave repos across domains (each domain sorted by stars) so a file-count
    cap yields a balanced corpus."""
    from collections import defaultdict

    buckets: dict[str, list] = defaultdict(list)
    for r in repos:
        buckets[r.domain].append(r)
    for b in buckets.values():
        b.sort(key=lambda r: r.stars, reverse=True)
    out, order = [], sorted(buckets)
    while any(buckets[d] for d in order):
        for d in order:
            if buckets[d]:
                out.append(buckets[d].pop(0))
    return out


def _repo_license(client: GitHubClient, repo: str) -> str | None:
    resp = client.get(f"/repos/{repo}")
    if resp.status_code != 200:
        return None
    lic = (resp.json() or {}).get("license") or {}
    return lic.get("spdx_id")


@click.command()
@click.option("--root", default=".")
@click.option("--languages", default=None, help="comma list; overrides config")
@click.option("--repos", "repo_cap", default=150, help="repos to scan per language")
@click.option("--files-per-repo", default=4)
@click.option("--target-files", default=0, help="stop once this many files are collected (0 = no cap)")
@click.option("--min-commits", default=None, type=int)
@click.option("--commit-check/--no-commit-check", default=True, help="skip to save API calls")
@click.option("--by-domain/--generic", default=True, help="targeted per-domain search vs one popularity search")
@click.option("--generic-topup", default=0, help="also pull N generic-search repos (domain via classifier)")
def main(
    root: str,
    languages: str | None,
    repo_cap: int,
    files_per_repo: int,
    target_files: int,
    min_commits: int | None,
    commit_check: bool,
    by_domain: bool,
    generic_topup: int,
) -> None:
    load_dotenv(Path(root) / ".env")
    load_dotenv(Path(root).parent / ".env")  # project-level .env
    setup_logging()

    settings = Settings.load(root)
    if languages:
        settings.corpus.languages = [x.strip() for x in languages.split(",")]
    if min_commits is not None:
        settings.corpus.min_commits = min_commits

    client = GitHubClient()
    if client.token and not client.authenticated:
        log.warning("GITHUB_TOKEN is invalid/expired — falling back to unauthenticated (60 req/hr)")
        client.session.headers.pop("Authorization", None)
        client.token = None
    log.info(
        "github: authenticated={} rate_limit_remaining={}",
        bool(client.token),
        client.rate_limit_remaining(),
    )

    store = CorpusStore(settings.corpus_dir)
    collector = RepoCollector(settings.corpus, client)
    lister = FileLister(settings.corpus, client)
    fetcher = FileFetcher(settings.corpus, client)

    rows: list[dict] = []
    for language in settings.corpus.languages:
        if by_domain:
            repos = collector.search_by_domain(language, cap_per_domain=repo_cap)
        else:
            repos = collector.search(language, cap=repo_cap)
        if generic_topup:
            have = {r.repo for r in repos}
            repos += [r for r in collector.search(language, cap=generic_topup) if r.repo not in have]
        repos = _round_robin_by_domain(repos)
        log.info(
            "{}: {} repos | domains {}",
            language, len(repos),
            {d: sum(r.domain == d for r in repos) for d in sorted({r.domain for r in repos})},
        )
        for repo in tqdm(repos, desc=f"{language} repos"):
            if target_files and len(rows) >= target_files:
                break
            if commit_check and not collector.commit_count_ok(repo.repo):
                continue
            created = datetime.fromisoformat(repo.created_at.replace("Z", "+00:00")).date()
            spdx = repo.spdx_license or _repo_license(client, repo.repo)
            for cand in lister.list_files(repo)[:files_per_repo]:
                fetched = fetcher.fetch(cand)
                if fetched is None:
                    continue
                enriched, text = fetched
                enriched = dataclasses.replace(
                    enriched, first_commit_date=created, spdx_license=spdx
                )
                store.write_source(enriched.file_id, text)
                rows.append(enriched.to_row())

    store.write_candidates(pd.DataFrame(rows).drop_duplicates("file_id"))
    click.echo(f"{len(rows)} candidate files -> {store.candidates_dir/'corpus_candidates.csv'}")


if __name__ == "__main__":
    main()
