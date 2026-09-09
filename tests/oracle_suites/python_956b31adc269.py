"""Oracle suite for python_956b31adc269  —  NEEDS_REVIEW
Function: _assert_no_banned_purple
Spec (docstring):
    Behavioral evals for deliverable handling — regression tier.

    Both cases replay a production failure from a 2026-07-05 user session
    (see evals/README.md).  Assertions target the trajectory and the sandbox,
    not the answer text — with one deliberate exception: the claim-vs-deed
    check, where the *claim* in the text is exactly what is under test.

    Tier: ``regression``, so these run pass@k (``eval_retry``) — the question
    is whether the fixed behavior is still reachable, not whether it holds on
    every single sample.  Policy probes are the other tier; see
    ``test_policy_behavior.py``.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import _assert_no_banned_purple  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert _assert_no_banned_purple(...) == ...
    assert callable(_assert_no_banned_purple)
