"""Oracle suite for python_510e22e783b1  —  NEEDS_REVIEW
Function: get_example_notebooks
Spec (docstring):
    Get all .ipynb files from the examples directory.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import get_example_notebooks  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert get_example_notebooks(...) == ...
    assert callable(get_example_notebooks)
