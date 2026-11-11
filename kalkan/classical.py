"""Stage 3 - character n-gram TF-IDF + Logistic Regression.

Char n-grams on the folded view survive agglutination and diacritic loss,
and the model scores in well under a millisecond on CPU.
"""
from __future__ import annotations

from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_union

from .normalize import normalize


def build_pipeline() -> Pipeline:
    features = make_union(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True, max_features=200_000),
        TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2, sublinear_tf=True),
    )
    clf = LogisticRegression(C=4.0, class_weight="balanced", max_iter=2000)
    return Pipeline([("features", features), ("clf", clf)])


class ClassicalModel:
    def __init__(self, pipeline: Pipeline):
        self.pipeline = pipeline

    @classmethod
    def train(cls, texts: list[str], labels: list[int]) -> "ClassicalModel":
        pipe = build_pipeline()
        pipe.fit([normalize(t).folded for t in texts], labels)
        return cls(pipe)

    def score(self, folded_texts: list[str]) -> list[float]:
        return self.pipeline.predict_proba(folded_texts)[:, 1].tolist()

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.pipeline, path)

    @classmethod
    def load(cls, path: str | Path) -> "ClassicalModel":
        return cls(joblib.load(path))
