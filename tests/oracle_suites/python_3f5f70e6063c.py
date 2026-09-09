"""Oracle suite for python_3f5f70e6063c  —  NEEDS_REVIEW
Function: hr_to_rr_intervals_ms
Spec (docstring):
    Convert raw HR (bpm) measurements to RR intervals in milliseconds.

        Args:
            hr_series: Heart rate values in beats per minute.

        Returns:
            Array of RR intervals in milliseconds, with non-positive and non-finite values removed.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import hr_to_rr_intervals_ms  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert hr_to_rr_intervals_ms(...) == ...
    assert callable(hr_to_rr_intervals_ms)
