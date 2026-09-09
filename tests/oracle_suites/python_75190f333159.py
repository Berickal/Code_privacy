"""Oracle suite for python_75190f333159  —  NEEDS_REVIEW
Function: clocks_only
Spec (docstring):
    Vivado IP example: a ``blk_mem_gen`` instance wrapped by ``bram_wrap.sv``.

    Shows ``VivadoIp`` end to end. The XCI is *generated* by the
    ``builder_tcl`` hook (``ip/blk_mem_kilobyte/regen.tcl``) on first build,
    so this example carries no Vivado-version-locked XCI — it works on any
    Vivado that has the ``blk_mem_gen`` IP.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import clocks_only  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert clocks_only(...) == ...
    assert callable(clocks_only)
