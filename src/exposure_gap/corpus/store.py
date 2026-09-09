"""On-disk layout for the corpus (raw sources + metadata tables)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..schema import CORPUS_COLUMNS, CorpusRecord
from ..utils import ensure_dir, read_table, write_table


class CorpusStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.raw_dir = ensure_dir(self.root / "raw")
        self.candidates_dir = ensure_dir(self.root / "candidates")

    # -- raw sources ----------------------------------------------------
    def write_source(self, file_id: str, text: str) -> Path:
        p = self.raw_dir / f"{file_id}.txt"
        p.write_text(text)
        return p

    def read_source(self, file_id: str) -> str:
        return (self.raw_dir / f"{file_id}.txt").read_text()

    def has_source(self, file_id: str) -> bool:
        return (self.raw_dir / f"{file_id}.txt").exists()

    def all_sources(self) -> dict[str, str]:
        return {p.stem: p.read_text() for p in self.raw_dir.glob("*.txt")}

    # -- tables -------------------------------------------------------
    def write_candidates(self, df: pd.DataFrame) -> Path:
        return write_table(df, self.candidates_dir / "corpus_candidates.csv")

    def read_candidates(self) -> pd.DataFrame:
        return read_table(self.candidates_dir / "corpus_candidates.csv")

    def write_metadata(self, records: list[CorpusRecord]) -> Path:
        df = pd.DataFrame([r.to_row() for r in records], columns=CORPUS_COLUMNS)
        df = df.sort_values("file_id").reset_index(drop=True)
        return write_table(df, self.root / "corpus_metadata.csv")

    def read_metadata(self) -> pd.DataFrame:
        return read_table(self.root / "corpus_metadata.csv")

    def records(self) -> list[CorpusRecord]:
        df = self.read_metadata()
        return [CorpusRecord(**{c: row[c] for c in CORPUS_COLUMNS}) for _, row in df.iterrows()]

    # -- canary registry --------------------------------------------
    @property
    def canary_registry_path(self) -> Path:
        return self.root / "canary_registry.json"
