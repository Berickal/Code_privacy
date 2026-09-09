"""Negative membership oracle: is a file in The Stack v2 (StarCoder2 pre-training)?

No AWS / no bulk download. We stream **metadata only** from ``bigcode/the-stack-v2``
(the per-file rows carry ``blob_id`` == ``sha1_git``), restrict to the languages we
care about, and insert every hash into an mmap bloom filter persisted to disk. A hit
means "probably in the corpus" (FP rate ~0.1%); a miss is exact.

For post-2023-11 files the expected hit count is ~0, so any hit is a data-quality
signal worth inspecting rather than a silent exclusion.
"""

from __future__ import annotations

from pathlib import Path

from ..utils import get_logger
from .base import MembershipOracle

log = get_logger()

DEFAULT_CAPACITY = 400_000_000
DEFAULT_ERROR_RATE = 1e-3


class StackV2BloomOracle(MembershipOracle):
    def __init__(self, bloom_path: str | Path):
        self.bloom_path = Path(bloom_path)
        if not self.bloom_path.exists():
            raise FileNotFoundError(
                f"{self.bloom_path} not found — run StackV2BloomBuilder.build() first"
            )
        from pybloomfilter import BloomFilter

        self._bf = BloomFilter.open(str(self.bloom_path))

    def contains(self, sha1_git: str) -> bool:
        return sha1_git in self._bf

    @property
    def n_items(self) -> int:
        return len(self._bf)


class StackV2BloomBuilder:
    """One-time build. Hours of streaming; run on a machine with good bandwidth."""

    def __init__(
        self,
        bloom_path: str | Path,
        languages: list[str],
        capacity: int = DEFAULT_CAPACITY,
        error_rate: float = DEFAULT_ERROR_RATE,
    ):
        self.bloom_path = Path(bloom_path)
        self.languages = {self._stack_v2_config(lang) for lang in languages}
        self.capacity = capacity
        self.error_rate = error_rate

    def build(self, hf_token: str | None = None, limit: int | None = None) -> Path:
        from pybloomfilter import BloomFilter

        self.bloom_path.parent.mkdir(parents=True, exist_ok=True)
        bf = BloomFilter(self.capacity, self.error_rate, str(self.bloom_path))
        n = 0
        for sha1_git in self._iter_hashes(hf_token=hf_token, limit=limit):
            bf.add(sha1_git)
            n += 1
            if n % 5_000_000 == 0:
                log.info("stack-v2 bloom: {} hashes", n)
        bf.sync()
        log.info("stack-v2 bloom built: {} hashes -> {}", n, self.bloom_path)
        return self.bloom_path

    #: The Stack v2 uses GitHub-linguist config names (capitalised). Map the
    #: lowercase language ids used elsewhere in this codebase onto them.
    _STACK_V2_CONFIGS = {
        "python": "Python",
        "java": "Java",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
        "c": "C",
        "cpp": "C++",
        "c++": "C++",
        "c-sharp": "C-Sharp",
        "csharp": "C-Sharp",
        "go": "Go",
        "rust": "Rust",
        "ruby": "Ruby",
    }

    @classmethod
    def _stack_v2_config(cls, lang: str) -> str:
        return cls._STACK_V2_CONFIGS.get(lang.lower(), lang)

    def _iter_hashes(self, *, hf_token: str | None, limit: int | None):
        from datasets import load_dataset

        seen = 0
        for lang in self.languages:
            ds = load_dataset(
                "bigcode/the-stack-v2",
                lang,
                split="train",
                streaming=True,
                token=hf_token or None,
            )
            for row in ds:
                yield row.get("blob_id") or row.get("sha1_git")
                seen += 1
                if limit and seen >= limit:
                    return
