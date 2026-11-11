"""Stage 1 - Turkish-aware text normalisation.

Produces several "views" of the input so later stages are robust to
diacritic stripping, casing tricks, homoglyphs, zero-width characters,
leetspeak and letter spacing.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

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
_WS = re.compile(r"\s+")


def turkish_lower(text: str) -> str:
    """Lowercase with Turkish dotted/dotless I rules (I->ı, İ->i)."""
    return text.replace("I", "ı").replace("İ", "i").lower().replace("i̇", "i")


def _collapse_spaced(text: str) -> str:
    """'y o k s a y' -> 'yoksay' (only for runs of single characters)."""
    return _SPACED.sub(lambda m: re.sub(r"[ .\-_*]", "", m.group(0)), text)


@dataclass(frozen=True)
class NormalizedText:
    original: str
    lower: str   # Turkish-lowercased, cleaned, keeps diacritics
    folded: str  # ASCII-folded, de-leeted, spacing collapsed: used by rules and TF-IDF


def normalize(text: str) -> NormalizedText:
    cleaned = unicodedata.normalize("NFKC", text).translate(ZERO_WIDTH).translate(HOMOGLYPHS)
    lower = _WS.sub(" ", turkish_lower(cleaned)).strip()
    folded = lower.translate(DIACRITICS)
    # De-leet only inside alphabetic words so numbers in normal text survive.
    folded = re.sub(r"\b(?=\w*[a-z])[\w@$!]+\b", lambda m: m.group(0).translate(LEET), folded)
    folded = _collapse_spaced(folded)
    folded = _WS.sub(" ", folded).strip()
    return NormalizedText(original=text, lower=lower, folded=folded)
