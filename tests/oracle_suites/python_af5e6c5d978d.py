"""Oracle suite for python_af5e6c5d978d  —  NEEDS_REVIEW
Function: _command_name
Spec (docstring):
    Extract real figure references from the Itasca command HTML (build-time).

    `flag_figure_defined.py` v1 keyed off text phrases ("refer to the figures
    above"), which both under-catches (figure-defined commands worded differently)
    and gives no actual link to the figure. This tool replaces that signal with the
    ground truth: the `<img>` / thumbnail markup in the source HTML that the text
    corpus dropped.

    It walks the local Itasca documentation tree, and for every command page
    (`cmd_*.html`) records the command name (from the page `<h1>`) and the
    real reference figures it embeds (the `_images/*.png|svg|gif` it links, minus
    `_static` logos, math/equation images, and `thumb_` duplicates). Each figure
    path is verified to exist on disk.

    Output is a committed, machine-independent manifest
    (`scripts/corpus/figure_manifest.json`) mapping

        "<command name>": [ {"name": "sector-quad.png", "doc_path": "_images/sector-quad.png"}, ... ]

    `flag_figure_defined.py` then consumes this manifest with NO dependency on a
    local install, so the flag-application pass (and its CI freshness check) runs
    anywhere. This tool is the install-dependent half; re-run it when regenerating
    the corpus against a new engine release (mirrors `parse_pfc*.py`).

    Usage:
        uv run python scripts/corpus/extract_figure_refs.py
        uv run python scripts/corpus/extract_figure_refs.py --doc-root "C:/Program Files/Itasca/PFC700/exe64/doc"

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import _command_name  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert _command_name(...) == ...
    assert callable(_command_name)
