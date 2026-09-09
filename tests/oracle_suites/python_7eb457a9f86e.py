"""Oracle suite for python_7eb457a9f86e  —  NEEDS_REVIEW
Function: as_repo_relative_path
Spec (docstring):
    Return a portable repo-relative path for saved artifacts.

        This prevents JSON artifacts from containing local absolute paths such as:
        C:\\Users\\Amir\\Desktop\\...

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import as_repo_relative_path  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert as_repo_relative_path(...) == ...
    assert callable(as_repo_relative_path)
