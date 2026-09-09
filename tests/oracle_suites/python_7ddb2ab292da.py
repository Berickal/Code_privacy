"""Oracle suite for python_7ddb2ab292da  —  NEEDS_REVIEW
Function: read_targets
Spec (docstring):
    filter_collinearity_targets.py

    Filter target-related collinear gene pairs from an MCScanX .collinearity file.

    Inputs:
      --collinearity  MCScanX .collinearity file
      --gff           MCScanX 4-column GFF: chromosome/scaffold gene_id start end
      --targets       one target ID per line

    Outputs:
      <out_prefix>_pairs.tsv
      <out_prefix>_summary.tsv

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import read_targets  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert read_targets(...) == ...
    assert callable(read_targets)
