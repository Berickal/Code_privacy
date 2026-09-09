"""Oracle suite for python_462fcc9610f5  —  NEEDS_REVIEW
Function: backoff
Spec (docstring):
    (no docstring)

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import backoff  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert backoff(...) == ...
    assert callable(backoff)
