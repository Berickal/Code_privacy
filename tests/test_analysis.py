import numpy as np
import pandas as pd

from exposure_gap.analysis import (
    DoseResponseAnalyzer,
    FDRCorrector,
    GapEstimator,
    InteractionAnalyzer,
)


def _predictions(delta: float, n_pairs: int = 40, k: int = 25, prompt: str = "P1a") -> pd.DataFrame:
    rng = np.random.default_rng(0)
    rows = []
    for p in range(n_pairs):
        base = rng.uniform(0.3, 0.6)
        rows.append(dict(task="reproduction", model="m", k=k, prompt_strategy=prompt,
                         split="E", matched_pair_id=f"pair_{p}",
                         lexical_f1=base + delta + rng.normal(0, 0.05)))
        rows.append(dict(task="reproduction", model="m", k=k, prompt_strategy=prompt,
                         split="U", matched_pair_id=f"pair_{p}",
                         lexical_f1=base + rng.normal(0, 0.05)))
    return pd.DataFrame(rows)


def test_gap_positive_detected():
    est = GapEstimator(n_bootstrap=2000, seed=0)
    res = est.estimate(_predictions(0.2), task="reproduction", metric="lexical_f1",
                       model="m", k=25, prompt="P1a")
    assert res.delta > 0.15
    assert res.ci_low > 0
    assert res.n_pairs == 40


def test_gap_zero_ci_contains_zero():
    est = GapEstimator(n_bootstrap=2000, seed=0)
    res = est.estimate(_predictions(0.0), task="reproduction", metric="lexical_f1",
                       model="m", k=25, prompt="P1a")
    assert res.ci_low < 0 < res.ci_high


def test_fdr_monotone_and_bounded():
    p = np.array([0.001, 0.01, 0.2, 0.5, np.nan])
    adj = FDRCorrector(0.05).adjust(p)
    assert np.nanmax(adj) <= 1.0
    assert np.isnan(adj[-1])
    assert adj[0] <= adj[1] <= adj[2]


def test_interaction_relative_to_baseline():
    gaps = pd.DataFrame([
        dict(task="t", metric="lexical_f1", model="m", k=25, prompt="P1a", delta=0.1),
        dict(task="t", metric="lexical_f1", model="m", k=25, prompt="P4b", delta=0.25),
    ])
    out = InteractionAnalyzer(baseline="P1a").table(gaps)
    assert out.set_index("prompt").loc["P4b", "interaction"] == 0.15


def test_analysis_pipeline_end_to_end(tmp_path):
    from exposure_gap.analysis import AnalysisPipeline

    frames = []
    for k in (0, 1, 5, 25):
        f = _predictions(0.02 * k, k=k)
        f["dataflow_sim"] = f["lexical_f1"] + 0.01
        f["ast_edit_distance"] = f["lexical_f1"] - 0.01
        frames.append(f)
    preds = pd.concat(frames, ignore_index=True)
    art = AnalysisPipeline().run(preds, tmp_path / "m")
    assert (tmp_path / "m" / "gaps.csv").exists()
    assert (tmp_path / "m" / "convergence.csv").exists()      # regression: merge collision
    assert not art.gaps.empty
    assert (art.gaps["metric"].nunique()) == 3


def test_dose_response_trend():
    preds = pd.concat([
        _predictions(0.05, k=1), _predictions(0.15, k=5), _predictions(0.3, k=25)
    ])
    dr = DoseResponseAnalyzer().table(preds, ["lexical_f1"])
    row = dr.iloc[0]
    assert row["mean_delta_k1"] < row["mean_delta_k5"] < row["mean_delta_k25"]
    assert row["jt_p_value"] < 0.05
