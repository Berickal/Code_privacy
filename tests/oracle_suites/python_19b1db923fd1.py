"""Oracle suite for python_19b1db923fd1  —  NEEDS_REVIEW
Function: pivot_delta
Spec (docstring):
    SELECT s.region, p.category AS dim_value, d.year_month, SUM(f.net_sales) AS rev
    FROM {FACT_SALES} f
    JOIN {DIM_STORE} s   ON f.store_key = s.store_key
    JOIN {DIM_PRODUCT} p ON f.product_key = p.product_key
    JOIN {DIM_DATE} d    ON f.date_key = d.date_key
    WHERE d.year_month IN ('{CURRENT_YEAR_MONTH}', '{PRIOR_YEAR_MONTH}')
    GROUP BY s.region, p.category, d.year_month

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import pivot_delta  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert pivot_delta(...) == ...
    assert callable(pivot_delta)
