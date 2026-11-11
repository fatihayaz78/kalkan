"""The Kalkan engine: normaliser -> rules -> TF-IDF+LR -> (transformer) -> decision.

Pure library: no web or storage dependencies, so it can be embedded in-process
or served by kalkan.service.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .classical import ClassicalModel
from .normalize import normalize
from .registry import ModelRegistry
from .rules import check_rules
from .transformer import TransformerModel

DEFAULT_POLICY = {
    "classical_allow_below": 0.15,  # stage 3 lets confidently benign input through
    "flag_at": 0.50,
    "block_at": 0.80,
}


@dataclass
class Verdict:
    decision: str          # allow | flag | block
    score: float
    stage: str             # rules | classical | transformer
    matched_rule: str | None
    latency_ms: float
    model_version: str | None = None
    trace: list[dict] = field(default_factory=list)
    normalized: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class Kalkan:
    """Detection engine bound to one model version."""

    def __init__(self, model_dir: str | Path | None = None, version: str | None = None):
        self.version = version
        d = Path(model_dir) if model_dir else None
        cpath = d / "classical.joblib" if d else None
        self.classical = ClassicalModel.load(cpath) if cpath and cpath.exists() else None
        self.transformer = TransformerModel.try_load(d / "berturk") if d else None

    @classmethod
    def from_registry(cls, root: str | Path = "models", version: str | None = None) -> "Kalkan":
        reg = ModelRegistry(root)
        v = version or reg.active()
        return cls(reg.path(v) if v else None, v)

    @staticmethod
    def _decide(score: float, policy: dict) -> str:
        if score >= policy["block_at"]:
            return "block"
        if score >= policy["flag_at"]:
            return "flag"
        return "allow"

    def check(self, text: str, policy: dict | None = None) -> Verdict:
        pol = {**DEFAULT_POLICY, **(policy or {})}
        t0 = time.perf_counter()
        trace: list[dict] = []
        norm = normalize(text)
        trace.append({"stage": "normaliser", "result": "done"})

        rule = check_rules(norm.folded, text)
        trace.append({"stage": "rules", "result": rule.rule or "no match", "decoded_from": rule.decoded_from})
        if rule.matched:
            return self._finish(t0, "block", 1.0, "rules", rule.rule, trace, norm.folded)

        if self.classical is None:
            trace.append({"stage": "classical", "result": "no model loaded"})
            return self._finish(t0, "allow", 0.0, "rules", None, trace, norm.folded)

        p = self.classical.score([norm.folded])[0]
        trace.append({"stage": "classical", "score": round(p, 4)})
        if p < pol["classical_allow_below"]:
            return self._finish(t0, "allow", p, "classical", None, trace, norm.folded)
        if self.transformer is None:
            return self._finish(t0, self._decide(p, pol), p, "classical", None, trace, norm.folded)

        p = self.transformer.score(text)
        trace.append({"stage": "transformer", "score": round(p, 4)})
        return self._finish(t0, self._decide(p, pol), p, "transformer", None, trace, norm.folded)

    def _finish(self, t0, decision, score, stage, rule, trace, folded) -> Verdict:
        return Verdict(decision, round(float(score), 4), stage, rule,
                       round((time.perf_counter() - t0) * 1000, 2), self.version, trace, folded)
