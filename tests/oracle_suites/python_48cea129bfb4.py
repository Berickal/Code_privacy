"""Oracle suite for python_48cea129bfb4  —  NEEDS_REVIEW
Function: parse_requirements
Spec (docstring):
    Download cp312 manylinux wheels. Pure-Python sdists are wheeled on the builder.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import parse_requirements  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert parse_requirements(...) == ...
    assert callable(parse_requirements)
