"""Phase F/G evaluation driver.

``TaskRunner`` runs one (model, k, task, strategy) cell over a target list.
``EvaluationMatrix`` iterates the full grid and writes ``results/raw_predictions/``.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from .. import (
    PROMPT_STRATEGIES,
    TASK_ATTRIBUTION,
    TASK_CANARY,
    TASK_REPRODUCTION,
    TASKS,
)
from ..config import DecodeConfig
from ..schema import Canary, PredictionRow
from ..utils import ensure_dir, get_logger, write_table
from .attribution import AttributionScorer
from .canary import CanaryScorer
from .infer import BackendFactory, InferenceBackend
from .reproduction import ReproductionScorer
from .targets import EvalTarget

log = get_logger()


@dataclass
class CellSpec:
    model: str
    k: int
    task: str
    strategy: str
    backend: str = "openrouter"
    served_name: str | None = None


class TaskRunner:
    def __init__(
        self,
        registry,               # PromptRegistry
        decode: DecodeConfig,
        backend_factory: BackendFactory | None = None,
        canary_registry: dict[str, Canary] | None = None,
        levenshtein_max: int = 2,
    ):
        self.registry = registry
        self.decode = decode
        self.factory = backend_factory or BackendFactory()
        self.canaries = canary_registry or {}
        self.repro_scorer = ReproductionScorer()
        self.attr_scorer = AttributionScorer()
        self.canary_scorer = CanaryScorer(levenshtein_max)

    # ------------------------------------------------------------------
    def _score(self, task: str, output: str, target: EvalTarget) -> dict[str, float]:
        if task == TASK_REPRODUCTION:
            return self.repro_scorer.score(
                output,
                target.fields.body_reference,
                language=target.record.language,
                test_source=target.test_source,
            )
        if task == TASK_ATTRIBUTION:
            return self.attr_scorer.score(
                output,
                gold_repo=target.record.github_repo,
                gold_spdx=target.record.spdx_license or "NOASSERTION",
            )
        if task == TASK_CANARY:
            canary = self.canaries.get(target.file_id)
            if canary is None:
                return {}
            return self.canary_scorer.score(output, value=canary.value, kind=canary.kind)
        raise ValueError(task)

    def _true_label(self, task: str, target: EvalTarget) -> str:
        if task == TASK_ATTRIBUTION:
            return target.record.github_repo
        if task == TASK_CANARY:
            c = self.canaries.get(target.file_id)
            return c.value if c else ""
        return target.fields.body_reference

    # ------------------------------------------------------------------
    def run_cell(
        self, spec: CellSpec, targets: list[EvalTarget], *, progress: bool = True
    ) -> list[PredictionRow]:
        if not self.registry.has(spec.task, spec.strategy):
            return []
        backend: InferenceBackend = self.factory.create(
            spec.model, spec.k, spec.backend, spec.served_name
        )
        decode = self.decode.for_task(spec.task)

        items = [
            (t, self.registry.render(spec.task, spec.strategy, t.fields, few_shot=""))
            for t in targets
            if not (spec.task == TASK_CANARY and t.file_id not in self.canaries)
        ]
        if not items:
            return []

        tag = f"{spec.model} k{spec.k} {spec.task}/{spec.strategy}"
        batches = backend.generate_batch(
            [p for _, p in items], decode, desc=f"gen {tag}" if progress else None
        )

        rows: list[PredictionRow] = []
        for (target, _), completions in tqdm(
            zip(items, batches), total=len(items), desc=f"score {tag}",
            disable=not progress, leave=False,
        ):
            for si, output in enumerate(completions):
                rows.append(
                    PredictionRow(
                        sample_id=f"{spec.model}|k{spec.k}|{spec.task}|{spec.strategy}|{target.file_id}|{si}",
                        file_id=target.file_id,
                        split=target.split,
                        k=spec.k,
                        model=spec.model,
                        prompt_strategy=spec.strategy,
                        task=spec.task,
                        true_label=self._true_label(spec.task, target),
                        predicted_output=output,
                        matched_pair_id=target.matched_pair_id,
                        metric_scores=self._score(spec.task, output, target),
                    )
                )
        log.info("cell {} -> {} rows", tag, len(rows))
        return rows


class EvaluationMatrix:
    def __init__(self, runner: TaskRunner, out_dir: str | Path):
        self.runner = runner
        self.out_dir = ensure_dir(Path(out_dir))

    def _cell_path(self, model_id: str, k: int, task: str, strategy: str) -> Path:
        return self.out_dir / f"{model_id}__k{k}__{task}__{strategy}.parquet"

    def run(
        self,
        targets: list[EvalTarget],
        models: list[tuple[str, str]],   # (model_id, backend)
        k_levels: tuple[int, ...],
        tasks: tuple[str, ...] = TASKS,
        strategies: tuple[str, ...] = PROMPT_STRATEGIES,
        resume: bool = True,
    ) -> pd.DataFrame:
        cells = list(product(models, k_levels, tasks, strategies))
        for (model_id, backend), k, task, strategy in tqdm(cells, desc="cells", unit="cell"):
            path = self._cell_path(model_id, k, task, strategy)
            if resume and path.exists():
                log.info("skip (cached): {}", path.name)
                continue
            spec = CellSpec(model_id, k, task, strategy, backend=backend)
            rows = self.runner.run_cell(spec, targets)
            frame = pd.DataFrame(r.to_row() for r in rows)
            if not frame.empty:
                write_table(frame, path)

        # rebuild the combined table from every cell parquet on disk
        parts = [
            pd.read_parquet(p)
            for p in sorted(self.out_dir.glob("*__k*__*.parquet"))
            if p.name != "all_predictions.parquet"
        ]
        combined = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        if not combined.empty:
            write_table(combined, self.out_dir / "all_predictions.parquet")
        return combined
