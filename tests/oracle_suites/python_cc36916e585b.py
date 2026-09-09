"""Oracle suite for python_cc36916e585b  —  NEEDS_REVIEW
Function: classify_error
Spec (docstring):
    Account error classification for failover logic.

    Classifies Kiro API errors into two categories:
    - FATAL: Error in the request itself → return to client immediately
    - RECOVERABLE: Error with the account → try next account

    This enables intelligent failover that doesn't waste time retrying
    requests that will fail on all accounts.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import classify_error  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert classify_error(...) == ...
    assert callable(classify_error)
