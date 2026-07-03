import json
import time
from pathlib import Path
import requests
from datetime import datetime, timezone

SERVICE_URL = "http://localhost:8000/analyze"
CASES_PATH = Path(__file__).with_name("job_match_cases.json")
RESULTS_DIR = Path(__file__).parent / "results"
REGISTRY_PATH = Path(__file__).parent.parent / "prompts" / "prompt_registry.json"

def keyword_coverage(text_items: list[str], expected_keywords: list[str]) -> float:
    if not expected_keywords:
        return 1.0

    combined_text = " ".join(text_items).lower()

    hits = 0
    for keyword in expected_keywords:
        if keyword.lower() in combined_text:
            hits += 1

    return hits / len(expected_keywords)

def contains_expected_items(actual_items: list[str], expected_items: list[str]) -> float:
    if not expected_items:
        return 1.0

    normalized_actual = {item.lower() for item in actual_items}

    hits = 0
    for expected in expected_items:
        if expected.lower() in normalized_actual:
            hits += 1

    return hits / len(expected_items)


def run_case(case: dict, prompt_version: str) -> dict:
    started_at = time.perf_counter()

    response = requests.post(
        SERVICE_URL,
        json={
            "resume_text": case["resume_text"],
            "job_description": case["job_description"],
            "prompt_version": prompt_version,
        },
        timeout=30,
    )

    latency_ms = int((time.perf_counter() - started_at) * 1000)

    if response.status_code != 200:
        return {
            "id": case["id"],
            "passed": False,
            "error": f"HTTP {response.status_code}: {response.text}",
            "latency_ms": latency_ms,
        }

    body = response.json()
    analysis = body["analysis"]
    metadata = body["metadata"]

    matched_skill_recall = contains_expected_items(
        analysis["matched_skills"],
        case.get("expected_matched_skills", []),
    )

    missing_skill_recall = contains_expected_items(
        analysis["missing_skills"],
        case.get("expected_missing_skills", []),
    )

    score = analysis["score"]
    score_ok = True

    if "min_score" in case:
        score_ok = score >= case["min_score"]

    if "max_score" in case:
        score_ok = score <= case["max_score"]

    recommendation_quality = keyword_coverage(
        analysis["recommendations"],
        case.get("expected_recommendation_keywords", []),
    )

    passed = (
        matched_skill_recall >= 0.7
        and missing_skill_recall >= 0.7
        and recommendation_quality >= 0.6
        and score_ok
    )

    return {
        "id": case["id"],
        "passed": passed,
        "score": score,
        "matched_skill_recall": matched_skill_recall,
        "missing_skill_recall": missing_skill_recall,
        "score_ok": score_ok,
        "latency_ms": latency_ms,
        "estimated_cost_usd": metadata.get("estimated_cost_usd"),
        "model": metadata.get("model"),
        "prompt_version": metadata.get("prompt_version"),
        "recommendation_quality": recommendation_quality,
    }

def summarize_by_prompt(results: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = {}

    for result in results:
        prompt_version = result.get("prompt_version", "unknown")
        grouped.setdefault(prompt_version, []).append(result)

    summary = {}

    for prompt_version, prompt_results in grouped.items():
        total = len(prompt_results)
        passed = sum(1 for result in prompt_results if result["passed"])

        summary[prompt_version] = {
            "passed": passed,
            "total": total,
            "pass_rate": passed / total if total else 0,
            "avg_matched_skill_recall": sum(
                result.get("matched_skill_recall", 0) for result in prompt_results
            ) / total if total else 0,
            "avg_missing_skill_recall": sum(
                result.get("missing_skill_recall", 0) for result in prompt_results
            ) / total if total else 0,
            "avg_latency_ms": sum(
                result.get("latency_ms", 0) for result in prompt_results
            ) / total if total else 0,
            "total_estimated_cost_usd": sum(
                result.get("estimated_cost_usd") or 0 for result in prompt_results
            ),
            "avg_recommendation_quality": sum(
                result.get("recommendation_quality", 0) for result in prompt_results
            ) / total if total else 0,
        }

    return summary

def choose_best_prompt(summary_by_prompt: dict) -> str | None:
    if not summary_by_prompt:
        return None

    ranked = sorted(
        summary_by_prompt.items(),
        key=lambda item: (
            item[1]["pass_rate"],
            item[1]["avg_missing_skill_recall"],
            item[1]["avg_matched_skill_recall"],
            -item[1]["avg_latency_ms"],
            -item[1]["total_estimated_cost_usd"],
        ),
        reverse=True,
    )

    return ranked[0][0]

def main():
    cases = json.loads(CASES_PATH.read_text())
    prompt_registry = json.loads(REGISTRY_PATH.read_text())
    prompt_versions = ["analysis_v1", "analysis_v2"]

    results = []
    for prompt_version in prompt_versions:
        for case in cases:
            results.append(run_case(case, prompt_version))

    passed_count = sum(1 for result in results if result["passed"])
    total_count = len(results)
    by_prompt_version = summarize_by_prompt(results)
    best_prompt_version = choose_best_prompt(by_prompt_version)
    report = {
        "summary": {
            "passed": passed_count,
            "total": total_count,
            "pass_rate": passed_count / total_count if total_count else 0,
            "by_prompt_version": by_prompt_version,
            "best_prompt_version": best_prompt_version,
        },
        "prompt_registry": prompt_registry,
        "results": results,
    }

    RESULTS_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    output_path = RESULTS_DIR / f"job_match_eval_{timestamp}.json"

    output_path.write_text(json.dumps(report, indent=2))

    print(json.dumps(report, indent=2))
    print(f"\nSaved eval report to: {output_path}")


if __name__ == "__main__":
    main()