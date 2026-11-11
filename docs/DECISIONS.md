# Decision log

Newest first. One entry per decision: context, decision, consequence.

## 2026-11-11 - D13: Red-team LLM access through an OpenAI-compatible adapter
The attack generator talks to any OpenAI-compatible endpoint (hosted, vLLM, Ollama) configured by environment variables, so no provider SDK is a dependency.

## 2026-11-11 - D12: Layered architecture (ports and adapters)
Domain (models, ports) → detection → application (use cases) → adapters → api. Only `api/container.py` and `application/factory.py` name concrete classes. Detection is a chain of stages; policies are strategies; `Kalkan` and the services are facades. See `ARCHITECTURE.md`.

## 2026-11-11 - D11: Client fails closed by default
If Kalkan is unreachable the SDK treats the request as `block`. Chatbots that prefer availability set `fail_mode="open"`. 4xx errors (bad key, too long) always raise, so misconfiguration is not hidden.

## 2026-11-11 - D10: Audit log stores a hash, text only for flagged/blocked
Kalkan sees end-user messages. Default `KALKAN_LOG_TEXT=flagged` keeps text only where it is needed for review; `none` and `all` are available.

## 2026-11-11 - D9: Retrain never auto-activates
A new version is trained from base data + accepted reports and shown next to the active one; an admin activates it. Activation swaps the engine in-process, no restart.

## 2026-11-11 - D8: Kalkan is a standalone service with a thin client
Core library has no web dependencies; the HTTP layer (now `kalkan/api/`) adds versioned API, per-client API keys and policies, SQLite storage; chatbots use `clients/python` (httpx only) or plain HTTP. `/v1/check/messages` accepts the OpenAI `messages` format so most chatbots integrate without reshaping data.

## 2026-11-11 - D7: v1 is a 4-week product build, not a research study
No research questions or statistical evaluation. v1 = normaliser, rules, TF-IDF+LR, API, UI, Docker, docs. BERTurk and LLM red-team move to "later". Done when: >=90% injection recall, <=2% benign blocked, <50 ms on CPU.

## 2026-11-11 - D6: Rules never allow, only block
Rules are high precision but low recall; letting them allow would make bypassing one regex enough. A rule miss falls through to the ML stages.

## 2026-11-11 - D5: "Developer mode" removed from strong rules
"Geliştirici modunu Android'de nasıl açarım?" was blocked. Persona detection for this phrase is left to the ML stages.

## 2026-11-11 - D4: Disjoint train / held-out transform sets
Training uses diacritic stripping, casing, ı/i swap, leetspeak, spacing, synonyms. The evasion split uses homoglyphs, zero-width characters, code-switching and Base64 only. The fuzz red-team mode uses train transforms only, so retraining on its output does not contaminate the evasion split.

## 2026-11-11 - D3: Template-level splits
Splits are made by `template_id`, not by row, so augmented variants of one template never appear in both train and test.

## 2026-11-11 - D2: Cascade instead of a single model
Stage 3 (TF-IDF+LR, <1 ms) decides confidently benign traffic; BERTurk runs only on the rest. Target: p95 < 100 ms on CPU.

## 2026-11-11 - D1: Seed dataset is synthetic
Template-generated Turkish data makes the pipeline runnable on day one. Known limits: few benign templates (benign test set is small), regular phrasing. Next: add translated public injection sets, Turkish instruction data and more hard negatives via `--extra`.
