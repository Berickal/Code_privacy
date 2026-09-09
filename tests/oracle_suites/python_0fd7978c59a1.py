"""Oracle suite for python_0fd7978c59a1  —  NEEDS_REVIEW
Function: is_registered_dataset
Spec (docstring):
    Resolution of a config value that is either a registered dataset name or a local path.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import is_registered_dataset  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert is_registered_dataset(...) == ...
    assert callable(is_registered_dataset)
