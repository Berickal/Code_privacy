from exposure_gap.config import CorpusConfig, MatchingTolerances
from exposure_gap.corpus import (
    CorpusBuilder,
    FeatureExtractor,
    LocalHashDeduper,
    PairMatcher,
    SourcererCCRunner,
)
from exposure_gap.oracle import NullMembershipOracle
from exposure_gap.schema import FileFeatures


def test_feature_extractor_python():
    src = 'def f(a, b):\n    """doc"""\n    if a:\n        return a\n    return b\n'
    feats = FeatureExtractor().extract("x", src, "python", "web_backend")
    assert feats.n_functions == 1
    assert feats.has_docstring
    assert feats.cyclomatic >= 2


def test_pair_matcher_respects_tolerances():
    base = FileFeatures("a", "python", "d", loc=100, cyclomatic=5, n_functions=3, has_docstring=True)
    near = FileFeatures("b", "python", "d", loc=110, cyclomatic=6, n_functions=3, has_docstring=True)
    far = FileFeatures("c", "python", "d", loc=400, cyclomatic=20, n_functions=9, has_docstring=True)
    pairs = PairMatcher(MatchingTolerances(), seed=0).match([base, near, far])
    assert len(pairs) == 1
    assert {pairs[0].exposed_id, pairs[0].unexposed_id} == {"a", "b"}


def test_local_hash_deduper_flags_cross_repo_duplicates():
    recs = [("f1", "h1", "repoA"), ("f2", "h1", "repoB"), ("f3", "h2", "repoA")]
    assert LocalHashDeduper().clone_ids(recs) == {"f1", "f2"}


def test_sourcerercc_shingle_approx_separates_distinct_files():
    near = "def a(x):\n    y = x + 1\n    z = y * 2\n    return z\n"
    near2 = "def a(x):\n    y = x + 1\n    z = y * 2\n    return z  # copy\n"
    distinct = "def totally_different(items):\n    return {k: len(v) for k, v in items.items()}\n"
    langs = {"near": "python", "near2": "python", "distinct": "python"}
    clones = SourcererCCRunner(type2_threshold=0.7).clone_ids(
        {"near": near, "near2": near2, "distinct": distinct}, langs
    )
    assert clones == {"near", "near2"}


def test_corpus_builder_forced_split(synthetic):
    cfg = CorpusConfig(languages=["python"])
    cfg.gate1.min_matched_pairs_per_language = 3
    builder = CorpusBuilder(
        cfg,
        synthetic["store"],
        NullMembershipOracle(),
        None,
        SourcererCCRunner(type2_threshold=2.0),
    )
    report = builder.run(
        forced_pairs=synthetic["syn"].forced_pairs(synthetic["exposed"], synthetic["unexposed"]),
        forced_holdout={f.file_id for f in synthetic["holdout"]},
    )
    assert report.n_pairs == 6
    assert report.gate1_pass
    meta = synthetic["store"].read_metadata()
    assert set(meta["split"]) == {"E", "U", "H"}
    # every exposed row is paired with exactly one unexposed row
    pair_counts = meta[meta.split.isin(["E", "U"])].groupby("matched_pair_id").size()
    assert (pair_counts == 2).all()
