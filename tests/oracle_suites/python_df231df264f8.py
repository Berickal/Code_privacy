"""Oracle suite for python_df231df264f8  —  NEEDS_REVIEW
Function: read_ids
Spec (docstring):
    extract_cds_by_ids.py

    Extract selected CDS sequences from a FASTA file.

    Inputs:
      --cds  all CDS FASTA
      --ids  one sequence ID per line
      --out  output FASTA

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import read_ids  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert read_ids(...) == ...
    assert callable(read_ids)
