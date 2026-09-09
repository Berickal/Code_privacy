"""Oracle suite for python_b4c71980a679  —  NEEDS_REVIEW
Function: setup
Spec (docstring):
    .. |project| replace:: {project}

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import setup  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert setup(...) == ...
    assert callable(setup)
