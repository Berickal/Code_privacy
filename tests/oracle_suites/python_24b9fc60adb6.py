"""Oracle suite for python_24b9fc60adb6  —  NEEDS_REVIEW
Function: _kernel_dir
Spec (docstring):
    One-shot bootstrap for missing PFC command JSON files.

    Generates skeleton JSON files for commands that are present in installed
    PFC HTML documentation (6.0 / 7.0 / 9.0) but not yet captured in the
    repository's `commands/` tree. Two cases are handled:

    * Partial scopes (existing JSON dir, missing some commands):
        model, contact, fragment

    * New scopes (no JSON dir yet):
        program, history, fish

    For each missing command, the script parses the HTML in all three PFC
    versions and writes a complete file matching the existing schema:
        {
          "category": <scope>,
          "search_keywords": [...],
          "description": <from 7.0 HTML>,
          "notes": [],
          "python_sdk_alternative": {"available": false, "workaround": ""},
          "versions": {"6.0": {...}, "7.0": {...}, "9.0": {...}}
        }

    After running this script, run `generate_index.py` to refresh `index.json`.

    Usage:
        uv run python src/itasca_mcp/knowledge/resources/command_docs/bootstrap_missing.py

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import _kernel_dir  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert _kernel_dir(...) == ...
    assert callable(_kernel_dir)
