"""Oracle suite for python_03a5cd0bf9b6  —  NEEDS_REVIEW
Function: _get_tags
Spec (docstring):
    Select which git tags to include in the versioned docs build.

    Strategy
    --------
    * For the current release major (highest major present), include the latest
      patch release for the last 5 minor series.
    * For major ``0``, include the latest patch for every minor from the current
      minor down to ``0.12`` (inclusive), not capped at five minors.
    * Also include the latest available release for each of the last 3 major
      versions.

    The selected tags are printed as JSON by default so they can be consumed by
    other scripts. A regex mode is still provided for compatibility.

    Usage
    -----
        python docs/scripts/select_versions.py
        python docs/scripts/select_versions.py --format regex

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import _get_tags  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert _get_tags(...) == ...
    assert callable(_get_tags)
