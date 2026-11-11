"""Turkish-aware text normalisation (stage 1).

Produces several views of the input so later stages are robust to diacritic
stripping, casing tricks, homoglyphs, zero-width characters, leetspeak and
letter spacing.
"""
from __future__ import annotations

import re
import unicodedata

from ..domain.models import NormalizedText

ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad\u180e"), None)

# Cyrillic / Greek look-alikes folded to Latin.
HOMOGLYPHS = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
    "і": "i", "ј": "j", "ѕ": "s", "к": "k", "м": "m", "т": "t", "н": "h",
    "А": "A", "Е": "E", "О": "O", "Р": "P", "С": "C", "Х": "X", "У": "Y",
    "І": "I", "К": "K", "М": "M", "Т": "T", "Н": "H", "В": "B",
    "α": "a", "ο": "o", "ρ": "p", "ε": "e", "ι": "i", "κ": "k", "ν": "v",
    "Α": "A", "Ο": "O", "Ρ": "P", "Ε": "E", "Ι": "I", "Κ": "K", "Ν": "N",
})
DIACRITICS = str.maketrans("çğıöşüâîû", "cgiosuaiu")
LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i"})

_SPACED = re.compile(r"\b(?:\w[ .\-_*]){3,}\w\b")
_LEET_WORD = re.compile(r"\b(?=\w*[a-z])[\w@$!]+\b")
_WS = re.compile(r"\s+")


def turkish_lower(text: str) -> str:
    """Lowercase with Turkish dotted/dotless I rules (I->ı, İ->i)."""
    return text.replace("I", "ı").replace("İ", "i").lower().replace("i̇", "i")


class TurkishNormalizer:
    """Default Normalizer implementation."""

    def normalize(self, text: str) -> NormalizedText:
        cleaned = unicodedata.normalize("NFKC", text).translate(ZERO_WIDTH).translate(HOMOGLYPHS)
        lower = _WS.sub(" ", turkish_lower(cleaned)).strip()
        folded = lower.translate(DIACRITICS)
        folded = _LEET_WORD.sub(lambda m: m.group(0).translate(LEET), folded)  # numbers in prose survive
        folded = _SPACED.sub(lambda m: re.sub(r"[ .\-_*]", "", m.group(0)), folded)
        return NormalizedText(original=text, lower=lower, folded=_WS.sub(" ", folded).strip())


_default = TurkishNormalizer()


def normalize(text: str) -> NormalizedText:
    """Module-level shortcut for the default normaliser."""
    return _default.normalize(text)
