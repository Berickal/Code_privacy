"""Test-only backend that simulates exposure-specific memorization.

For ``k == 0`` it returns the canonical (converged) implementation for every target.
For ``k > 0`` it returns the idiosyncratic "exposed" implementation for files whose
signature name it recognises, with recall probability rising in ``k`` — so the
exposed-unexposed gap is positive and dose-responsive by construction. Used by the
end-to-end smoke test and analysis unit tests.
"""

from __future__ import annotations

import random
import re

from .infer import GenerationRequest, InferenceBackend

_NAME = re.compile(r"def\s+(\w+)")


class MemorizationSimBackend(InferenceBackend):
    name = "memorization-sim"

    def __init__(self, k: int, exposed_impls: dict[str, str], canonical: str, seed: int = 0):
        self.k = k
        self.exposed_impls = exposed_impls  # function-name -> idiosyncratic body
        self.canonical = canonical
        self.recall_p = {0: 0.0, 1: 0.15, 5: 0.55, 25: 0.9}.get(k, 0.0)
        self.rng = random.Random(seed)

    def generate(self, request: GenerationRequest) -> list[str]:
        m = _NAME.search(request.prompt)
        name = m.group(1) if m else ""
        out = []
        for _ in range(request.decode.n_samples):
            if name in self.exposed_impls and self.rng.random() < self.recall_p:
                body = self.exposed_impls[name]
            else:
                body = self.canonical
            out.append(f"def {name or '_f'}(values, factor):\n{body}")
        return out


class MemorizationSimFactory:
    def __init__(self, exposed_impls: dict[str, str], canonical: str, seed: int = 0):
        self.exposed_impls = exposed_impls
        self.canonical = canonical
        self.seed = seed

    def create(self, model_id: str, k: int, backend: str = "sim", served_name: str | None = None):
        return MemorizationSimBackend(k, self.exposed_impls, self.canonical, self.seed)
