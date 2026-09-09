"""Oracle suite for python_ca8639db5ee2  —  NEEDS_REVIEW
Function: _is_port
Spec (docstring):
    Dump the laid-out geometry of a .mmd so a reported defect can be confirmed.

    `probe_layout.py` answers "did anything trip a check?". This answers "where is
    everything?" - the coordinates you need to turn an eyeballed report ("section 2
    content is pulled too low", "that input floats too high") into a quantified,
    credible bug ("`al_minimap` y=392 vs the trunk at y=216.8, a 175px drag").

    For each section it prints the bbox extents and every station's (x, y) with a
    PORT / OFF(-track) tag, then a few derived red flags:
      - stations that sit off their section's trunk (modal y of non-port stations)
      - off-track inputs/outputs more than ~one row from their nearest neighbour
      - the inter-section gaps between vertically-stacked sections

    Usage:
        python inspect_layout.py INPUT.mmd

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import _is_port  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert _is_port(...) == ...
    assert callable(_is_port)
