import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from skills.extractor import extract_known_skills
from skills.job_requirements import extract_job_requirements


DEV_DATA_PATH = Path("evals/data/skill_matching_cases.json")
HOLDOUT_DATA_PATH = Path("evals/data/skill_matching_holdout_cases.json")
RESULTS_PATH = Path("evals/results/skill_matching_report.json")


def normalize(items):
    return {item.lower().strip() for item in items}


def score_prediction(predicted, expected):
    predicted_set = normalize(predicted)
    expected_set = normalize(expected)

    true_positive = len(predicted_set & expected_set)
    false_positive = len(predicted_set - expected_set)
    false_negative = len(expected_set - predicted_set)

    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 0
    )

    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 0
    )

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0
    )

    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
    }


def micro_score(results, metric_name):
    true_positive = sum(result[metric_name]["true_positive"] for result in results)
    false_positive = sum(result[metric_name]["false_positive"] for result in results)
    false_negative = sum(result[metric_name]["false_negative"] for result in results)

    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 0
    )

    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 0
    )

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0
    )

    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
    }


def build_summary(results):
    return {
        "case_count": len(results),
        "required_match_micro": micro_score(results, "required_match_score"),
        "required_missing_micro": micro_score(results, "required_missing_score"),
        "preferred_match_micro": micro_score(results, "preferred_match_score"),
        "preferred_missing_micro": micro_score(results, "preferred_missing_score"),
    }


def evaluate_cases(data_path, ignore_weak_context=True):
    cases = json.loads(data_path.read_text())
    results = []

    for case in cases:
        resume_skills = extract_known_skills(
            case["resume_text"],
            ignore_weak_context=ignore_weak_context,
        )

        job_requirements = extract_job_requirements(case["job_description"])

        required_skills = job_requirements["required_skills"]
        preferred_skills = job_requirements["preferred_skills"]

        required_matches = [
            skill for skill in required_skills if skill in resume_skills
        ]

        required_missing = [
            skill for skill in required_skills if skill not in resume_skills
        ]

        preferred_matches = [
            skill for skill in preferred_skills if skill in resume_skills
        ]

        preferred_missing = [
            skill for skill in preferred_skills if skill not in resume_skills
        ]

        results.append(
            {
                "id": case["id"],
                "required_match_score": score_prediction(
                    required_matches,
                    case["expected_required_matches"],
                ),
                "required_missing_score": score_prediction(
                    required_missing,
                    case["expected_required_missing"],
                ),
                "preferred_match_score": score_prediction(
                    preferred_matches,
                    case["expected_preferred_matches"],
                ),
                "preferred_missing_score": score_prediction(
                    preferred_missing,
                    case["expected_preferred_missing"],
                ),
                "predicted": {
                    "resume_skills": resume_skills,
                    "required_matches": required_matches,
                    "required_missing": required_missing,
                    "preferred_matches": preferred_matches,
                    "preferred_missing": preferred_missing,
                },
            }
        )

    return results

def build_improvement_summary(before, after):
    before_summary = build_summary(before)
    after_summary = build_summary(after)

    return {
        "holdout_case_count": after_summary["case_count"],
        "required_match_false_positives_before": before_summary[
            "required_match_micro"
        ]["false_positive"],
        "required_match_false_positives_after": after_summary[
            "required_match_micro"
        ]["false_positive"],
        "preferred_match_false_positives_before": before_summary[
            "preferred_match_micro"
        ]["false_positive"],
        "preferred_match_false_positives_after": after_summary[
            "preferred_match_micro"
        ]["false_positive"],
        "required_missing_recall_before": before_summary[
            "required_missing_micro"
        ]["recall"],
        "required_missing_recall_after": after_summary[
            "required_missing_micro"
        ]["recall"],
        "preferred_missing_recall_before": before_summary[
            "preferred_missing_micro"
        ]["recall"],
        "preferred_missing_recall_after": after_summary[
            "preferred_missing_micro"
        ]["recall"],
    }

def main():
    dev_results = evaluate_cases(
        DEV_DATA_PATH,
        ignore_weak_context=True,
    )

    holdout_without_guard = evaluate_cases(
        HOLDOUT_DATA_PATH,
        ignore_weak_context=False,
    )

    holdout_with_guard = evaluate_cases(
        HOLDOUT_DATA_PATH,
        ignore_weak_context=True,
    )

    combined_results = dev_results + holdout_with_guard

    report = {
        "dev": {
            "summary": build_summary(dev_results),
            "cases": dev_results,
        },
        "holdout_without_weak_context_guard": {
            "summary": build_summary(holdout_without_guard),
            "cases": holdout_without_guard,
        },
        "holdout_with_weak_context_guard": {
            "summary": build_summary(holdout_with_guard),
            "cases": holdout_with_guard,
        },
        "combined": {
            "summary": build_summary(combined_results),
        },
        "improvement": build_improvement_summary(
            holdout_without_guard,
            holdout_with_guard,
        ),
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(report, indent=2))

    print("DEV SUMMARY")
    print(json.dumps(report["dev"]["summary"], indent=2))

    print("\nHOLDOUT WITHOUT WEAK-CONTEXT GUARD")
    print(json.dumps(report["holdout_without_weak_context_guard"]["summary"], indent=2))

    print("\nHOLDOUT WITH WEAK-CONTEXT GUARD")
    print(json.dumps(report["holdout_with_weak_context_guard"]["summary"], indent=2))
    
    print("\nIMPROVEMENT SUMMARY")
    print(json.dumps(report["improvement"], indent=2))
    
    print("\nCOMBINED SUMMARY")
    print(json.dumps(report["combined"]["summary"], indent=2))

    print(f"\nSaved full report to {RESULTS_PATH}")


if __name__ == "__main__":
    main()