"""Thin client for the Kalkan service. Only depends on httpx.

    from kalkan_client import KalkanClient, InjectionBlocked

    kalkan = KalkanClient("http://kalkan:8000", api_key="...", fail_mode="closed")
    kalkan.guard(user_text)            # raises InjectionBlocked on `block`
    result = kalkan.check(user_text)   # or inspect the result yourself

fail_mode decides what happens if Kalkan is unreachable or times out:
  "closed" -> treat as block (safer; default)
  "open"   -> treat as allow (availability first)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

import httpx

__all__ = ["KalkanClient", "AsyncKalkanClient", "CheckResult", "InjectionBlocked"]
SEVERITY = {"allow": 0, "flag": 1, "block": 2}


@dataclass
class CheckResult:
    decision: str
    score: float = 0.0
    stage: str = ""
    matched_rule: str | None = None
    request_id: str | None = None
    model_version: str | None = None
    latency_ms: float = 0.0
    degraded: bool = False  # True when the service was unreachable and fail_mode decided
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def blocked(self) -> bool:
        return self.decision == "block"

    @classmethod
    def from_json(cls, d: dict) -> "CheckResult":
        keys = cls.__dataclass_fields__.keys() - {"raw", "degraded"}
        return cls(**{k: d.get(k) for k in keys if k in d}, raw=d)


class InjectionBlocked(Exception):
    def __init__(self, result: CheckResult):
        self.result = result
        super().__init__(f"Prompt injection blocked ({result.stage}: {result.matched_rule or result.score})")


def _messages(messages: Iterable[Any]) -> list[dict]:
    out = []
    for m in messages:
        if isinstance(m, dict):
            out.append({"role": m["role"], "content": m["content"]})
        else:  # objects with .role/.content (OpenAI SDK, LangChain-like)
            out.append({"role": getattr(m, "role", getattr(m, "type", "user")), "content": str(m.content)})
    return out


class _Base:
    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 2.0, fail_mode: str = "closed",
                 transport: httpx.BaseTransport | httpx.AsyncBaseTransport | None = None):
        if fail_mode not in ("open", "closed"):
            raise ValueError("fail_mode must be 'open' or 'closed'")
        self.fail_mode = fail_mode
        self._kw = dict(base_url=base_url.rstrip("/"), timeout=timeout,
                        headers={"Authorization": f"Bearer {api_key}"} if api_key else {})
        if transport is not None:
            self._kw["transport"] = transport

    def _fallback(self) -> CheckResult:
        return CheckResult(decision="block" if self.fail_mode == "closed" else "allow", degraded=True)

    def _raise_if_blocked(self, r: CheckResult) -> CheckResult:
        if r.blocked:
            raise InjectionBlocked(r)
        return r


class KalkanClient(_Base):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._http = httpx.Client(**self._kw)

    def _post(self, path: str, body: dict) -> dict | None:
        try:
            r = self._http.post(path, json=body)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:
                raise  # caller errors (bad key, too long) surface instead of being masked by fail_mode
            return None
        except httpx.TransportError:
            return None

    def check(self, text: str, source: str = "user", conversation_id: str | None = None) -> CheckResult:
        d = self._post("/v1/check", {"text": text, "source": source, "conversation_id": conversation_id})
        return CheckResult.from_json(d) if d else self._fallback()

    def check_messages(self, messages: Iterable[Any], scope: str = "latest") -> CheckResult:
        """Check a chat transcript; returns the most severe result."""
        d = self._post("/v1/check/messages", {"messages": _messages(messages), "scope": scope})
        if not d:
            return self._fallback()
        worst = max(d["results"], key=lambda r: SEVERITY[r["decision"]], default={"decision": "allow"})
        return CheckResult.from_json(worst)

    def check_documents(self, docs: list[str]) -> list[CheckResult]:
        """Check retrieved RAG chunks; drop the ones that are not `allow` before building the prompt."""
        d = self._post("/v1/check/batch", {"items": [{"text": t, "source": "document"} for t in docs]})
        return [CheckResult.from_json(r) for r in d["results"]] if d else [self._fallback() for _ in docs]

    def guard(self, text: str, **kw) -> CheckResult:
        return self._raise_if_blocked(self.check(text, **kw))

    def report(self, label: str, request_id: str | None = None, text: str | None = None, note: str | None = None):
        """Report a wrong decision: label is 'injection' or 'benign'."""
        return self._post("/v1/feedback", {"label": label, "request_id": request_id, "text": text, "note": note})

    def close(self):
        self._http.close()


class AsyncKalkanClient(_Base):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._http = httpx.AsyncClient(**self._kw)

    async def _post(self, path: str, body: dict) -> dict | None:
        try:
            r = await self._http.post(path, json=body)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:
                raise
            return None
        except httpx.TransportError:
            return None

    async def check(self, text: str, source: str = "user", conversation_id: str | None = None) -> CheckResult:
        d = await self._post("/v1/check", {"text": text, "source": source, "conversation_id": conversation_id})
        return CheckResult.from_json(d) if d else self._fallback()

    async def guard(self, text: str, **kw) -> CheckResult:
        return self._raise_if_blocked(await self.check(text, **kw))

    async def aclose(self):
        await self._http.aclose()
