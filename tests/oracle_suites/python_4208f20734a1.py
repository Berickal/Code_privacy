"""Oracle suite for python_4208f20734a1  —  NEEDS_REVIEW
Function: normalize_seq
Spec (docstring):
    Uppercase, remove spaces, and (optionally) map non-20AA to X.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import normalize_seq  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert normalize_seq(...) == ...
    assert callable(normalize_seq)
