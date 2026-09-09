"""Oracle suite for python_a74538e5f7fa  —  NEEDS_REVIEW
Function: pytest_ignore_collect
Spec (docstring):
    Skip alpagym in generic CI root pytest runs.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import pytest_ignore_collect  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert pytest_ignore_collect(...) == ...
    assert callable(pytest_ignore_collect)
