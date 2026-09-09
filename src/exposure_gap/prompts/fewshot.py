"""Few-shot example selection for P2 (report Section 7).

P2a: 3 structurally-similar examples from the same domain, no exposure relationship.
P2b: 3 examples from different domains.
Structural similarity = cyclomatic +/-1 and parameter count +/-1.
"""

from __future__ import annotations

import random
import re

from ..schema import FileFeatures


class FewShotSelector:
    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    @staticmethod
    def _n_params(signature: str) -> int:
        m = re.search(r"\(([^)]*)\)", signature)
        if not m or not m.group(1).strip():
            return 0
        return len([p for p in m.group(1).split(",") if p.strip()])

    def select(
        self,
        target: FileFeatures,
        target_signature: str,
        pool: list[tuple[FileFeatures, str, str]],  # (features, signature, source)
        cross_domain: bool,
        n: int = 3,
    ) -> list[str]:
        target_params = self._n_params(target_signature)
        cands = []
        for feats, signature, source in pool:
            if feats.file_id == target.file_id:
                continue
            same_domain = feats.domain == target.domain
            if cross_domain and same_domain:
                continue
            if not cross_domain and not same_domain:
                continue
            if abs(feats.cyclomatic - target.cyclomatic) > 1:
                continue
            if abs(self._n_params(signature) - target_params) > 1:
                continue
            cands.append(source)
        self.rng.shuffle(cands)
        return cands[:n]

    @staticmethod
    def format_block(examples: list[str]) -> str:
        return "\n\n".join(f"# Example {i + 1}\n{ex}" for i, ex in enumerate(examples))
