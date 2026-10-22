# 🧭 AI Job Application Copilot

A full-stack app that compares a resume with a job posting and helps the candidate apply: a fit analysis with skill-by-skill evidence, a resume review, a cover letter and interview prep.

The AI features are built to be checked rather than trusted. Every model call returns schema-validated output, is retried and costed consistently, and is logged per user. Generated claims are tied back to verbatim resume quotes, and the matching logic is measured against a labeled dataset before any change becomes the default.

## ✨ Features

- 📊 **Fit analysis.** Score, strengths, weaknesses and recommendations for a resume against a job description.
- 🔍 **Skill evidence.** Every skill the job asks for, marked required or preferred, matched or missing, with the exact resume quote that supports each match.
- 📝 **Resume review.** Prioritized suggestions grounded in the analysis and skill evidence.
- ✉️ **Cover letter.** Three paragraphs, each with the resume quotes it relies on. Quotes that do not appear in the resume are flagged.
- 🎤 **Interview prep.** Technical, behavioral and project questions built from the candidate's own resume.
- 📁 **Application tracking.** Resumes (text or PDF upload), jobs, applications, status and notes.

## 🏗️ Architecture

```mermaid
flowchart LR
    Browser --> FE["Next.js frontend<br/>(route handlers proxy the API)"]
    FE --> BE["NestJS API<br/>JWT auth · Prisma"]
    BE --> AI["FastAPI AI service"]
    AI --> OpenAI["OpenAI<br/>Responses + Embeddings"]
    BE --> DB[("PostgreSQL + pgvector")]
    AI --> DB
```

| Service | Stack | Responsibility |
|---|---|---|
| `frontend/` | Next.js 16, React 19, Tailwind CSS 4 | UI. Server-side route handlers call the API, so the JWT stays in an HTTP-only cookie. |
| `backend/` | NestJS 11, Prisma 6, Passport JWT | Auth, ownership checks, persistence, and logging every AI call to the `AiRun` table. |
| `ai-service/` | FastAPI, Pydantic, OpenAI SDK, psycopg | Prompts, structured LLM calls, typed tools, skill matching and claim verification, evals. Only the backend can call it (shared-secret header). |
| Database | PostgreSQL with pgvector | App data, AI run logs, and skill embeddings behind an HNSW index. |

## 🤖 How the AI layer works

All model calls go through one client, [`ai-service/llm/client.py`](ai-service/llm/client.py).

- 🧱 **Strict structured output.** Each endpoint defines a Pydantic model, converted to a strict JSON Schema (`strict: true`, every field required, no extra fields). The response is validated against the same model.
- 🔁 **Real retries.** The SDK's own retries are disabled, so the `retries` count is accurate. Rate limits, timeouts and 5xx errors are retried with exponential backoff and jitter. Invalid output is retried once. Refusals and truncated output are reported, not retried.
- 💰 **Cost accounting.** Tokens and cost are summed across all attempts, failed ones included, from a per-model price table ([`llm/config.py`](ai-service/llm/config.py)).
- 📈 **Run logging.** Every response carries run metadata: model, prompt version, latency, tokens, retries, status, error type and cost. The backend writes one `AiRun` row per LLM call, including failures, linked to the user.
- 🏷️ **Versioned prompts.** Prompts live in [`ai-service/prompts/`](ai-service/prompts/) and are listed in `prompt_registry.json`. Only registered versions can be loaded.
- ✅ **Grounding check.** The cover letter cites resume quotes per paragraph, and [`skills/grounding.py`](ai-service/skills/grounding.py) flags any quote that is not actually in the resume.

## 🎯 Skill matching and evaluation

`/analyze` runs the fit analysis and skill matching in parallel. Skill matching ([`skills/skill_matcher.py`](ai-service/skills/skill_matcher.py)) works in two steps:

1. **LLM proposal.** One structured call lists each job skill with its priority, whether the resume shows it, and a verbatim resume quote as evidence.
2. **Optional deterministic verification.** The quote must actually appear in the resume. It must not be hedged ("currently learning", "no experience with"). It must name the skill through a taxonomy alias, or be close enough in embedding space. Similarity is computed in PostgreSQL with pgvector's cosine distance operator (`<=>`, see [`skills/semantic_matcher.py`](ai-service/skills/semantic_matcher.py)).

Whether verification is worth turning on was decided by measurement. [`evals/skill_matching_ab.py`](ai-service/evals/skill_matching_ab.py) runs both modes on the same LLM output, so the comparison isolates the verifier:

- 41 hand-labeled cases, split into dev (16 cases, 83 labeled skills) and holdout (25 cases, 121 labeled skills).
- The cases include adjacent-skill traps (Docker vs. Kubernetes, MySQL vs. PostgreSQL), hedged or negated mentions, and implied skills (EKS → Kubernetes).
- Verifier settings are chosen on dev only, then applied once to holdout.

Results (gpt-4.1-mini, 3 repeats, pooled micro F1 over required/preferred × matched/missing):

| Split | Taxonomy only (heuristic baseline) | LLM only | LLM + verification |
|---|---|---|---|
| Dev | 0.904 | 0.982 | 0.982 |
| Holdout | 0.945 | **0.984** | 0.975 |

Verification did not beat LLM-only on holdout, so the default stays `SKILL_MATCH_MODE=llm`. On holdout the two modes differ by one labeled skill out of 121: the verifier rejected "GCP" for a resume that mentions only "GKE", and it did not catch either of the LLM's two errors. On data this size the difference is not meaningful in either direction. The harness is in place to re-test the verifier as the dataset grows.

## 🚀 Running locally

**Prerequisites:** Node.js 20+, Python 3.12+, Docker, an OpenAI API key.

Generate one shared secret for the backend and AI service (both `.env` files use it as `AI_SERVICE_TOKEN`):
```bash
openssl rand -hex 32
```

**1. Database (PostgreSQL with pgvector):**
```bash
docker run -d --name ajc-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=ajc \
  -p 5432:5432 pgvector/pgvector:pg16
```

**2. Backend (http://localhost:4000):**
```bash
cd backend
cp .env.example .env            # set JWT_SECRET and AI_SERVICE_TOKEN
npm install
npx prisma migrate deploy       # also enables the vector extension
npm run start:dev
```

**3. AI service (http://localhost:8000):**
```bash
cd ai-service
cp .env.example .env            # set OPENAI_API_KEY and the same AI_SERVICE_TOKEN
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn main:app --reload --port 8000
```

**4. Frontend (http://localhost:3000):**
```bash
cd frontend
cp .env.example .env.local      # point both URLs at http://localhost:4000
npm install
npm run dev
```

## 🧪 Tests and evals

```bash
# AI service unit tests (no network: OpenAI clients are blocked in tests)
cd ai-service && .venv/bin/python -m pytest

# pgvector integration test against the local database
PGVECTOR_TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/ajc" \
  .venv/bin/python -m pytest -k pgvector

# Skill-matching A/B eval (real OpenAI calls, about $0.08 with --repeats 3; LLM output is cached)
.venv/bin/python evals/skill_matching_ab.py --repeats 3

# Backend type check and build
cd backend && npx tsc --noEmit && npm run build
```

## 📂 Project structure

```
ai-service/
  llm/            structured-output client, retries, cost config
  routes/         /analyze, /cover-letter, /interview-prep, /resume-review
  skills/         skill matcher, taxonomy, pgvector similarity, grounding checks
  prompts/        versioned prompts and registry
  evals/          labeled datasets and evaluation harnesses
  tests/          pytest suite
backend/
  prisma/         schema and migrations
  src/            NestJS modules (auth, resumes, jobs, applications, AI features)
frontend/
  src/app/        Next.js pages and API route handlers
```

## 🗺️ Roadmap

- 🛠️ **Typed tools:** job-posting fetch (SSRF-safe), requirement extraction, skill matching, resume evidence search with pgvector, and a claim verifier that rejects claims without resume evidence.
- 🔄 **Agent workflow:** a LangGraph plan → tools → draft → verify → revise loop with step limits, human approval, and per-step traces.
- 🔌 **MCP server:** the same tools exposed through the Model Context Protocol.
- 📏 **Agent evals:** task success, tool-call accuracy, unsupported-claim rate with and without the verifier, cost and latency.
