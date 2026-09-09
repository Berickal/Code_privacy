"""Build the fine-tuning corpus: exposed targets only, each repeated k times, reshuffled
between repetitions (report Section 11.2)."""

from __future__ import annotations

import random
from pathlib import Path

from ..corpus.canaries import CanaryInjector
from ..schema import Canary
from ..utils import write_jsonl


class FinetuneDatasetBuilder:
    def __init__(self, seed: int = 0):
        self.seed = seed
        self.injector = CanaryInjector()

    def _apply_canaries(
        self, sources: dict[str, str], canaries: dict[str, Canary]
    ) -> dict[str, str]:
        out = dict(sources)
        for file_id, canary in canaries.items():
            if file_id in out:
                out[file_id] = self.injector.inject(out[file_id], canary)
        return out

    def build(
        self,
        exposed_sources: dict[str, str],
        k: int,
        canaries: dict[str, Canary] | None = None,
    ) -> list[dict]:
        sources = self._apply_canaries(exposed_sources, canaries or {})
        rng = random.Random(self.seed)
        file_ids = sorted(sources)
        examples: list[dict] = []
        for rep in range(k):
            order = file_ids[:]
            rng.shuffle(order)
            for fid in order:
                examples.append({"file_id": fid, "repetition": rep, "text": sources[fid]})
        return examples

    def write(self, examples: list[dict], path: str | Path) -> Path:
        return write_jsonl(examples, path)
