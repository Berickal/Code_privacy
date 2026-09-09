"""Evaluation targets: a corpus record joined with its source and derived fields."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..corpus.store import CorpusStore
from ..prompts import TargetFieldExtractor, TargetFields
from ..schema import CorpusRecord


@dataclass(frozen=True)
class EvalTarget:
    record: CorpusRecord
    source: str
    fields: TargetFields
    test_source: str | None = None

    @property
    def file_id(self) -> str:
        return self.record.file_id

    @property
    def split(self) -> str:
        return self.record.split

    @property
    def matched_pair_id(self) -> str:
        return self.record.matched_pair_id


class TargetLoader:
    def __init__(self, store: CorpusStore, oracle_suites_dir: str | Path | None = None):
        self.store = store
        self.oracle_suites_dir = Path(oracle_suites_dir) if oracle_suites_dir else None
        self.extractor = TargetFieldExtractor()

    def _test_source(self, file_id: str) -> str | None:
        if not self.oracle_suites_dir:
            return None
        p = self.oracle_suites_dir / f"{file_id}.py"
        return p.read_text() if p.exists() else None

    def load(self, splits: tuple[str, ...] = ("E", "U")) -> list[EvalTarget]:
        targets: list[EvalTarget] = []
        for rec in self.store.records():
            if rec.split not in splits:
                continue
            source = self.store.read_source(rec.file_id)
            fields = self.extractor.extract(
                rec.file_id, source, rec.language, rec.domain, rec.path
            )
            targets.append(
                EvalTarget(
                    record=rec,
                    source=source,
                    fields=fields,
                    test_source=self._test_source(rec.file_id),
                )
            )
        return targets
