"""Oracle interfaces.

The corpus pipeline needs two questions answered per candidate file:

* **Membership** — was this content in the model's pre-training corpus?
  (report Section 6.2.1 — The Stack v2 as the negative oracle)
* **Timestamp** — when did this content first appear publicly?
  (report Section 6.2.2 — commit-date cutoff oracle)

Concrete backends are swappable: the no-AWS build uses
:class:`~exposure_gap.oracle.stack_v2.StackV2BloomOracle` +
:class:`~exposure_gap.oracle.github_time.GitHubTimestampOracle`, cross-checked against
:class:`~exposure_gap.oracle.swh_rest.SWHRestOracle`. An ``AthenaOracle`` can be added
later without touching downstream code.
"""

from __future__ import annotations

import abc
from datetime import date


class MembershipOracle(abc.ABC):
    """Answers: is ``sha1_git`` in the pre-training corpus?"""

    @abc.abstractmethod
    def contains(self, sha1_git: str) -> bool:
        ...

    def contains_any(self, sha1_gits: list[str]) -> dict[str, bool]:
        return {s: self.contains(s) for s in sha1_gits}


class TimestampOracle(abc.ABC):
    """Answers: what is the earliest known public appearance date of this content?"""

    @abc.abstractmethod
    def first_seen(self, *, sha1_git: str, repo: str | None = None, path: str | None = None) -> date | None:
        ...

    def is_post_cutoff(self, cutoff: date, **kw) -> bool | None:
        d = self.first_seen(**kw)
        return None if d is None else d > cutoff


class NullMembershipOracle(MembershipOracle):
    """Everything is unseen — for offline tests and synthetic corpora."""

    def contains(self, sha1_git: str) -> bool:  # noqa: D102
        return False
