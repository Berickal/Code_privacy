"""Oracle suite for python_e1880f422341  —  NEEDS_REVIEW
Function: _build_parser
Spec (docstring):
    CLI entry point: ``python -m docs.screenshots [list] [--only N] [--stack] [--agentic]``.

    Default (no command, no flags) captures only the ``standalone_interface`` static
    recipes — zero container, CI-safe locally. ``--stack`` opts into the
    tutorial-stack recipes (needs a container runtime + the port layout's free
    postgres port); ``--agentic`` opts into the live web-terminal hero (needs a live
    Claude session). ``list`` prints the registry without capturing anything.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import _build_parser  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert _build_parser(...) == ...
    assert callable(_build_parser)
