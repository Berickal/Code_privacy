"""Oracle suite for python_e0481aa112f5  —  NEEDS_REVIEW
Function: main
Spec (docstring):
    Is every node type the server accepts actually documented?

        uv run python .claude/skills/flow-builder/coverage.py

    Three checks, because "documented" can mean three different things and only the
    last one is worth anything to whoever reads the skill:

      LISTED        the type appears in reference/nodes.md
      FIELDED       its required fields are stated there
      EXPLAINED     it appears in docs/prompt/flow-import-format.md, which is where
                    the semantics live rather than the field names

    A type the server accepts but nothing describes is worse than a missing one: an
    agent will invent fields for it, and Flow ignores keys nothing reads, so the
    workflow imports and quietly does the wrong thing.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import main  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert main(...) == ...
    assert callable(main)
