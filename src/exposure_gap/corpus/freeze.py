"""FREEZE.lock — SHA-256 of every input that must not change once model runs begin
(report Section 11.1, Phases B-E)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..utils import get_logger, read_json, sha256_file, write_json

log = get_logger()

FROZEN_GLOBS = (
    "corpus/corpus_metadata.csv",
    "corpus/canary_registry.json",
    "prompts/**/*.txt",
    "configs/*.yaml",
    "tests/oracle_suites/**/*.py",
)


@dataclass(frozen=True)
class FreezeViolation:
    kind: str  # "modified" | "deleted" | "added"
    path: str

    def __str__(self) -> str:
        return f"{self.kind}: {self.path}"


class FreezeManager:
    def __init__(self, root: str | Path = "."):
        self.root = Path(root)
        self.lock_path = self.root / "FREEZE.lock"

    def _iter_paths(self) -> list[Path]:
        found: list[Path] = []
        for pattern in FROZEN_GLOBS:
            found.extend(sorted(self.root.glob(pattern)))
        return found

    def write(self) -> Path:
        lock = {
            str(p.relative_to(self.root)): sha256_file(p)
            for p in self._iter_paths()
            if p.is_file()
        }
        write_json(lock, self.lock_path)
        log.info("wrote {} ({} entries)", self.lock_path, len(lock))
        return self.lock_path

    def verify(self) -> list[FreezeViolation]:
        if not self.lock_path.exists():
            raise FileNotFoundError("FREEZE.lock missing — run `exposure-gap freeze` first")
        lock: dict[str, str] = read_json(self.lock_path)
        violations: list[FreezeViolation] = []
        for rel, want in lock.items():
            p = self.root / rel
            if not p.exists():
                violations.append(FreezeViolation("deleted", rel))
            elif sha256_file(p) != want:
                violations.append(FreezeViolation("modified", rel))
        current = {str(p.relative_to(self.root)) for p in self._iter_paths() if p.is_file()}
        for extra in sorted(current - set(lock)):
            violations.append(FreezeViolation("added", extra))
        return violations

    def assert_clean(self) -> None:
        violations = self.verify()
        if violations:
            raise RuntimeError(
                "FREEZE.lock violated:\n" + "\n".join(f"  {v}" for v in violations)
            )
