"""A/B evaluation of skill matching: LLM-only vs. LLM + deterministic verification.

    python evals/skill_matching_ab.py --repeats 3

Both arms read the same LLM output per case (skills/skill_matcher.py), so the
difference between them is the verifier alone. A taxonomy-only arm (the older
heuristic pipeline) is reported for reference.

Protocol
  1. Run the LLM on every dev and holdout case, `--repeats` times. Outputs are
     cached in evals/results/skill_match_llm_cache.json, keyed by model, prompt
     version, case text and repeat index.
  2. Sweep verifier settings on the dev split only and pick the best by pooled
     micro F1 (ties go to the more conservative setting).
  3. Apply that setting once to the holdout split and compare against LLM-only.

Scoring: each prediction is a (category, skill) pair, where category is one of
required_match, required_missing, preferred_match, preferred_missing. Micro
precision/recall/F1 are computed over all pairs pooled, and per category.

Requires OPENAI_API_KEY and DATABASE_URL (pgvector) in ai-service/.env.
"""

import argparse
import hashlib
import itertools
import json
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from llm import config as llm_config  # noqa: E402
from skills.extractor import extract_known_skills  # noqa: E402
from skills.job_requirements import extract_job_requirements  # noqa: E402
from skills.semantic_matcher import PgVectorSimilarity  # noqa: E402
from skills.skill_matcher import (  # noqa: E402
    PROMPT_VERSION,
    SkillClaim,
    VerifierConfig,
    check_claims,
    decide,
    extract_skill_claims,
)

DATA_DIR = ROOT / "evals" / "data"
RESULTS_DIR = ROOT / "evals" / "results"
CACHE_PATH = RESULTS_DIR / "skill_match_llm_cache.json"
SPLITS = {
    "dev": DATA_DIR / "skill_matching_cases.json",
    "holdout": DATA_DIR / "skill_matching_holdout_cases.json",
}
CATEGORIES = ["required_match", "required_missing", "preferred_match", "preferred_missing"]

SWEEP = {
    "skill_similarity": [0.60, 0.65, 0.70, 0.75, 0.78, 0.80, 0.85, 1.01],
    "evidence_similarity": [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 1.01],
    "resume_alias_overrides": [False, True],
}


def expected_pairs(case: dict) -> set[tuple[str, str]]:
    return {
        (category, skill.lower())
        for category in CATEGORIES
        for skill in case[f"expected_{category.replace('_match', '_matches')}"]
    }


def predicted_pairs(decisions: list[tuple[str, str, bool]]) -> set[tuple[str, str]]:
    """decisions: (skill, priority, present)."""
    return {(f"{priority}_{'match' if present else 'missing'}", skill.lower()) for skill, priority, present in decisions}


def counts(predicted: set, expected: set) -> dict:
    return {"tp": len(predicted & expected), "fp": len(predicted - expected), "fn": len(expected - predicted)}


def prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4), "tp": tp, "fp": fp, "fn": fn}


def score(per_case: list[tuple[set, set]]) -> dict:
    """per_case: list of (predicted, expected) pair sets. Returns pooled and per-category micro scores."""
    result = {}
    for category in [None, *CATEGORIES]:
        total = {"tp": 0, "fp": 0, "fn": 0}
        for predicted, expected in per_case:
            if category:
                predicted = {pair for pair in predicted if pair[0] == category}
                expected = {pair for pair in expected if pair[0] == category}
            for key, value in counts(predicted, expected).items():
                total[key] += value
        result[category or "pooled"] = prf(**total)
    return result


# ---------- LLM runs (cached) ----------


def cache_key(case: dict, repeat: int) -> str:
    text = json.dumps([llm_config.get_model(), PROMPT_VERSION, case["resume_text"], case["job_description"], repeat])
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def load_cache() -> dict:
    return json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}


def run_llm(cases: list[dict], repeats: int, cache: dict) -> tuple[dict, dict]:
    jobs = [(case, repeat) for case in cases for repeat in range(repeats) if cache_key(case, repeat) not in cache]
    usage = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "retries": 0}

    def work(job):
        case, repeat = job
        claims, metadata = extract_skill_claims(case["resume_text"], case["job_description"])
        return cache_key(case, repeat), [claim.model_dump() for claim in claims], metadata

    with ThreadPoolExecutor(max_workers=8) as pool:
        for key, claims, metadata in pool.map(work, jobs):
            cache[key] = claims
            usage["calls"] += 1
            usage["tokens_in"] += metadata.tokens_in
            usage["tokens_out"] += metadata.tokens_out
            usage["cost_usd"] += metadata.estimated_cost_usd or 0
            usage["retries"] += metadata.retries

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=1))
    usage["cost_usd"] = round(usage["cost_usd"], 6)
    return cache, usage


# ---------- arms ----------


def taxonomy_only(case: dict) -> list[tuple[str, str, bool]]:
    resume_skills = set(extract_known_skills(case["resume_text"]))
    requirements = extract_job_requirements(case["job_description"])
    return [
        (skill, priority, skill in resume_skills)
        for priority, key in (("required", "required_skills"), ("preferred", "preferred_skills"))
        for skill in requirements[key]
    ]


def arm_decisions(checks, mode: str, config: VerifierConfig | None = None) -> list[tuple[str, str, bool]]:
    return [(check.skill, check.priority, decide(check, mode, config)[0] if config else decide(check, mode)[0]) for check in checks]


def evaluate_arm(runs: list[dict], decide_fn) -> list[dict]:
    """runs: one entry per repeat, mapping case id -> (case, checks). Returns one score per repeat."""
    return [
        score([(predicted_pairs(decide_fn(checks)), expected_pairs(case)) for case, checks in run.values()])
        for run in runs
    ]


def mean_scores(scores: list[dict]) -> dict:
    summary = {}
    for section in scores[0]:
        summary[section] = {}
        for metric in ("precision", "recall", "f1"):
            values = [score[section][metric] for score in scores]
            summary[section][metric] = round(statistics.mean(values), 4)
            summary[section][f"{metric}_min"] = min(values)
            summary[section][f"{metric}_max"] = max(values)
    return summary


def case_errors(run: dict, decide_fn) -> list[dict]:
    errors = []
    for case_id, (case, checks) in run.items():
        predicted = predicted_pairs(decide_fn(checks))
        expected = expected_pairs(case)
        if predicted != expected:
            errors.append(
                {
                    "id": case_id,
                    "false_positives": sorted(f"{c}:{s}" for c, s in predicted - expected),
                    "false_negatives": sorted(f"{c}:{s}" for c, s in expected - predicted),
                }
            )
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    splits = {name: json.loads(path.read_text()) for name, path in SPLITS.items()}
    cache, usage = run_llm([case for cases in splits.values() for case in cases], args.repeats, load_cache())

    similarity = PgVectorSimilarity()
    runs = {name: [] for name in splits}
    try:
        for name, cases in splits.items():
            for repeat in range(args.repeats):
                run = {}
                for case in cases:
                    claims = [SkillClaim(**claim) for claim in cache[cache_key(case, repeat)]]
                    run[case["id"]] = (case, check_claims(claims, case["resume_text"], similarity))
                runs[name].append(run)
    finally:
        similarity.close()

    llm_only = lambda checks: arm_decisions(checks, "llm")  # noqa: E731

    # Sweep verifier settings on dev only.
    sweep_results = []
    for skill_sim, evidence_sim, overrides in itertools.product(*SWEEP.values()):
        config = VerifierConfig(skill_sim, evidence_sim, overrides)
        dev_scores = mean_scores(evaluate_arm(runs["dev"], lambda checks, c=config: arm_decisions(checks, "verified", c)))
        sweep_results.append((config, dev_scores["pooled"]["f1"]))

    # Best dev F1; ties go to higher thresholds, then to no alias override (fewer assumptions).
    best_config, best_dev_f1 = max(
        sweep_results,
        key=lambda item: (item[1], item[0].skill_similarity, item[0].evidence_similarity, not item[0].resume_alias_overrides),
    )
    verified = lambda checks: arm_decisions(checks, "verified", best_config)  # noqa: E731

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": llm_config.get_model(),
        "prompt_version": PROMPT_VERSION,
        "repeats": args.repeats,
        "case_counts": {name: len(cases) for name, cases in splits.items()},
        "llm_usage_this_run": usage,
        "chosen_on_dev": {
            "skill_similarity": best_config.skill_similarity,
            "evidence_similarity": best_config.evidence_similarity,
            "resume_alias_overrides": best_config.resume_alias_overrides,
            "dev_pooled_f1": best_dev_f1,
        },
        "splits": {},
    }

    for name in splits:
        taxonomy_scores = score([(predicted_pairs(taxonomy_only(case)), expected_pairs(case)) for case in splits[name]])
        report["splits"][name] = {
            "taxonomy_only": taxonomy_scores,
            "llm_only": mean_scores(evaluate_arm(runs[name], llm_only)),
            "llm_plus_verification": mean_scores(evaluate_arm(runs[name], verified)),
            "errors_repeat_0": {
                "llm_only": case_errors(runs[name][0], llm_only),
                "llm_plus_verification": case_errors(runs[name][0], verified),
            },
        }

    holdout = report["splits"]["holdout"]
    verified_f1 = holdout["llm_plus_verification"]["pooled"]["f1"]
    llm_f1 = holdout["llm_only"]["pooled"]["f1"]
    report["decision"] = {
        "holdout_pooled_f1_llm_only": llm_f1,
        "holdout_pooled_f1_verified": verified_f1,
        "verified_wins_on_holdout": verified_f1 > llm_f1,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_path = RESULTS_DIR / f"skill_matching_ab_{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2))

    print(f"model={report['model']} prompt={PROMPT_VERSION} repeats={args.repeats} cases={report['case_counts']}")
    print(f"LLM usage this run: {usage}")
    print(f"Chosen on dev: {report['chosen_on_dev']}")
    for name in splits:
        print(f"\n[{name}] pooled micro (mean over repeats, [min-max])")
        for arm in ("taxonomy_only", "llm_only", "llm_plus_verification"):
            pooled = report["splits"][name][arm]["pooled"]
            spread = f" f1[{pooled['f1_min']}-{pooled['f1_max']}]" if "f1_min" in pooled else ""
            print(f"  {arm:24} P={pooled['precision']:.3f} R={pooled['recall']:.3f} F1={pooled['f1']:.3f}{spread}")
    print(f"\nDecision: {report['decision']}")
    print(f"Report: {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
