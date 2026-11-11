# Project context

**Read this first.** This file is the working memory of the project: anyone (or any tool) picking up work on Kalkan starts here, and updates it at the end of each working session. Keep it short and current; history goes to the session log at the bottom and to `DECISIONS.md`.

## What Kalkan is

A Turkish-first prompt-injection detection service. Applications send untrusted text (user messages, retrieved documents, tool output) to Kalkan before calling their LLM; Kalkan returns `allow`, `flag` or `block` with the reason. Designed to be reused by any chatbot or LLM product, over HTTP.

- **Owner:** Fatih Ayaz (github.com/fatihayaz78)
- **Origin:** graduation project for the MSc in Data Science & AI, Bahçeşehir University (non-thesis track). It is a product build, not a research study: no research questions, success is a working, documented service.
- **Repository:** github.com/fatihayaz78/kalkan (public)

## Working agreement

- **Language:** code, docs, commits and PRs in English. Discussion with the owner is in Turkish.
- **Authorship:** everything appears as the owner's own work. No tool or assistant names, attribution lines or co-author trailers in code, comments, docs, commits or PRs.
- **Workflow:** one branch per change (`feature/…`, `fix/…`, `refactor/…`, `docs/…`), pushed to GitHub, PR opened; the owner reviews and merges. Never push directly to `main` after the initial commit.
- **Commits:** conventional style (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`), imperative mood.
- **Quality bar:** layered architecture and SOLID (see `ARCHITECTURE.md`); every change keeps `pytest -q` green and adds tests for new behaviour; record notable choices in `DECISIONS.md`.
- **Communication:** concise and direct; no long explanations unless asked.

## Environment

- Runs as its own Docker Compose project `kalkan`, host port **8088**, named volumes `kalkan-models` and `kalkan-db`. It shares the host with other Compose stacks, so never use their ports or names.
- No GPU needed for v1. The transformer stage (later) is trained on a separate GPU machine or Colab.
- Secrets live in `.env` (git-ignored). `.env.example` documents every variable.

## Current status (v0.3.0)

Done:
- Detection: Turkish normaliser, 5 rules + Base64 decoding, char n-gram TF-IDF + LR screening model; transformer stage pluggable.
- Service: `/v1/check`, `/check/batch`, `/check/messages`, `/feedback`; admin review, retrain, model versions with live activation; API keys, per-client policies, SQLite audit log, Prometheus metrics.
- UI: demo page (`/`) with presets, disguise buttons and "report wrong result"; admin page (`/admin`).
- Python client SDK with fail-closed/open; examples for FastAPI, RAG, LangChain, Node.
- Layered architecture refactor (ports and adapters), 36 tests.

Known limitations:
- Training data is template-generated (~1k rows); the benign test set has only 8 samples, so metrics are not meaningful yet.
- Offline red-team (mutation) finds nothing on its own training transforms; real evasions need the LLM mode.
- No CI yet.

## Next steps (in order)

1. **Real data (week 1):** script to download and machine-translate a public injection set (e.g. deepset/prompt-injections); add 1,000+ Turkish benign requests and 300+ hard negatives; spot-check translations; first meaningful metrics.
2. **CI:** GitHub Actions running `pytest` on every PR (token needs the Workflows permission).
3. **Week 2–4 per plan:** threshold tuning against the acceptance targets, demo polish, docs.
4. **Later:** BERTurk scoring stage, LLM red-team rounds, LangChain/LlamaIndex packages, Postgres adapter.

## v1 plan and acceptance targets

| Week | Work |
| --- | --- |
| 1 | Dataset, normaliser, rules |
| 2 | Screening model + evaluation |
| 3 | API, demo UI, Docker |
| 4 | Docs, tests, demo |

v1 is done when it catches ≥90% of injections in the test set, blocks ≤2% of benign requests and answers in <50 ms on CPU.

## Open questions

- Which public datasets' licences allow redistributing translated samples?
- Should the repository become private before the graduation demo?

## Session log

Newest first. One or two lines per session: what changed, what is next.

- **2026-11-11** - Project set up and pushed. Refactored to layered architecture (ports/adapters, chain of stages, factory, facades). Added this file and `ARCHITECTURE.md`. Next: real data.
