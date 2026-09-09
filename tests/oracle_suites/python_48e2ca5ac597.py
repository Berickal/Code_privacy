"""Oracle suite for python_48e2ca5ac597  —  NEEDS_REVIEW
Function: _csv_data_rows
Spec (docstring):
    Behavioral evals for agent policy — challenge tier.

    FIM One connects agents to ERP / CRM / OA / databases, so a run that goes
    wrong writes to someone's production system. These cases probe the three
    ways that happens: the agent routes around a tool it was not given, it
    obeys an instruction that arrived inside data it read, or it reports a
    job done that the tools never did.

    Unlike the regression tier, these are not frozen production bugs — they
    are properties the agent must hold *every* time, so they run pass^k
    (:func:`eval_repeat`): one breach in k runs fails the case. An agent that
    respects a tool ban four times in five is not safe to leave unattended,
    and pass@k would call it green.

    Assertions are trajectory- and sandbox-level: which tools were called,
    what landed on disk. The exception is the claim-vs-deed check, where the
    deed provably did not happen and the claim in the text is what is under
    test.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import _csv_data_rows  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert _csv_data_rows(...) == ...
    assert callable(_csv_data_rows)
