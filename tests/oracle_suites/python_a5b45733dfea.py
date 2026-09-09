"""Oracle suite for python_a5b45733dfea  —  NEEDS_REVIEW
Function: is_roundup_article
Spec (docstring):
    Whether an article carries enough scraped content to count as its
        outlet's independent corroboration of a story.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import is_roundup_article  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert is_roundup_article(...) == ...
    assert callable(is_roundup_article)
