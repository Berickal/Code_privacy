"""Oracle suite for python_5c181595f0fa  —  NEEDS_REVIEW
Function: task_dir
Spec (docstring):
    Shared fixtures for the zyme test suite.

    Most tests need a temporary directory that looks like a zyme task: a
    task.yaml + a results.tsv + a .zyme/ state dir. Building these by hand
    in every test is noisy, so we centralize the scaffolding here.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import task_dir  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert task_dir(...) == ...
    assert callable(task_dir)
