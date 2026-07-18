import json
import time
import urllib.request
from pathlib import Path

GPT_4O_MINI_INPUT_COST_PER_1M = 0.15
GPT_4O_MINI_OUTPUT_COST_PER_1M = 0.60

API_BASE = "http://localhost:8000"
RESULTS_PATH = Path("evals/results/ai_endpoint_metrics.json")


RESUME_TEXT = (
    "Software engineer with experience in Python, FastAPI, PostgreSQL, Docker, "
    "React, TypeScript, OpenAI APIs, prompt engineering, evaluation pipelines, "
    "observability, and vector search."
)

JOB_DESCRIPTION = (
    "Required Qualifications: Python, FastAPI, PostgreSQL, Docker, LLM APIs, "
    "Prompt Engineering, AI Evaluation. Preferred Qualifications: AWS, "
    "Kubernetes, pgvector, Vector Search, RAG, Production AI Infrastructure, "
    "Observability."
)


ANALYSIS_EXAMPLE = {
    "score": 80,
    "matched_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
    "missing_skills": ["AWS", "Kubernetes"],
    "strengths": ["Strong backend and AI tooling alignment."],
    "weaknesses": ["Limited cloud infrastructure evidence."],
    "recommendations": [
        "Clarify OpenAI API work as LLM application experience."
    ],
}


ENDPOINTS = [
    {
        "name": "analysis",
        "path": "/analyze",
        "payload": {
            "resume_text": RESUME_TEXT,
            "job_description": JOB_DESCRIPTION,
        },
    },
    {
        "name": "resume_review",
        "path": "/resume-review",
        "payload": {
            "resume_text": RESUME_TEXT,
            "job_description": JOB_DESCRIPTION,
            "analysis": ANALYSIS_EXAMPLE,
            "evidence": {},
        },
    },
    {
        "name": "cover_letter",
        "path": "/cover-letter",
        "payload": {
            "resume_text": RESUME_TEXT,
            "job_description": JOB_DESCRIPTION,
        },
    },
    {
        "name": "interview_prep",
        "path": "/interview-prep",
        "payload": {
            "resume_text": RESUME_TEXT,
            "job_description": JOB_DESCRIPTION,
        },
    },
]


def post_json(path, payload):
    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    start = time.time()

    with urllib.request.urlopen(request) as response:
        body = response.read().decode("utf-8")

    elapsed_ms = int((time.time() - start) * 1000)

    return json.loads(body), elapsed_ms

def estimate_cost(tokens_in, tokens_out):
    if tokens_in is None or tokens_out is None:
        return None

    input_cost = (tokens_in / 1_000_000) * GPT_4O_MINI_INPUT_COST_PER_1M
    output_cost = (tokens_out / 1_000_000) * GPT_4O_MINI_OUTPUT_COST_PER_1M

    return round(input_cost + output_cost, 6)

def main():
    results = []

    for endpoint in ENDPOINTS:
        try:
            response, measured_latency_ms = post_json(
                endpoint["path"],
                endpoint["payload"],
            )

            metadata = response.get("metadata", {})

            results.append(
                {
                    "name": endpoint["name"],
                    "path": endpoint["path"],
                    "status": metadata.get("status", "SUCCESS"),
                    "reported_latency_ms": metadata.get("latency_ms"),
                    "measured_latency_ms": measured_latency_ms,
                    "model": metadata.get("model"),
                    "prompt_version": metadata.get("prompt_version"),
                    "total_tokens": metadata.get("total_tokens"),
                    "tokens_in": metadata.get("tokens_in"),
                    "tokens_out": metadata.get("tokens_out"),
                    "estimated_cost_usd": estimate_cost(
                        metadata.get("tokens_in"),
                        metadata.get("tokens_out"),
                    ),
                }
            )

        except Exception as error:
            results.append(
                {
                    "name": endpoint["name"],
                    "path": endpoint["path"],
                    "status": "FAILED",
                    "error": f"{type(error).__name__}: {error}",
                }
            )

    successful = [item for item in results if item["status"] == "SUCCESS"]

    average_latency_ms = (
        round(
            sum(item["measured_latency_ms"] for item in successful)
            / len(successful),
            2,
        )
        if successful
        else None
    )

    report = {
        "summary": {
            "endpoint_count": len(results),
            "successful_endpoint_count": len(successful),
            "average_measured_latency_ms": average_latency_ms,
        },
        "endpoints": results,
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(report, indent=2))

    print(json.dumps(report["summary"], indent=2))
    print(f"\nSaved full report to {RESULTS_PATH}")


if __name__ == "__main__":
    main()