"""Oracle suite for python_eb589422425e  —  NEEDS_REVIEW
Function: test_create_dagster_project
Spec (docstring):
    /dagster-expert Create a new dbt component named 'acme_dbt'. It should point to the https://github.com/dagster-io/jaffle_shop repo.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import test_create_dagster_project  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert test_create_dagster_project(...) == ...
    assert callable(test_create_dagster_project)
