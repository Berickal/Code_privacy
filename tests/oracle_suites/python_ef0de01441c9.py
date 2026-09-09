"""Oracle suite for python_ef0de01441c9  —  NEEDS_REVIEW
Function: collect_slides
Spec (docstring):
    Predict spatial gene expression for a whole-slide H&E image with DeepSpot-M.

    Unlike ``predict.py`` (which scores pre-cut 224x224 tiles), this reads a
    whole-slide image, tiles it on a 224-px grid at native resolution, drops
    background tiles, predicts expression per tile, and writes a spatial AnnData
    (``.h5ad``) with one row per tile — the same format as the TCGA virtual spatial
    transcriptomics atlas, ready for scanpy / squidpy.

    Tiles are cut at the slide's native pixel resolution, so the input should be a
    ~20x H&E whole-slide image (the magnification DeepSpot-M was trained on).

    Needs ``pyvips`` (libvips) and ``anndata`` in addition to the core deps:
        pip install pyvips anndata

    Examples:
      # one slide -> one .h5ad (full ~19k-gene panel)
      python examples/predict_wsi.py slide.svs -o slide.h5ad

      # a folder of slides -> one .h5ad each in out/, scoring three marker genes
      python examples/predict_wsi.py slides/ -o out/ --genes EPCAM CD3D PTPRC

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import collect_slides  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert collect_slides(...) == ...
    assert callable(collect_slides)
