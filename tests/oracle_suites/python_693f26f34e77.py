"""Oracle suite for python_693f26f34e77  —  NEEDS_REVIEW
Function: first_word
Spec (docstring):
    Lint a SciAgent-Skills `description` field.

    Used both by `scaffold.py` (programmatic check) and as a standalone CLI for
    authors who want to test a description before scaffolding.

    Rules enforced (mirrors AGENTS.md Step 5 "Description writing rules"):

    1. Length: hard ceiling 1024 chars (also enforced by tests/test_skill_quality.py).
    2. First-120-char keyword carrier: the first word must NOT be a stop verb
       (`Use`, `A`, `An`, `The`, `Query`, `Fetch`, `Run`). Leading with the tool
       or domain name is the goal.
    3. No promotional adjectives (`powerful`, `comprehensive`, `state-of-the-art`,
       `cutting-edge`). These waste tokens and add no discovery signal.
    4. Description must not start with `>` (YAML block scalar) — keep it inline
       for grep/search consistency.

    Usage:
        # CLI form
        python validate_description.py "MyTool short-form description..."

        # Importable
        from validate_description import check
        errors = check(description_text)

    Exit codes (CLI):
        0  description passes
        1  one or more rule violations (printed to stderr)

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import first_word  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert first_word(...) == ...
    assert callable(first_word)
