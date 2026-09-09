"""RQ7: ecosystem-only license predictor (report Section 12.6).

Logistic regression on cues that need NO target-specific recall. The exposure-specific
license signal is (LLM accuracy on exposed) - (this baseline's accuracy).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict


@dataclass(frozen=True)
class LicenseBaselineResult:
    baseline_accuracy: float
    majority_class_rate: float
    per_class_accuracy: dict[str, float]

    def to_row(self) -> dict:
        d = asdict(self)
        d["per_class_accuracy"] = str(d["per_class_accuracy"])
        return d


class EcosystemFeaturizer:
    _IMPORT = re.compile(r"^\s*(?:import|from)\s+([\w.]+)", re.M)

    def features(self, *, file_path: str, source: str, language: str) -> dict:
        imports = {f"imp={i.split('.')[0]}": 1 for i in self._IMPORT.findall(source)}
        path_toks = {
            f"path={t}": 1 for t in re.split(r"[/_\-.]", file_path.lower()) if t
        }
        naming = {
            "snake_case": int(bool(re.search(r"def [a-z]+_[a-z]", source))),
            "camelCase": int(bool(re.search(r"def [a-z]+[A-Z]", source))),
            "lang": language,
        }
        return {**imports, **path_toks, **naming}


class LicenseBaseline:
    def __init__(self, seed: int = 0):
        self.seed = seed
        self.featurizer = EcosystemFeaturizer()

    def fit_predict(self, rows: pd.DataFrame) -> tuple[LicenseBaselineResult, np.ndarray]:
        """``rows`` columns: file_path, source, language, spdx_license."""
        feats = [
            self.featurizer.features(
                file_path=r.file_path, source=r.source, language=r.language
            )
            for r in rows.itertuples(index=False)
        ]
        X = DictVectorizer(sparse=True).fit_transform(feats)
        y = rows["spdx_license"].fillna("NOASSERTION").to_numpy()
        clf = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=self.seed)
        n_splits = min(5, int(pd.Series(y).value_counts().min()))
        pred = (
            cross_val_predict(clf, X, y, cv=n_splits)
            if n_splits >= 2
            else np.full_like(y, pd.Series(y).mode()[0])
        )
        acc = float((pred == y).mean())
        majority = float(pd.Series(y).value_counts(normalize=True).max())
        per_class = {
            c: float((pred[y == c] == c).mean()) for c in np.unique(y) if (y == c).any()
        }
        return LicenseBaselineResult(acc, majority, per_class), pred
