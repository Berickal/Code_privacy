"""Oracle suite for python_00ca747b7a41  —  NEEDS_REVIEW
Function: find_abandoned
Spec (docstring):
    Identify abandoned-cart sessions.

    A session counts as abandoned when:

    * It has **at least one ``ADD_TO_CART``** (the buyer expressed
      intent), and
    * It did **not** complete checkout, and
    * The net cart value is **above** ``min_cart_vnd`` (default 50,000 VND
      — VN marketplaces typically don't run recovery for ≤ ₫50k carts
      since campaign cost > expected revenue).

    Sessions that **explicitly abandoned** (the buyer hit
    ``ABANDON_CHECKOUT`` — closed the checkout drawer) are still counted
    — most CRM teams chase them as the highest-intent cohort. Production
    callers can split into two classes (explicit vs implicit timeout)
    via the returned :class:`AbandonedSession`'s ``reason`` field.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import find_abandoned  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert find_abandoned(...) == ...
    assert callable(find_abandoned)
