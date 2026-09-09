"""Rebuild corpus/raw/ byte-identically from the committed metadata.

    python scripts/08_refetch_raw.py

corpus/raw/ is not committed (third-party source — see DATA_AVAILABILITY.md). This
script re-downloads exactly the files in corpus/candidates/corpus_candidates.csv from
GitHub and verifies each blob's sha1_git, so any checkout / compute box reproduces the
identical frozen corpus. Idempotent: skips files already present with the right hash.
"""

from __future__ import annotations

import base64
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import click
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from exposure_gap.config import Settings
from exposure_gap.corpus import CorpusStore
from exposure_gap.oracle import GitHubClient
from exposure_gap.utils import get_logger, git_blob_sha1_text, setup_logging

log = get_logger()


@click.command()
@click.option("--root", default=".")
@click.option("--metadata-only", is_flag=True, help="only fetch files kept in corpus_metadata.csv")
def main(root: str, metadata_only: bool) -> None:
    load_dotenv(Path(root) / ".env")
    load_dotenv(Path(root).parent / ".env")
    setup_logging()

    settings = Settings.load(root)
    store = CorpusStore(settings.corpus_dir)
    cand = pd.read_csv(store.candidates_dir / "corpus_candidates.csv")

    if metadata_only:
        meta_path = settings.corpus_dir / "corpus_metadata.csv"
        keep = set(pd.read_csv(meta_path)["file_id"])
        cand = cand[cand["file_id"].isin(keep)]

    client = GitHubClient()
    if client.token and not client.authenticated:
        client.session.headers.pop("Authorization", None)
        client.token = None
        log.warning("GITHUB_TOKEN invalid — unauthenticated (60 req/hr)")

    ok = skipped = failed = mismatch = 0
    for row in tqdm(list(cand.itertuples(index=False)), desc="refetch"):
        dest = store.raw_dir / f"{row.file_id}.txt"
        if dest.exists() and git_blob_sha1_text(dest.read_text()) == row.sha1_git:
            skipped += 1
            continue
        repo = row.github_repo
        resp = client.get(
            f"/repos/{repo}/contents/{row.path}", params={"ref": row.commit_sha}
        )
        if resp.status_code != 200 or resp.json().get("encoding") != "base64":
            failed += 1
            continue
        text = base64.b64decode(resp.json()["content"]).decode("utf-8", errors="replace")
        if git_blob_sha1_text(text) != row.sha1_git:
            mismatch += 1
            log.warning("sha1_git mismatch for {} ({}@{})", row.file_id, repo, row.path)
            continue
        dest.write_text(text)
        ok += 1
        time.sleep(0.05)

    click.echo(f"fetched {ok}, verified-present {skipped}, failed {failed}, hash-mismatch {mismatch}")
    if failed or mismatch:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
