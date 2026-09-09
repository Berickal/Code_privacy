"""Oracle suite for python_45f163c2cf3f  —  NEEDS_REVIEW
Function: lifespan
Spec (docstring):
    (no docstring)

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import lifespan  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert lifespan(...) == ...
    assert callable(lifespan)
