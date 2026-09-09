"""Deterministic high-entropy canary generation and injection (report Section 6.5).

Every value derives from a single ``master_seed`` so the registry is reproducible and
can be pre-registered on OSF before fine-tuning. All canaries are format-realistic but
fake.
"""

from __future__ import annotations

import hashlib
import random
import string

from ..config import CanaryConfig
from ..schema import Canary

_ALNUM = string.ascii_letters + string.digits
_B64 = _ALNUM + "+/"


class CanaryGenerator:
    """Produces one canary string per (kind, deterministic sub-seed)."""

    def __init__(self, master_seed: int):
        self.master_seed = master_seed

    def _rng(self, tag: str) -> random.Random:
        digest = hashlib.sha256(f"{self.master_seed}:{tag}".encode()).hexdigest()
        return random.Random(int(digest[:16], 16))

    def generate(self, kind: str, tag: str) -> str:
        r = self._rng(f"{kind}:{tag}")
        if kind == "api_key":
            return "sk-" + "".join(r.choice(_ALNUM) for _ in range(48))
        if kind == "db_conn":
            pw = "".join(r.choice(_ALNUM) for _ in range(32))
            return f"postgresql://fakeuser:{pw}@fakehost.internal:5432/fakedb"
        if kind == "pem":
            body = "".join(r.choice(_B64) for _ in range(64 * 6))
            lines = [body[i : i + 64] for i in range(0, len(body), 64)]
            return (
                "-----BEGIN RSA PRIVATE KEY-----\n"
                + "\n".join(lines)
                + "\n-----END RSA PRIVATE KEY-----"
            )
        raise ValueError(f"unknown canary kind: {kind}")


class CanaryRegistry:
    """Builds and holds the (file, position, k) -> canary assignment grid."""

    def __init__(self, config: CanaryConfig):
        self.config = config
        self.generator = CanaryGenerator(config.master_seed)
        self._canaries: list[Canary] = []

    @property
    def canaries(self) -> list[Canary]:
        return list(self._canaries)

    def by_file(self) -> dict[str, Canary]:
        return {c.file_id: c for c in self._canaries}

    def assign(self, exposed_ids_by_k: dict[int, list[str]]) -> list[Canary]:
        """Fill the grid: kinds x positions x k x instances_per_cell.

        ``exposed_ids_by_k`` supplies, per k level, the pool of exposed file IDs that
        are fine-tuned at that frequency (so a canary's host file is repeated k times).
        """
        cfg = self.config
        out: list[Canary] = []
        cursor: dict[int, int] = {k: 0 for k in cfg.k_levels}
        idx = 0
        for kind in cfg.kinds:
            for position in cfg.positions:
                for k in cfg.k_levels:
                    pool = exposed_ids_by_k.get(k, [])
                    for _ in range(cfg.instances_per_cell):
                        if cursor[k] >= len(pool):
                            raise ValueError(
                                f"not enough exposed files at k={k} for canary assignment"
                            )
                        file_id = pool[cursor[k]]
                        cursor[k] += 1
                        out.append(
                            Canary(
                                canary_id=f"canary_{idx:03d}_{kind}_{position}_k{k}",
                                kind=kind,
                                value=self.generator.generate(kind, f"{idx}"),
                                file_id=file_id,
                                position=position,
                                k=k,
                            )
                        )
                        idx += 1
        self._canaries = out
        return out


class CanaryInjector:
    """Inserts a canary line into a source file at its assigned position."""

    def wrap(self, canary: Canary) -> str:
        if canary.position == "docstring":
            return f'    """fixture credential (do not use): {canary.value}"""\n'
        if canary.position == "comment":
            return f"    # fixture: {canary.value}\n"
        return f'    _FIXTURE_SECRET = "{canary.value}"\n'

    def inject(self, source: str, canary: Canary) -> str:
        lines = source.splitlines(keepends=True)
        insert_at = 0
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith(("def ", "class ", "async def ")):
                insert_at = i + 1
                break
        lines.insert(insert_at, self.wrap(canary))
        return "".join(lines)
