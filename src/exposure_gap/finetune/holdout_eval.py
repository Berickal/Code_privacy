"""Quantify the general-capability change from fine-tuning (report H2, Section 11.2).

Runs pass@1 on the unexposed holdout T_H before and after each fine-tuning run. The
residual holdout gain is reported separately from Delta_pi and must not, on its own,
explain the exposed-unexposed gap.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from ..eval.infer import BackendFactory, GenerationRequest
from ..eval.targets import EvalTarget
from ..eval.tests_harness import PassAtOneRunner
from ..config import DecodeConfig


@dataclass(frozen=True)
class HoldoutDelta:
    model: str
    k: int
    pass1_before: float
    pass1_after: float
    delta: float
    catastrophic_forgetting: bool

    def to_row(self) -> dict:
        return asdict(self)


class HoldoutEvaluator:
    def __init__(
        self,
        decode: DecodeConfig,
        backend_factory: BackendFactory | None = None,
        runner: PassAtOneRunner | None = None,
        forgetting_threshold: float = -0.02,
    ):
        self.decode = decode
        self.factory = backend_factory or BackendFactory()
        self.runner = runner or PassAtOneRunner()
        self.forgetting_threshold = forgetting_threshold

    def _pass1(self, model: str, k: int, backend: str, targets: list[EvalTarget]) -> float:
        be = self.factory.create(model, k, backend)
        spec = self.decode.for_task("reproduction")
        hits = 0
        for t in targets:
            if not t.test_source:
                continue
            prompt = f'{t.fields.signature}\n    """{t.fields.docstring}"""\n'
            out = be.generate(GenerationRequest(prompt=prompt, decode=spec))[0]
            hits += int(self.runner.run(out, t.test_source))
        n = sum(1 for t in targets if t.test_source)
        return hits / max(n, 1)

    def evaluate(
        self, model: str, k: int, backend: str, holdout_targets: list[EvalTarget]
    ) -> HoldoutDelta:
        before = self._pass1(model, 0, backend, holdout_targets)
        after = self._pass1(model, k, backend, holdout_targets)
        d = after - before
        return HoldoutDelta(model, k, before, after, d, d < self.forgetting_threshold)

    @staticmethod
    def to_frame(rows: list[HoldoutDelta]) -> pd.DataFrame:
        return pd.DataFrame(r.to_row() for r in rows)
