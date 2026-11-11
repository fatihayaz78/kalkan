"""Detection pipeline: runs stages in order until one decides; otherwise the policy decides."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Sequence

from ..domain.models import Decision, NormalizedText, Policy, Verdict
from ..domain.ports import DetectionStage, Normalizer


@dataclass(frozen=True)
class _Context:
    text: str
    normalized: NormalizedText
    policy: Policy


class DetectionPipeline:
    def __init__(self, normalizer: Normalizer, stages: Sequence[DetectionStage], version: str | None = None):
        self._normalizer = normalizer
        self._stages = list(stages)
        self.version = version

    @property
    def stage_names(self) -> list[str]:
        return [s.name for s in self._stages]

    def run(self, text: str, policy: Policy | None = None) -> Verdict:
        t0 = time.perf_counter()
        ctx = _Context(text, self._normalizer.normalize(text), policy or Policy())
        trace: list[dict] = [{"stage": "normaliser", "result": "done"}]
        score, last_stage, rule, decision = 0.0, "rules", None, None

        for stage in self._stages:
            r = stage.evaluate(ctx)
            trace.append(r.as_trace())
            if r.score is not None:
                score, last_stage = r.score, r.stage
            if r.decision is not None:
                decision, last_stage, rule = r.decision, r.stage, r.rule
                break

        if decision is None:
            has_scorer = any(t.get("score") is not None for t in trace)
            decision = ctx.policy.decide(score) if has_scorer else Decision.ALLOW
        return Verdict(decision, round(float(score), 4), last_stage, rule,
                       round((time.perf_counter() - t0) * 1000, 2), self.version, tuple(trace),
                       ctx.normalized.folded)
