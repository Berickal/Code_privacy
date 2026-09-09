from exposure_gap.corpus.collect import DomainClassifier


def test_classifier_weights_topics_and_name():
    c = DomainClassifier()
    assert c.classify("a small project", ["fastapi", "rest-api"], "acme/user-service") == "web_backend"
    assert c.classify(None, ["etl", "airflow"], "x/pipeline") == "data_engineering"
    assert c.classify("PDE solver with finite elements", None, "y/fem-solver") == "scientific_computing"
    assert c.classify("my cool cli tool", [], "z/awesome-list") == "unknown"


def test_min_functions_filter(synthetic):
    # synthetic files all have >= 0 functions; the transform_/scale_ ones have a body
    from exposure_gap.config import CorpusConfig
    from exposure_gap.corpus import CorpusBuilder, SourcererCCRunner
    from exposure_gap.oracle import NullMembershipOracle

    cfg = CorpusConfig(languages=["python"], min_functions=1)
    cfg.gate1.min_matched_pairs_per_language = 1
    report = CorpusBuilder(
        cfg, synthetic["store"], NullMembershipOracle(), None,
        SourcererCCRunner(type2_threshold=2.0),
    ).run(
        forced_pairs=synthetic["syn"].forced_pairs(synthetic["exposed"], synthetic["unexposed"]),
        forced_holdout={f.file_id for f in synthetic["holdout"]},
    )
    meta = synthetic["store"].read_metadata()
    assert (meta["n_functions"] >= 1).all()
    assert report.n_pairs >= 1
