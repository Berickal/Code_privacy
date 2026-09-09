"""Oracle suite for python_eb4a23019a62  —  NEEDS_REVIEW
Function: _events
Spec (docstring):
    How the dynamics passes scale.

    `retention`, `missingness`, `late_arrivals`, `time_grids` and `duplicates` all
    run *after* generation and rewrite whole tables. That is the right design for
    exactness, and it also means nobody had measured what it costs. This measures
    it, at sizes people actually use, and prints the per-row cost so a regression
    shows up as a number rather than a feeling.

        python -m benchmarks.bench_dynamics            # 100k, 1M
        python -m benchmarks.bench_dynamics --big      # adds 10M

    Every figure is measured on the run that prints it. Nothing here is a target.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import _events  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert _events(...) == ...
    assert callable(_events)
