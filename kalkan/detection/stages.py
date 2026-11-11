"""Detection stages (Chain of Responsibility links).

Each stage either decides (allow/flag/block) or passes with a score. Stages
depend on ports, not concrete models, so any classifier can be plugged in.
"""
from __future__ import annotations

from typing import Callable

from ..domain.models import Decision, NormalizedText, StageResult
from ..domain.ports import DetectionContext, TextClassifier
from .rules import RuleSet

TextView = Callable[[NormalizedText], str]
FOLDED: TextView = lambda n: n.folded       # noqa: E731
ORIGINAL: TextView = lambda n: n.original   # noqa: E731


class RuleStage:
    """Blocks on a rule hit; never allows on its own."""
    name = "rules"

    def __init__(self, rules: RuleSet):
        self._rules = rules

    def evaluate(self, ctx: DetectionContext) -> StageResult:
        m = self._rules.match(ctx.normalized.folded, ctx.text)
        if m.matched:
            return StageResult(self.name, Decision.BLOCK, 1.0, m.rule, {"decoded_from": m.decoded_from})
        return StageResult(self.name, detail={"result": "no match"})


class ScreeningStage:
    """Cheap classifier: allows confidently benign input, otherwise passes its score on."""

    def __init__(self, name: str, classifier: TextClassifier, view: TextView = FOLDED):
        self.name, self._clf, self._view = name, classifier, view

    def evaluate(self, ctx: DetectionContext) -> StageResult:
        p = self._clf.score([self._view(ctx.normalized)])[0]
        decision = Decision.ALLOW if p < ctx.policy.classical_allow_below else None
        return StageResult(self.name, decision, p)


class ScoringStage:
    """Final classifier: contributes the score the policy decides on."""

    def __init__(self, name: str, classifier: TextClassifier, view: TextView = ORIGINAL):
        self.name, self._clf, self._view = name, classifier, view

    def evaluate(self, ctx: DetectionContext) -> StageResult:
        return StageResult(self.name, None, self._clf.score([self._view(ctx.normalized)])[0])
