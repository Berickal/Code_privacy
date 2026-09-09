"""High-level phase orchestrators wired to :class:`~exposure_gap.config.Settings`.

Thin glue so the CLI and notebooks share one code path. Each method corresponds to a
report phase (Section 13).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import K_LEVELS, SPLIT_EXPOSED
from .analysis import AnalysisArtifacts, AnalysisPipeline
from .config import Settings
from .corpus import (
    CanaryRegistry,
    CorpusBuilder,
    CorpusStore,
    FreezeManager,
    SourcererCCRunner,
)
from .eval import BackendFactory, EvaluationMatrix, TargetLoader, TaskRunner
from .oracle import NullMembershipOracle
from .prompts import PromptMaterializer, PromptRegistry
from .schema import Canary
from .utils import get_logger, read_json, write_json

log = get_logger()


@dataclass
class PhaseContext:
    settings: Settings

    @property
    def store(self) -> CorpusStore:
        return CorpusStore(self.settings.corpus_dir)

    @property
    def prompt_registry(self) -> PromptRegistry:
        return PromptRegistry(self.settings.prompts_dir)

    @property
    def freeze(self) -> FreezeManager:
        return FreezeManager(self.settings.root)


class Phases:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.load()
        self.ctx = PhaseContext(self.settings)

    # -- Phase A --------------------------------------------------------
    def build_corpus(
        self,
        membership_oracle=None,
        timestamp_oracle=None,
    ):
        builder = CorpusBuilder(
            config=self.settings.corpus,
            store=self.ctx.store,
            membership_oracle=membership_oracle or NullMembershipOracle(),
            timestamp_oracle=timestamp_oracle,
            sourcerercc=SourcererCCRunner(),
        )
        return builder.run()

    # -- Phase B --------------------------------------------------------
    def build_canaries(self) -> list[Canary]:
        store = self.ctx.store
        meta = store.read_metadata()
        exposed = meta[meta["split"] == SPLIT_EXPOSED]["file_id"].tolist()
        rng = random.Random(self.settings.canary.master_seed)
        rng.shuffle(exposed)
        # disjoint host-file pools per k level
        per_k = max(1, len(exposed) // len(self.settings.canary.k_levels))
        pools = {
            k: exposed[i * per_k : (i + 1) * per_k]
            for i, k in enumerate(self.settings.canary.k_levels)
        }
        registry = CanaryRegistry(self.settings.canary)
        canaries = registry.assign(pools)
        write_json(
            {"canaries": [c.to_row() for c in canaries]},
            store.canary_registry_path,
        )
        log.info("wrote {} canaries -> {}", len(canaries), store.canary_registry_path)
        return canaries

    def load_canaries(self) -> dict[str, Canary]:
        p = self.ctx.store.canary_registry_path
        if not p.exists():
            return {}
        return {
            row["file_id"]: Canary(**row) for row in read_json(p)["canaries"]
        }

    # -- Phase D --------------------------------------------------------
    def materialize_prompts(self) -> int:
        n = PromptMaterializer().write_all(self.settings.prompts_dir)
        log.info("materialized {} prompt templates", n)
        return n

    def check_prompts(self) -> list[str]:
        meta_path = self.settings.corpus_dir / "corpus_metadata.csv"
        exposed: list[str] = []
        if meta_path.exists():
            df = pd.read_csv(meta_path)
            exposed = df[df["split"] == SPLIT_EXPOSED]["file_id"].astype(str).tolist()
        return self.ctx.prompt_registry.audit_no_target_leakage(exposed)

    # -- Freeze -------------------------------------------------------
    def write_freeze(self) -> Path:
        return self.ctx.freeze.write()

    def verify_freeze(self):
        return self.ctx.freeze.verify()

    # -- Phase F / G ------------------------------------------------
    def _task_runner(
        self, offline: bool, quantization: str | None = None, batch_size: int = 8
    ) -> TaskRunner:
        return TaskRunner(
            registry=self.ctx.prompt_registry,
            decode=self.settings.decode,
            backend_factory=BackendFactory(
                offline=offline,
                checkpoints_dir=str(self.settings.checkpoints_dir),
                quantization=quantization,
                batch_size=batch_size,
                hf_ids={m.id: m.hf_model_id for m in self.settings.finetune.models if m.hf_model_id},
            ),
            canary_registry=self.load_canaries(),
            levenshtein_max=self.settings.canary.levenshtein_max,
        )

    def evaluate(
        self,
        models: list[tuple[str, str]] | None = None,
        k_levels: tuple[int, ...] = (0, *K_LEVELS),
        tasks=None,
        strategies=None,
        offline: bool = False,
        splits: tuple[str, ...] = ("E", "U"),
        quantization: str | None = None,
        batch_size: int = 8,
    ) -> pd.DataFrame:
        self.ctx.freeze.assert_clean()
        loader = TargetLoader(
            self.ctx.store,
            oracle_suites_dir=self.settings.root / "tests" / "oracle_suites",
        )
        targets = loader.load(splits=splits)
        runner = self._task_runner(offline, quantization=quantization, batch_size=batch_size)

        if not offline and models and any(b == "vllm" for _, b in models):
            from .eval.infer import VLLMBackend

            ok, why = VLLMBackend("_probe").healthy()
            if not ok:
                raise RuntimeError(
                    f"vLLM server not reachable ({why}). Start it first:\n"
                    "  python scripts/serve_vllm.py --model <id> --run\n"
                    "then re-run this command from another terminal."
                )
        matrix = EvaluationMatrix(runner, self.settings.results_dir / "raw_predictions")
        models = models or [
            (m.id, m.backend) for m in self.settings.finetune.models
        ] or [("echo-model", "echo")]
        from . import PROMPT_STRATEGIES, TASKS

        return matrix.run(
            targets=targets,
            models=models,
            k_levels=k_levels,
            tasks=tasks or TASKS,
            strategies=strategies or PROMPT_STRATEGIES,
        )

    # -- Phase G analysis ----------------------------------------
    def analyse(self, predictions: pd.DataFrame | None = None) -> AnalysisArtifacts:
        if predictions is None:
            path = self.settings.results_dir / "raw_predictions" / "all_predictions.parquet"
            predictions = pd.read_parquet(path)
        pipeline = AnalysisPipeline(self.settings.analysis)
        return pipeline.run(predictions, self.settings.results_dir / "metrics")
