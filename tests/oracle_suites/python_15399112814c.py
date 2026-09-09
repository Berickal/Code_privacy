"""Oracle suite for python_15399112814c  —  NEEDS_REVIEW
Function: parse_frontmatter
Spec (docstring):
    Validate registry.yaml: check all entries point to existing SKILL.md files
    with valid YAML frontmatter.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import parse_frontmatter  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert parse_frontmatter(...) == ...
    assert callable(parse_frontmatter)
