# 🧭 AI Job Application Copilot

A full-stack app that compares a resume with a job posting and helps the candidate apply: a fit analysis with skill-by-skill evidence, a resume review, a cover letter and interview prep.

The AI features are built to be checked rather than trusted. Every model call returns schema-validated output, is retried and costed consistently, and is logged per user. Generated claims are tied back to verbatim resume quotes, and the matching logic is measured against a labeled dataset before any change becomes the default.

## ✨ Features

- 📊 **Fit analysis.** Score, strengths, weaknesses and recommendations for a resume against a job description.
- 🔍 **Skill evidence.** Every skill the job asks for, marked required or preferred, matched or missing, with the exact resume quote that supports each match.
- ✂️ **Resume tailoring agent.** Picks the resume lines that matter for a job, rewords them in the job's terms, rejects any rewrite that adds a skill, number or claim the original line doesn't state, then lets you accept, edit or keep each line and save the result as a new, named resume.
- ✉️ **Cover letter.** Three paragraphs, each with the resume quotes it relies on. Quotes that do not appear in the resume are flagged.
- 🎤 **Interview prep.** Technical, behavioral and project questions built from the candidate's own resume.
- 🕵️ **Cover letter assistant.** Plans the letter, retrieves supporting resume lines, drafts, fact-checks every claim, revises what fails, then pauses for you to approve, edit or reject.
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

## ✂️ Resume tailoring agent

The main agent, in [`ai-service/agent/tailoring.py`](ai-service/agent/tailoring.py):

```mermaid
flowchart LR
    plan --> rewrite --> verify
    verify -- "a rewrite added something,<br/>revisions left" --> revise --> verify
    verify -- "every rewrite only rephrases<br/>its original" --> human_review["your review<br/>(interrupt)"]
    human_review --> done(["save as a new resume / discard"])
```

- **Plan.** `match_skills` compares the resume with the job, the resume is split into units (wrapped PDF lines are rejoined into whole bullets, [`skills/resume_units.py`](ai-service/skills/resume_units.py)), and a planner picks up to six lines worth tailoring and what each should emphasize.
- **Rewrite, verify, revise.** `rewrite_bullet` rewords each line. The check is strict because each rewrite is compared only with its own original line: it may not add a skill, a number, or three or more content words the original doesn't contain (which catches padding like "to support investor dashboards"). Failing rewrites are redrafted with that feedback; a revision that fixes nothing stops early.
- **Your review.** Each line shows the original next to the suggestion with *Use suggestion / Edit / Keep original*; flagged suggestions default to the original. Job skills the resume doesn't show are listed separately and are never added.
- **Saved as a new resume.** Accepted lines are spliced into the resume at their original positions and saved under a name you choose; the original resume is unchanged. One click switches the application to the new resume.

Measured results are in [Agent evaluation](#-agent-evaluation): verification roughly halves invented content, but some still gets through, which is why every line still needs your approval.

## 🕵️ Cover letter assistant

A LangGraph workflow in [`ai-service/agent/graph.py`](ai-service/agent/graph.py):

```mermaid
flowchart LR
    plan --> gather_evidence --> draft --> verify
    verify -- "claim rejected,<br/>revisions left" --> revise --> verify
    verify -- "all supported or<br/>budget used" --> human_review["human review<br/>(interrupt)"]
    human_review --> done(["approve / edit / reject"])
```

- **Typed tools.** Each step calls tools from one registry ([`ai-service/tools/`](ai-service/tools/)): `match_skills`, `search_resume_evidence` (pgvector search over resume chunks), `draft_section`, `rewrite_bullet` and `verify_claims`. The same tools are exposed at `GET /tools` and `POST /tools/{name}`, alongside an SSRF-safe `fetch_job_posting` and `extract_requirements`.
- **Fact-checking.** [`skills/claim_verifier.py`](ai-service/skills/claim_verifier.py) rejects a claim unless its cited resume lines exist, are not hedged ("currently learning"), and contain every skill and number the claim states. It also checks the paragraph text itself, so a statement the model left out of its claim list is still caught. A rejected paragraph is redrafted with the verifier's reasons as feedback.
- **Bounded.** At most two revisions per paragraph and a hard step limit. Paragraphs that still fail are shown to the reviewer as unresolved rather than hidden.
- **Human approval.** The run pauses with `interrupt()` and its state is saved by the LangGraph Postgres checkpointer, so the decision can arrive in a later request. Nothing is saved as the cover letter until the user approves or edits it.
- **Traces.** Every step is stored as an `AgentStep` (node, latency, detail), and every LLM call as an `AiRun` linked to its step.

Measured results are in [Agent evaluation](#-agent-evaluation).

The claim verifier was measured on 40 hand-labeled claims ([`evals/claim_verification_eval.py`](ai-service/evals/claim_verification_eval.py)): rejection precision 0.78 and recall 0.78. It catches inflated numbers, swapped tools and hedged sources; it misses invented qualities with no skill or number in them ("fault-tolerant") and is strict about implied skills. The labels and rules come from the same author, so treat this as behaviour on known patterns rather than a generalization measure.

## 📏 Agent evaluation

[`evals/agent_eval.py`](ai-service/evals/agent_eval.py) measures both agents and the checks they rely on, with real model calls (agents on gpt-4.1-mini).

**1. Rewrite checker** (deterministic, no model): 40 hand-labeled rewrites, 20 faithful and 20 that add content, none used to build the checker. Precision **0.76**, recall **0.80**. It catches added tools, numbers, purposes and scale claims; it misses additions phrased in one or two words ("led a team", "real-time") and flags some honest rewrites that use job terms ("infrastructure as code").

**2. Judge.** A stronger model (gpt-4.1) labels the same 40 rewrites: **97.5% agreement** with the human labels (Cohen's κ 0.95). It then scores the agents' output below. Its paragraph-level judgements for cover letters were spot-checked by hand but not formally validated.

**3. Agents end to end** on 8 synthetic resume/job pairs. "Without verification" is each run's first draft, read back from the LangGraph checkpoint history; "with verification" is what the user is shown. Two runs each:

| | Resume tailoring | Cover letter |
|---|---|---|
| Task success (reached review, nothing unresolved) | 100% | 100% |
| Content the resume doesn't support, without verification | 17–30% of rewrites | 67–71% of paragraphs |
| …with verification | **11–17%** of lines applied by default | **63%** of paragraphs |
| Valid planner selections / cited evidence ids | 100% | 100% |
| Mean LLM calls, cost, latency per run | 6.6, $0.0023, 5.7 s | 6.0, $0.0041, 9.0–9.5 s |

What this shows:
- **Tailoring:** verification consistently cuts invented content roughly in half (three runs: 24→13%, 17→11%, 30→17%). What remains is mostly qualifiers and scope taken from the job ("advanced SQL", "Led development").
- **Cover letter:** the first evaluation found unsupported statements in 90% of paragraphs, mostly self-praise such as "demonstrating strong database skills" and job requirements stated as experience. Rewriting the drafting prompt (`draft_section_v2`) brought that to about 63%. The deterministic verifier adds only a few points on top, because it checks skills and numbers and this content is neither.
- The evaluation also found a crash when revision feedback was long; it is fixed and covered by a regression test.

The cover letter remains a draft to edit, not a letter to send unread. Catching self-assessment needs a model-based check in the verify step, which is the next improvement to measure with this same harness.

## 🔌 MCP server

The same seven tools are available to any MCP client through [`ai-service/mcp_server.py`](ai-service/mcp_server.py), built on the official Python SDK. Tool names, descriptions and input/output schemas come from the same registry as the HTTP API and the agent, so the three cannot drift apart. Results include structured output plus usage metadata (LLM calls, estimated cost, latency); failures such as a blocked URL or invalid arguments come back as MCP tool errors.

```bash
cd ai-service

# Explore the tools in the MCP Inspector (web UI)
npx @modelcontextprotocol/inspector .venv/bin/python mcp_server.py

# Or from the command line
npx @modelcontextprotocol/inspector --cli .venv/bin/python mcp_server.py --method tools/list
npx @modelcontextprotocol/inspector --cli .venv/bin/python mcp_server.py \
  --method tools/call --tool-name fetch_job_posting --tool-arg url=https://www.python.org/jobs/
```

To use it from an MCP client, register a stdio server whose command is the absolute path to `ai-service/.venv/bin/python` with the argument `ai-service/mcp_server.py`. The server runs locally over stdio and opens no network port; it reads `OPENAI_API_KEY` and `DATABASE_URL` from `ai-service/.env`.

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
# Separate database for agent checkpoints (LangGraph manages its own tables there)
docker exec ajc-postgres createdb -U postgres ajc_agent
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

# Agent evaluation: rewrite checker, judge validation, both agents end to end (about $0.35)
.venv/bin/python evals/agent_eval.py
.venv/bin/python evals/agent_eval.py --skip-agents   # checker and judge only (about $0.04)

# Backend type check and build
cd backend && npx tsc --noEmit && npm run build
```

## 📂 Project structure

```
ai-service/
  agent/          LangGraph cover-letter agent and Postgres checkpointer
  llm/            structured-output client, retries, cost config
  mcp_server.py   MCP server exposing the tool registry over stdio
  routes/         AI endpoints, /tools and /agent/runs
  skills/         skill matcher, claim verifier, resume chunks, SSRF-safe fetch, taxonomy
  tools/          typed tool registry
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

- 🔎 **Model-based claim check:** add a semantic check to the verify step to catch self-assessment and scope inflation, and measure it against the current results.
- 📊 **Larger evaluation sets:** more resumes, real (consented) job postings, and repeated runs for tighter ranges.
