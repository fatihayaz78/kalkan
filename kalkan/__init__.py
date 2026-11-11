"""Kalkan - Turkish prompt-injection detection (core library)."""
from .cascade import DEFAULT_POLICY, Kalkan, Verdict
from .registry import ModelRegistry

__all__ = ["Kalkan", "Verdict", "ModelRegistry", "DEFAULT_POLICY", "check"]
__version__ = "0.2.0"

_default: Kalkan | None = None


def check(text: str) -> Verdict:
    """In-process use: kalkan.check("...") with the active model from ./models."""
    global _default
    if _default is None:
        _default = Kalkan.from_registry()
    return _default.check(text)
