"""Character n-gram TF-IDF + Logistic Regression (scikit-learn adapter).

Char n-grams on the folded view survive Turkish suffixes and missing diacritics;
scoring takes well under a millisecond on CPU.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_union

FILENAME = "classical.joblib"


class TfidfClassifier:
    """Implements TrainableClassifier. Expects already-normalised (folded) text."""

    def __init__(self, pipeline: Pipeline | None = None):
        self._pipe = pipeline or self._build()

    @staticmethod
    def _build() -> Pipeline:
        features = make_union(
            TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True, max_features=200_000),
            TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2, sublinear_tf=True),
        )
        return Pipeline([("features", features),
                         ("clf", LogisticRegression(C=4.0, class_weight="balanced", max_iter=2000))])

    def fit(self, texts: Sequence[str], labels: Sequence[int]) -> "TfidfClassifier":
        self._pipe.fit(list(texts), list(labels))
        return self

    def score(self, texts: Sequence[str]) -> list[float]:
        return self._pipe.predict_proba(list(texts))[:, 1].tolist()

    def save(self, directory: Path) -> None:
        Path(directory).mkdir(parents=True, exist_ok=True)
        joblib.dump(self._pipe, Path(directory) / FILENAME)

    @classmethod
    def exists(cls, directory: Path) -> bool:
        return (Path(directory) / FILENAME).exists()

    @classmethod
    def load(cls, directory: Path) -> "TfidfClassifier":
        return cls(joblib.load(Path(directory) / FILENAME))
