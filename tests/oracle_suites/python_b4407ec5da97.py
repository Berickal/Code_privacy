"""Oracle suite for python_b4407ec5da97  —  NEEDS_REVIEW
Function: ensure_file
Spec (docstring):
    GFF/GTF predicate & projection pushdown regression harness.

    Validates polars_bio's `scan_gtf`/`scan_gff` pushdown against a real GENCODE
    annotation file, three ways, for every (predicate, projection) case:

      A = polars_bio, pushdown ON   (predicate_pushdown=projection_pushdown=True)
      B = polars_bio, pushdown OFF  (both False)  -> client-side filter/select only
      C = oxbow ground truth        (independent reader: read-all, filter in Polars)

    A case PASSES iff A == C and B == C as row sets (row order is also checked).
    This is the core correctness contract of the pushdown work (issue #396 / PR
    #407): pushdown is a pure optimization layered on top of a client-side filter
    that is the *source of truth*, so a translation bug may cost performance but
    must never change results. Comparing against oxbow (a separate Rust/Arrow
    GFF/GTF reader) guards against a bug that is wrong in the *same* way on both
    the ON and OFF polars_bio paths.

    It also times A vs B so you can see the optimization actually firing: a
    selective predicate should be markedly faster with pushdown on.

    Usage:
        python bench_pushdown.py [gtf] [gff3]          # default: gtf
        POLARS_BIO_GENCODE_DIR=/data python bench_pushdown.py gtf gff3

    Exit code is non-zero if any case fails, so this doubles as a CI check.
    Data files are downloaded once into the data dir if absent.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import ensure_file  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert ensure_file(...) == ...
    assert callable(ensure_file)
