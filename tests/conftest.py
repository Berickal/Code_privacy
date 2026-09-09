import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from exposure_gap.corpus import CorpusStore, SyntheticCorpus


@pytest.fixture
def synthetic(tmp_path):
    store = CorpusStore(tmp_path / "corpus")
    syn = SyntheticCorpus(seed=0)
    exposed, unexposed, holdout = syn.populate_store(store, n_pairs=6, n_holdout=3)
    return {
        "store": store,
        "syn": syn,
        "exposed": exposed,
        "unexposed": unexposed,
        "holdout": holdout,
        "root": tmp_path,
    }
