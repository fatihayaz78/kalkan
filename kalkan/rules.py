"""Stage 2 - high-precision rule layer.

Rules run on the ASCII-folded view, so one pattern covers diacritic-stripped,
leetspeak, homoglyph and spaced-letter variants. A strong match blocks; the
layer never allows on its own.
"""
from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass

from .normalize import normalize

# Nouns that name the model's instructions (stems; suffixes allowed).
_NOUN = r"(?:talimat|komut|kural|yonerge|yonerg|direktif|sistem mesaj|sistem prompt|kisitlama|instruction|rule|prompt)\w*"
# Imperative "ignore" verbs, Turkish + common code-switching forms. Must end the word.
_VERB = (
    r"(?:unut|yok ?say|gormezden gel|dikkate alma|iptal et|umursama|birak|uygulama|"
    r"ignore(?:'?la| et)?|bypass(?:'?la| et)?|disregard|forget)"
)
_END = r"(?=$|[\s.,!;:?]|\s+ve\b)"

RULES: dict[str, re.Pattern] = {
    "override_tr": re.compile(
        rf"\b(?:onceki|yukaridaki|tum|butun|eski|verilen|sana verilen|mevcut|ilk)\b(?:\s+\w+){{0,3}}\s+{_NOUN}(?:\s+\w+){{0,2}}\s+{_VERB}{_END}"
    ),
    "override_en": re.compile(
        r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier|system)\s+(?:instructions|rules|prompts?|messages?)"
    ),
    "extract_system": re.compile(
        r"\b(?:sistem (?:mesaj|prompt|talimat)\w*|system prompt|gizli talimat\w*|ilk mesaj\w*)(?:\s+\w+){0,4}\s+"
        r"(?:yaz|goster|soyle|tekrarla|paylas|ver|listele|print|reveal|repeat)\w{0,4}" + _END
    ),
    "persona_jailbreak": re.compile(
        r"\b(?:artik|bundan sonra)\b.{0,60}\b(?:kural|kisitlama|filtre|sinir|etik)\w*\s+(?:olmayan|yok|tanimayan)\b"
        r"|\bdan (?:modu|modunda|olarak)\b"
    ),
    # Code-switched Turkish/English, e.g. "previous instructions'ı ignore et".
    "override_codeswitch": re.compile(
        r"\b(?:previous|prior|above|all|onceki|tum|butun|yukaridaki)\b[\w' ]{0,20}?"
        r"(?:instruction|rule|prompt|talimat|kural)[\w']*\s+(?:ignore|bypass|forget|skip|override)[\w']*"
    ),
}

_B64 = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")


@dataclass(frozen=True)
class RuleResult:
    matched: bool
    rule: str | None = None
    decoded_from: str | None = None  # e.g. "base64" when the hit was inside an encoded payload


def _match(folded: str) -> str | None:
    for name, pattern in RULES.items():
        if pattern.search(folded):
            return name
    return None


def _decoded_payloads(text: str) -> list[str]:
    out = []
    for token in _B64.findall(text):
        try:
            raw = base64.b64decode(token + "=" * (-len(token) % 4), validate=True)
            decoded = raw.decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        if sum(c.isprintable() for c in decoded) / max(len(decoded), 1) > 0.9:
            out.append(decoded)
    return out


def check_rules(folded: str, original: str) -> RuleResult:
    hit = _match(folded)
    if hit:
        return RuleResult(True, hit)
    for payload in _decoded_payloads(original):
        hit = _match(normalize(payload).folded)
        if hit:
            return RuleResult(True, hit, decoded_from="base64")
    return RuleResult(False)
