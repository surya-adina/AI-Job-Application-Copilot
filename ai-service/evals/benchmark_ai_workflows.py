import json
import statistics
import time
import argparse
from pathlib import Path

import requests

AI_SERVICE_URL = "http://localhost:8000"

RUNS_PER_ENDPOINT = 10

RESUME_TEXT = """
Surya Adina is a software engineer with experience in Python, TypeScript, React,
Next.js, NestJS, FastAPI, PostgreSQL, Prisma, Docker, AI/ML systems, RAG, NLP,
RoBERTa-based classification, and full-stack web applications.
"""

JOB_DESCRIPTION = """
We are hiring a full-stack engineer to build AI infrastructure and developer-facing
tools. The role involves Python, TypeScript, React, backend APIs, FastAPI or similar
frameworks, Docker, cloud infrastructure, and strong debugging skills. Go and
open-source SDK experience are preferred but not required.
"""

ANALYSIS_CONTEXT = {
    "score": 85,
    "matchedSkills": ["Python", "TypeScript", "React", "FastAPI", "PostgreSQL"],
    "missingSkills": ["Go", "Open-source SDKs"],
    "strengths": "Strong full-stack and AI project experience.",
    "weaknesses": "Limited direct Go and SDK contribution evidence.",
    "suggestions": {
        "recommendations": [
            "Mention FastAPI and full-stack AI projects clearly.",
            "Do not claim Go unless genuinely experienced."
        ]
    },
}

EVIDENCE_CONTEXT = {
    "matchedSkills": ["Python", "TypeScript", "React", "FastAPI", "PostgreSQL"],
    "missingSkills": ["Go", "Open-source SDKs"],
    "score": 85,
}


def estimate_cost_usd(tokens_in, tokens_out):
    # GPT-4o mini rough pricing used for internal benchmark estimates.
    if tokens_in is None or tokens_out is None:
        return None

    input_cost_per_1m = 0.15
    output_cost_per_1m = 0.60

    return (tokens_in / 1_000_000 * input_cost_per_1m) + (
        tokens_out / 1_000_000 * output_cost_per_1m
    )


def post_json(path, payload):
    started = time.time()
    response = requests.post(f"{AI_SERVICE_URL}{path}", json=payload, timeout=90)
    elapsed_ms = int((time.time() - started) * 1000)

    response.raise_for_status()
    data = response.json()

    metadata = data.get("metadata", {})
    tokens_in = metadata.get("tokens_in")
    tokens_out = metadata.get("tokens_out")
    total_tokens = metadata.get("total_tokens")

    return {
        "path": path,
        "success": True,
        "http_latency_ms": elapsed_ms,
        "service_latency_ms": metadata.get("latency_ms"),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "total_tokens": total_tokens,
        "estimated_cost_usd": estimate_cost_usd(tokens_in, tokens_out),
    }


def summarize(endpoint_name, rows):
    successful = [row for row in rows if row["success"]]

    latencies = [row["http_latency_ms"] for row in successful]
    service_latencies = [
        row["service_latency_ms"]
        for row in successful
        if row["service_latency_ms"] is not None
    ]
    total_tokens = [
        row["total_tokens"]
        for row in successful
        if row["total_tokens"] is not None
    ]
    costs = [
        row["estimated_cost_usd"]
        for row in successful
        if row["estimated_cost_usd"] is not None
    ]

    def p95(values):
        if not values:
            return None
        sorted_values = sorted(values)
        index = int(round(0.95 * (len(sorted_values) - 1)))
        return sorted_values[index]

    return {
        "endpoint": endpoint_name,
        "runs": len(rows),
        "successful_runs": len(successful),
        "success_rate": len(successful) / len(rows) if rows else 0,
        "avg_http_latency_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "p50_http_latency_ms": round(statistics.median(latencies), 2) if latencies else None,
        "p95_http_latency_ms": p95(latencies),
        "avg_service_latency_ms": round(statistics.mean(service_latencies), 2)
        if service_latencies
        else None,
        "avg_total_tokens": round(statistics.mean(total_tokens), 2)
        if total_tokens
        else None,
        "avg_estimated_cost_usd": round(statistics.mean(costs), 8) if costs else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--label",
        default="benchmark",
        help="Label for this benchmark run, for example baseline or interview_prep_optimized",
    )
    args = parser.parse_args()
    endpoints = {
        "analysis": (
            "/analyze",
            {
                "resume_text": RESUME_TEXT,
                "job_description": JOB_DESCRIPTION,
            },
        ),
        "resume_review": (
            "/resume-review",
            {
                "resume_text": RESUME_TEXT,
                "job_description": JOB_DESCRIPTION,
                "analysis": ANALYSIS_CONTEXT,
                "evidence": EVIDENCE_CONTEXT,
            },
        ),
        "cover_letter": (
            "/cover-letter",
            {
                "resume_text": RESUME_TEXT,
                "job_description": JOB_DESCRIPTION,
            },
        ),
        "interview_prep": (
            "/interview-prep",
            {
                "resume_text": RESUME_TEXT,
                "job_description": JOB_DESCRIPTION,
            },
        ),
    }

    all_results = {}
    summaries = []

    for endpoint_name, (path, payload) in endpoints.items():
        print(f"\nBenchmarking {endpoint_name}...")

        rows = []

        for run_number in range(1, RUNS_PER_ENDPOINT + 1):
            try:
                result = post_json(path, payload)
                rows.append(result)
                print(
                    f"  run {run_number}: {result['http_latency_ms']} ms, "
                    f"{result['total_tokens']} tokens"
                )
            except Exception as error:
                rows.append(
                    {
                        "path": path,
                        "success": False,
                        "error": f"{type(error).__name__}: {error}",
                    }
                )
                print(f"  run {run_number}: FAILED - {error}")

        all_results[endpoint_name] = rows
        summaries.append(summarize(endpoint_name, rows))

    output_dir = Path("ai-service/evals/results")
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_path = output_dir / f"{args.label}_ai_workflow_raw.json"
    summary_path = output_dir / f"{args.label}_ai_workflow_summary.json"

    raw_path.write_text(json.dumps(all_results, indent=2))
    summary_path.write_text(json.dumps(summaries, indent=2))

    print("\nSummary:")
    print(json.dumps(summaries, indent=2))

    print(f"\nSaved raw results to {raw_path}")
    print(f"Saved summary to {summary_path}")


if __name__ == "__main__":
    main()