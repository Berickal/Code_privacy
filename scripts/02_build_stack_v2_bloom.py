"""One-time: build the Stack v2 membership bloom filter (report §6.2.1, PLAN §1).

    HF_TOKEN=... python scripts/02_build_stack_v2_bloom.py --out data/stack_v2.bloom

Streams metadata only (no code download). Hours of streaming; run on good bandwidth.
Use --limit for a smoke build.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import click

from exposure_gap.config import Settings
from exposure_gap.oracle import StackV2BloomBuilder
from exposure_gap.utils import setup_logging


@click.command()
@click.option("--root", default=".")
@click.option("--out", default="data/stack_v2.bloom")
@click.option("--limit", default=None, type=int, help="cap hashes (smoke build)")
def main(root: str, out: str, limit: int | None) -> None:
    setup_logging()
    settings = Settings.load(root)
    import os

    builder = StackV2BloomBuilder(out, languages=settings.corpus.languages)
    builder.build(hf_token=os.environ.get("HF_TOKEN"), limit=limit)
    click.echo(f"bloom filter written to {out}")


if __name__ == "__main__":
    main()
