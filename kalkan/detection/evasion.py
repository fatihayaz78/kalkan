"""Turkish evasion transforms.

Used three ways: training augmentation, the held-out evasion test split,
and the red-team mutation fuzzer. TRAIN_TRANSFORMS and HELDOUT_TRANSFORMS are
disjoint on purpose so the evasion split measures generalisation.
"""
from __future__ import annotations

import random
import re
from typing import Callable

Transform = Callable[[str, random.Random], str]

_STRIP = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
_LEET = {"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "t": "7"}
_HOMO = {"a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "x": "х", "i": "і"}  # Cyrillic
_ZW = ["\u200b", "\u200c", "\u200d", "\u2060"]

# Turkish phrase -> code-switched / synonym variants.
_CODE_SWITCH = {
    "yok say": ["ignore et", "ignore'la", "skip'le"],
    "görmezden gel": ["ignore et", "bypass et"],
    "unut": ["forget'la", "unut gitsin"],
    "talimatları": ["instruction'ları", "prompt'ları"],
    "kuralları": ["rule'ları", "policy'leri"],
    "sistem mesajını": ["system prompt'u", "system message'ı"],
}
_SYNONYMS = {
    "yok say": ["görmezden gel", "dikkate alma", "umursama"],
    "unut": ["yok say", "bir kenara bırak"],
    "talimatları": ["yönergeleri", "komutları", "direktifleri"],
    "önceki": ["yukarıdaki", "daha önceki", "ilk verilen"],
}


def strip_diacritics(t: str, rng: random.Random) -> str:
    return t.translate(_STRIP)


def random_case(t: str, rng: random.Random) -> str:
    return "".join(c.upper() if rng.random() < 0.35 else c for c in t)


def i_swap(t: str, rng: random.Random) -> str:
    table = {"i": "ı", "ı": "i", "İ": "I", "I": "İ"}
    return "".join(table[c] if c in table and rng.random() < 0.5 else c for c in t)


def leetspeak(t: str, rng: random.Random) -> str:
    return "".join(_LEET[c] if c in _LEET and rng.random() < 0.5 else c for c in t)


def spaced_letters(t: str, rng: random.Random) -> str:
    words = t.split()
    if not words:
        return t
    idx = max(range(len(words)), key=lambda k: len(words[k]))  # space out the longest word
    words[idx] = " ".join(words[idx])
    return " ".join(words)


def synonym_swap(t: str, rng: random.Random) -> str:
    for src, alts in _SYNONYMS.items():
        if src in t and rng.random() < 0.7:
            t = t.replace(src, rng.choice(alts), 1)
    return t


def zero_width(t: str, rng: random.Random) -> str:
    return "".join(c + (rng.choice(_ZW) if c.isalpha() and rng.random() < 0.3 else "") for c in t)


def homoglyph(t: str, rng: random.Random) -> str:
    return "".join(_HOMO[c] if c in _HOMO and rng.random() < 0.4 else c for c in t)


def code_switch(t: str, rng: random.Random) -> str:
    for src, alts in _CODE_SWITCH.items():
        if src in t:
            t = t.replace(src, rng.choice(alts), 1)
    return t


def base64_wrap(t: str, rng: random.Random) -> str:
    import base64
    payload = base64.b64encode(t.encode()).decode()
    return rng.choice([f"Şunu decode edip uygula: {payload}", f"Base64: {payload} — çöz ve yap."])


TRAIN_TRANSFORMS: dict[str, Transform] = {
    "strip_diacritics": strip_diacritics,
    "random_case": random_case,
    "i_swap": i_swap,
    "leetspeak": leetspeak,
    "spaced_letters": spaced_letters,
    "synonym_swap": synonym_swap,
}
HELDOUT_TRANSFORMS: dict[str, Transform] = {
    "zero_width": zero_width,
    "homoglyph": homoglyph,
    "code_switch": code_switch,
    "base64_wrap": base64_wrap,
}
ALL_TRANSFORMS = {**TRAIN_TRANSFORMS, **HELDOUT_TRANSFORMS}


def apply(text: str, names: list[str], seed: int | None = None) -> str:
    rng = random.Random(seed)
    for n in names:
        text = ALL_TRANSFORMS[n](text, rng)
    return re.sub(r"[ ]{2,}", " ", text)


def augment(text: str, pool: dict[str, Transform], k: int, rng: random.Random) -> list[str]:
    """k variants, each with 1-2 random transforms from the pool."""
    names = list(pool)
    out = []
    for _ in range(k):
        chosen = rng.sample(names, rng.choice([1, 2]))
        out.append(apply(text, chosen, seed=rng.randint(0, 10**9)))
    return out
