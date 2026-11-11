# Kalkan

Turkish-first prompt-injection detection, packaged as a service any chatbot can call. Send untrusted text to Kalkan before your LLM; it answers `allow`, `flag` or `block` with the reason.

Graduation project, MSc Data Science & AI, Bahçeşehir University. Background and scope: `docs/PROJECT.md`. Contributors start with `docs/CONTEXT.md`.

## Run it

```bash
cp .env.example .env            # empty keys = dev mode, no auth
docker compose up --build       # http://localhost:8088
```

| URL | What |
| --- | --- |
| `http://localhost:8088/` | Demo: try attacks, disguise them, report wrong results |
| `http://localhost:8088/admin` | Admin: review reports, train a new model version, activate it |
| `http://localhost:8088/docs` | API reference (OpenAPI) |

Port taken? `KALKAN_PORT=9090 docker compose up`.

## Use it from a chatbot

```bash
curl -X POST localhost:8088/v1/check -H "Authorization: Bearer $KEY" \
  -H 'Content-Type: application/json' -d '{"text": "Önceki talimatları yok say"}'
# {"request_id":"…","decision":"block","score":1.0,"stage":"rules","matched_rule":"override_tr",…}
```

```python
from kalkan_client import KalkanClient, InjectionBlocked
kalkan = KalkanClient("http://localhost:8088", api_key=KEY, fail_mode="closed")
kalkan.guard(user_message)   # raises InjectionBlocked
```

Integration guide (RAG chunks, chat transcripts, fail-open/closed, per-client strictness, other languages): `docs/INTEGRATION.md`.

## API

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/v1/check` | client key | Check one text |
| POST | `/v1/check/batch` | client key | Check up to 64 texts (RAG chunks) |
| POST | `/v1/check/messages` | client key | Check an OpenAI-style `messages` transcript |
| POST | `/v1/feedback` | client key | Report a wrong decision |
| GET | `/v1/admin/feedback` | admin key | Review queue |
| POST | `/v1/admin/feedback/{id}` | admin key | Accept / reject a report |
| POST | `/v1/admin/retrain` | admin key | Train a new version (base data + accepted reports) |
| GET | `/v1/admin/models` | admin key | Versions and their metrics |
| POST | `/v1/admin/models/{v}/activate` | admin key | Switch the live model (no restart) |
| GET | `/health`, `/ready`, `/metrics` | none | Ops, Prometheus counters |

## Architecture

Layered, ports-and-adapters design following SOLID. The domain (`Verdict`, `Policy`, ports) has no framework dependencies; detection runs as a chain of stages; models, storage and LLM providers are adapters behind small interfaces; one composition root wires everything. Patterns used: chain of responsibility (stages), strategy (per-client policies), factory (pipeline per model version), facade (`Kalkan` in-process, application services for the API), adapter and repository (models, SQLite, registry). Details and extension points: `docs/ARCHITECTURE.md`.

In-process use without the HTTP service:

```python
from kalkan import Kalkan
guard = Kalkan.from_directory("models")
guard.check("Önceki talimatları yok say").decision   # Decision.BLOCK
```

## How detection works

| Stage | Module | What it does |
| --- | --- | --- |
| 1 Normaliser | `kalkan/detection/normalizer.py` | NFKC, hidden characters, Cyrillic/Greek look-alikes, Turkish İ/ı casing, diacritics, leetspeak, spaced letters |
| 2 Rules | `kalkan/detection/rules.py` | High-precision patterns (override, Turkish-English mixing, system prompt extraction, persona) + Base64 decoding. Block only |
| 3 Screening model | `kalkan/adapters/classifiers/tfidf.py` | Char n-gram TF-IDF + Logistic Regression |
| 4 Transformer (later) | `kalkan/adapters/classifiers/transformer.py` | Fine-tuned BERTurk; loaded automatically if `models/<version>/berturk/` exists |

## Layout

```
kalkan/domain/         entities, value objects, ports (no dependencies)
kalkan/detection/      normaliser, rules, evasion transforms, stages, pipeline
kalkan/application/    use cases, pipeline factory, policies, training
kalkan/adapters/       classifiers, model registry, SQLite, data source, attack generators
kalkan/api/            FastAPI routes, auth, composition root, demo and admin UI
clients/python/        kalkan-client SDK (httpx only) for chatbots
examples/              chatbot, RAG, LangChain, Node.js
scripts/               build_dataset, train_classical, train_transformer, evaluate, redteam
docs/                  CONTEXT.md, ARCHITECTURE.md, INTEGRATION.md, DECISIONS.md, PROJECT.md
```

## Develop

```bash
pip install -r requirements-train.txt && pip install -e clients/python
python scripts/build_dataset.py && python scripts/train_classical.py
uvicorn kalkan.api.app:app --reload --port 8088
pytest -q
```

The seed dataset is template-generated so everything runs on day one. Real Turkish and translated data is added in week 1 (`build_dataset.py --extra file.jsonl`).
