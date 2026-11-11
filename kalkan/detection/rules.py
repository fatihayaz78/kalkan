"""High-precision rules (stage 2).

Open/Closed: new rules are added by registering a Rule, without touching the
engine. Rules run on the ASCII-folded view, so one pattern also covers
diacritic-stripped, leetspeak, homoglyph and spaced-letter variants.
"""
from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from typing import Iterable, Protocol

from ..domain.ports import Normalizer

_NOUN = r"(?:talimat|komut|kural|yonerge|yonerg|direktif|sistem mesaj|sistem prompt|kisitlama|instruction|rule|prompt)\w*"
_VERB = (r"(?:unut|yok ?say|gormezden gel|dikkate alma|iptal et|umursama|birak|uygulama|"
         r"ignore(?:'?la| et)?|bypass(?:'?la| et)?|disregard|forget)")
_END = r"(?=$|[\s.,!;:?]|\s+ve\b)"


class Rule(Protocol):
    name: str

    def matches(self, folded: str) -> bool: ...


@dataclass(frozen=True)
class RegexRule:
    name: str
    pattern: re.Pattern

    def matches(self, folded: str) -> bool:
        return bool(self.pattern.search(folded))


class PayloadDecoder(Protocol):
    name: str

    def decode(self, text: str) -> list[str]: ...


class Base64Decoder:
    name = "base64"
    _token = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")

    def decode(self, text: str) -> list[str]:
        out = []
        for token in self._token.findall(text):
            try:
                decoded = base64.b64decode(token + "=" * (-len(token) % 4), validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError, ValueError):
                continue
            if sum(c.isprintable() for c in decoded) / max(len(decoded), 1) > 0.9:
                out.append(decoded)
        return out


def default_rules() -> list[Rule]:
    return [
        RegexRule("override_tr", re.compile(
            rf"\b(?:onceki|yukaridaki|tum|butun|eski|verilen|sana verilen|mevcut|ilk)\b(?:\s+\w+){{0,3}}\s+"
            rf"{_NOUN}(?:\s+\w+){{0,2}}\s+{_VERB}{_END}")),
        RegexRule("override_en", re.compile(
            r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier|system)\s+"
            r"(?:instructions|rules|prompts?|messages?)")),
        RegexRule("extract_system", re.compile(
            r"\b(?:sistem (?:mesaj|prompt|talimat)\w*|system prompt|gizli talimat\w*|ilk mesaj\w*)(?:\s+\w+){0,4}\s+"
            r"(?:yaz|goster|soyle|tekrarla|paylas|ver|listele|print|reveal|repeat)\w{0,4}" + _END)),
        RegexRule("persona_jailbreak", re.compile(
            r"\b(?:artik|bundan sonra)\b.{0,60}\b(?:kural|kisitlama|filtre|sinir|etik)\w*\s+(?:olmayan|yok|tanimayan)\b"
            r"|\bdan (?:modu|modunda|olarak)\b")),
        RegexRule("override_codeswitch", re.compile(
            r"\b(?:previous|prior|above|all|onceki|tum|butun|yukaridaki)\b[\w' ]{0,20}?"
            r"(?:instruction|rule|prompt|talimat|kural)[\w']*\s+(?:ignore|bypass|forget|skip|override)[\w']*")),
    ]


@dataclass(frozen=True)
class RuleMatch:
    rule: str | None
    decoded_from: str | None = None

    @property
    def matched(self) -> bool:
        return self.rule is not None


class RuleSet:
    def __init__(self, normalizer: Normalizer, rules: Iterable[Rule] | None = None,
                 decoders: Iterable[PayloadDecoder] | None = None):
        self._normalizer = normalizer
        self._rules = list(rules if rules is not None else default_rules())
        self._decoders = list(decoders if decoders is not None else [Base64Decoder()])

    def register(self, rule: Rule) -> "RuleSet":
        self._rules.append(rule)
        return self

    @property
    def names(self) -> list[str]:
        return [r.name for r in self._rules]

    def _first(self, folded: str) -> str | None:
        return next((r.name for r in self._rules if r.matches(folded)), None)

    def match(self, folded: str, original: str) -> RuleMatch:
        if hit := self._first(folded):
            return RuleMatch(hit)
        for decoder in self._decoders:
            for payload in decoder.decode(original):
                if hit := self._first(self._normalizer.normalize(payload).folded):
                    return RuleMatch(hit, decoder.name)
        return RuleMatch(None)
