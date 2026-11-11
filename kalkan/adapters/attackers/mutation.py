"""Offline attack generator: mutates seeds with the training transforms only,
so the held-out evasion split stays untouched."""
from __future__ import annotations

import random

from ...detection.evasion import TRAIN_TRANSFORMS, augment


class MutationAttacker:
    def __init__(self, seed: int = 0):
        self._rng = random.Random(seed)

    def variants(self, attack: str, n: int) -> list[str]:
        return augment(attack, TRAIN_TRANSFORMS, n, self._rng)
