"""End-to-end smoke test — no network, no GPU.

Builds a synthetic matched corpus, materialises prompts, freezes, runs the full
evaluation matrix with a memorization-simulating backend, and runs the analysis
pipeline. Asserts that a positive, dose-responsive exposed-unexposed gap is detected.

    python scripts/00_smoke_test.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


from exposure_gap import PROMPT_STRATEGIES, TASK_REPRODUCTION
from exposure_gap.analysis import AnalysisPipeline
from exposure_gap.config import Settings
from exposure_gap.corpus import (
    CorpusBuilder,
    CorpusStore,
    FreezeManager,
    SourcererCCRunner,
    SyntheticCorpus,
)
from exposure_gap.eval import EvaluationMatrix, MemorizationSimFactory, TargetLoader, TaskRunner
from exposure_gap.oracle import NullMembershipOracle
from exposure_gap.prompts import PromptMaterializer, PromptRegistry


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="exposure_gap_smoke_"))
    try:
        # copy configs into the temp root
        src_root = Path(__file__).resolve().parents[1]
        shutil.copytree(src_root / "configs", root / "configs")
        settings = Settings.load(root)
        settings.corpus.gate1.min_matched_pairs_per_language = 4  # relax for 8-pair corpus
        settings.corpus.languages = ["python"]  # synthetic corpus is python-only

        store = CorpusStore(root / "corpus")
        syn = SyntheticCorpus(seed=0)
        exposed, unexposed, holdout = syn.populate_store(store, n_pairs=8, n_holdout=4)

        # -- Phase A -------------------------------------------------
        builder = CorpusBuilder(
            config=settings.corpus,
            store=store,
            membership_oracle=NullMembershipOracle(),
            timestamp_oracle=None,
            # token-Jaccard is unreliable on tiny near-templated files; disable for the
            # synthetic smoke corpus. Real runs use the SourcererCC jar.
            sourcerercc=SourcererCCRunner(type2_threshold=2.0),
        )
        report = builder.run(
            forced_pairs=syn.forced_pairs(exposed, unexposed),
            forced_holdout={f.file_id for f in holdout},
        )
        print("corpus:", report)
        assert report.n_pairs >= 4, report
        assert report.n_holdout >= 1, report

        # -- Phase D -------------------------------------------------
        PromptMaterializer().write_all(root / "prompts")
        registry = PromptRegistry(root / "prompts")
        assert len(registry.templates) == 30
        assert not registry.audit_no_target_leakage([f.file_id for f in exposed])

        # -- Freeze --------------------------------------------------
        FreezeManager(root).write()
        assert not FreezeManager(root).verify()

        # -- Phase F/G ----------------------------------------------
        targets = TargetLoader(store).load(splits=("E", "U"))
        assert targets, "no targets loaded"
        runner = TaskRunner(
            registry=registry,
            decode=settings.decode,
            backend_factory=MemorizationSimFactory(
                syn.exposed_impls(exposed), canonical="    return [v * factor for v in values]"
            ),
        )
        matrix = EvaluationMatrix(runner, root / "results" / "raw_predictions")
        preds = matrix.run(
            targets=targets,
            models=[("sim-model", "sim")],
            k_levels=(0, 1, 5, 25),
            tasks=(TASK_REPRODUCTION,),
            strategies=PROMPT_STRATEGIES,
        )
        assert not preds.empty

        # -- Analysis --------------------------------------------
        artifacts = AnalysisPipeline(settings.analysis).run(preds, root / "results" / "metrics")
        gaps = artifacts.gaps
        lex = gaps[(gaps.metric == "lexical_f1") & (gaps.k == 25)]
        print(lex[["prompt", "delta", "ci_low", "ci_high", "p_adj"]].to_string(index=False))
        assert (lex["delta"] > 0).any(), "expected a positive gap at k=25"

        dose = artifacts.dose_response
        assert not dose.empty
        assert (dose["mean_delta_k25"] >= dose["mean_delta_k1"]).any(), "expected dose-response"

        print("\nSMOKE TEST PASSED")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
