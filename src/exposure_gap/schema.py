"""Shared record types that flow between phases.

These are frozen dataclasses (cheap, hashable, immutable). DataFrames are built from
lists of them via ``.to_row()`` so the on-disk column set is defined in exactly one place.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date

from . import SPLIT_EXPOSED, SPLIT_HOLDOUT, SPLIT_UNEXPOSED


@dataclass(frozen=True, slots=True)
class CandidateFile:
    """A file fetched from GitHub, before verification."""

    file_id: str
    sha1_git: str
    github_repo: str          # "owner/name"
    path: str
    commit_sha: str
    language: str
    domain: str
    first_commit_date: date | None = None
    spdx_license: str | None = None

    def to_row(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FileFeatures:
    """Structural features used for exposed/unexposed matching (report Section 6.3)."""

    file_id: str
    language: str
    domain: str
    loc: int
    cyclomatic: int
    n_functions: int
    has_docstring: bool

    def to_row(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MatchedPair:
    pair_id: str
    exposed_id: str
    unexposed_id: str
    distance: float

    def to_row(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Canary:
    """A deterministic, format-realistic fake secret (report Section 6.5)."""

    canary_id: str
    kind: str                 # "api_key" | "db_conn" | "pem"
    value: str
    file_id: str
    position: str             # "docstring" | "comment" | "string_literal"
    k: int

    def to_row(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CorpusRecord:
    """One row of ``corpus/corpus_metadata.csv`` (report Section 6.3 required table)."""

    file_id: str
    sha1_git: str
    split: str                # E / U / H
    language: str
    domain: str
    loc: int
    cyclomatic: int
    n_functions: int
    has_docstring: bool
    matched_pair_id: str
    spdx_license: str | None
    first_commit_date: date | None
    in_stack_v2: bool
    clone_free_local: bool
    clone_free_sourcerercc: bool
    github_repo: str
    path: str
    commit_sha: str

    def to_row(self) -> dict:
        return asdict(self)

    @property
    def is_exposed(self) -> bool:
        return self.split == SPLIT_EXPOSED

    @property
    def is_unexposed(self) -> bool:
        return self.split == SPLIT_UNEXPOSED

    @property
    def is_holdout(self) -> bool:
        return self.split == SPLIT_HOLDOUT


CORPUS_COLUMNS = [f.name for f in CorpusRecord.__dataclass_fields__.values()]  # type: ignore[attr-defined]


@dataclass(frozen=True, slots=True)
class PredictionRow:
    """One scored generation (report Section 14 minimum schema + metric columns)."""

    sample_id: str
    file_id: str
    split: str
    k: int
    model: str
    prompt_strategy: str
    task: str
    true_label: str
    predicted_output: str
    matched_pair_id: str
    metric_scores: dict[str, float] = field(default_factory=dict)

    def to_row(self) -> dict:
        base = {
            k: v for k, v in asdict(self).items() if k != "metric_scores"
        }
        base.update(self.metric_scores)
        return base
