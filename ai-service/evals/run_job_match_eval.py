import json
import time
from pathlib import Path
import requests


SERVICE_URL = "http://localhost:8000/analyze"
CASES_PATH = Path(__file__).with_name("job_match_cases.json")


def contains_expected_items(actual_items: list[str], expected_items: list[str]) -> float:
    if not expected_items:
        return 1.0

    normalized_actual = {item.lower() for item in actual_items}

    hits = 0
    for expected in expected_items:
        if expected.lower() in normalized_actual:
            hits += 1

    return hits / len(expected_items)


def run_case(case: dict) -> dict:
    started_at = time.perf_counter()

    response = requests.post(
        SERVICE_URL,
        json={
            "resume_text": case["resume_text"],
            "job_description": case["job_description"],
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

    passed = (
        matched_skill_recall >= 0.7
        and missing_skill_recall >= 0.7
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
    }


def main():
    cases = json.loads(CASES_PATH.read_text())

    results = [run_case(case) for case in cases]

    passed_count = sum(1 for result in results if result["passed"])
    total_count = len(results)

    print(json.dumps(
        {
            "summary": {
                "passed": passed_count,
                "total": total_count,
                "pass_rate": passed_count / total_count if total_count else 0,
            },
            "results": results,
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()