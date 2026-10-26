"""Evaluation of the two agents and the checks they rely on.

    python evals/agent_eval.py                # everything (real OpenAI calls)
    python evals/agent_eval.py --skip-agents  # rewrite checker + judge validation only

1. Rewrite checker (deterministic). rewrite_problems() on 40 hand-labeled
   rewrites (evals/data/rewrite_faithfulness_cases.json). The added-wording
   threshold was chosen on six earlier examples; none of these cases were used
   to set it.
2. Judge validation. The model judge (evals/judge.py) labels the same 40
   rewrites; agreement with the human labels says how far to trust it below.
3. Agents end to end on 8 synthetic resume/job pairs
   (evals/data/agent_eval_cases.json). For each run the first drafts are read
   back from the LangGraph checkpoint history, so "without verification"
   (first drafts) and "with verification" (what the user is shown) come from
   the same run. The judge scores both.

The cover-letter agent normally searches resume chunks in Postgres; here the
same chunks are embedded with the same model and ranked by cosine similarity
in memory, so the eval needs no database rows.
"""

import argparse
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

import agent.graph as cover_module  # noqa: E402
from agent.graph import AgentConfig, build_graph, run_config  # noqa: E402
from agent.tailoring import build_tailoring_graph  # noqa: E402
from evals.judge import JUDGE_MODEL, judge_paragraph, judge_rewrite  # noqa: E402
from llm import config as llm_config  # noqa: E402
from skills.claim_verifier import rewrite_problems  # noqa: E402
from skills.embedding_client import embed  # noqa: E402
from skills.resume_chunks import chunk_resume  # noqa: E402
from tools import invoke as real_invoke  # noqa: E402
from tools.base import ToolResult  # noqa: E402
from tools.definitions import EvidenceChunk, SearchResumeEvidenceOutput  # noqa: E402

DATA = ROOT / "evals" / "data"
RESULTS = ROOT / "evals" / "results"


def rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def cost(runs: list[dict]) -> float:
    return sum(run.get("estimated_cost_usd") or 0 for run in runs)


def pmap(fn, items, workers=8):
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, items))


# ---------- 1 and 2: rewrite checker and judge on labeled cases ----------


def classification(predicted: list[bool], expected: list[bool]) -> dict:
    tp = sum(p and e for p, e in zip(predicted, expected))
    fp = sum(p and not e for p, e in zip(predicted, expected))
    fn = sum(not p and e for p, e in zip(predicted, expected))
    tn = sum(not p and not e for p, e in zip(predicted, expected))
    precision, recall = rate(tp, tp + fp), rate(tp, tp + fn)
    f1 = round(2 * precision * recall / (precision + recall), 3) if precision and recall else 0.0
    total = len(expected)
    observed = (tp + tn) / total
    chance = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (total * total)
    kappa = round((observed - chance) / (1 - chance), 3) if chance < 1 else None
    return {"precision": precision, "recall": recall, "f1": f1, "accuracy": round(observed, 3), "kappa": kappa,
            "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn}}


def evaluate_checker(cases: list[dict]) -> dict:
    flagged = [bool(rewrite_problems(case["rewrite"], case["original"])) for case in cases]
    expected = [case["adds_content"] for case in cases]
    by_kind = defaultdict(lambda: [0, 0])
    errors = []
    for case, flag in zip(cases, flagged):
        by_kind[case["kind"]][0] += flag == case["adds_content"]
        by_kind[case["kind"]][1] += 1
        if flag != case["adds_content"]:
            errors.append({"id": case["id"], "error": "missed_addition" if case["adds_content"] else "flagged_faithful_rewrite",
                           "problems": rewrite_problems(case["rewrite"], case["original"])})
    return {**classification(flagged, expected), "by_kind": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_kind.items())}, "errors": errors}


def evaluate_judge(cases: list[dict]) -> tuple[dict, list[dict]]:
    results = pmap(lambda case: judge_rewrite(case["original"], case["rewrite"]), cases)
    verdicts = [judgement.adds_content for judgement, _ in results]
    errors = [
        {"id": case["id"], "label": case["adds_content"], "judge": judgement.adds_content, "reason": judgement.reason}
        for case, (judgement, _) in zip(cases, results)
        if judgement.adds_content != case["adds_content"]
    ]
    runs = [metadata.model_dump() for _, metadata in results]
    return {**classification(verdicts, [case["adds_content"] for case in cases]), "errors": errors}, runs


# ---------- 3: agents end to end ----------


def run_steps(graph, config: dict) -> list[dict]:
    return graph.get_state(config).values.get("trace", [])


def state_after(graph, config: dict, node: str) -> dict | None:
    """State right after the first time `node` ran (history is newest first)."""
    matches = [
        snapshot.values
        for snapshot in graph.get_state_history(config)
        if snapshot.values.get("trace") and snapshot.values["trace"][-1]["node"] == node
    ]
    return matches[-1] if matches else None


def run_metrics(trace: list[dict], seconds: float) -> dict:
    runs = [run for step in trace for run in step["runs"]]
    return {
        "steps": len(trace),
        "llm_calls": len(runs),
        "retries": sum(run.get("retries", 0) for run in runs),
        "cost_usd": round(cost(runs), 6),
        "latency_s": round(seconds, 1),
        "revise_steps": sum(step["node"] == "revise" for step in trace),
    }


def eval_tailoring_case(case: dict) -> dict:
    graph = build_tailoring_graph(AgentConfig(parallelism=3), checkpointer=InMemorySaver())
    config = run_config(f"eval-tailor-{case['id']}")
    started = time.perf_counter()
    try:
        result = graph.invoke(
            {"resume_id": case["id"], "resume_text": case["resume"], "job_description": case["job"], "instructions": "",
             "trace": [], "steps": 0},
            config,
        )
    except Exception as error:  # a failed run is a result, not a crash of the eval
        return {"id": case["id"], "error": f"{type(error).__name__}: {error}"[:300]}
    seconds = time.perf_counter() - started

    review = result["__interrupt__"][0].value
    trace = run_steps(graph, config)
    first = state_after(graph, config, "rewrite") or {"drafts": {}}
    plan_detail = trace[0]["detail"]

    first_drafts = [
        {"original": item["original"], "text": first["drafts"][str(item["unit_id"])]["text"]}
        for item in review["items"]
        if str(item["unit_id"]) in first["drafts"] and not first["drafts"][str(item["unit_id"])]["unchanged"]
    ]
    applied = [{"original": item["original"], "text": item["rewritten"]} for item in review["items"] if item["passed"] and not item["unchanged"]]
    flagged = [item for item in review["items"] if not item["passed"]]

    judged_first = pmap(lambda d: judge_rewrite(d["original"], d["text"]), first_drafts, workers=6)
    judged_applied = pmap(lambda d: judge_rewrite(d["original"], d["text"]), applied, workers=6)
    judge_runs = [m.model_dump() for _, m in judged_first + judged_applied]

    return {
        "id": case["id"],
        "lines_selected": len(review["items"]),
        "planner_valid": rate(len(plan_detail["units"]), plan_detail["planner_returned"]),
        "first_drafts": len(first_drafts),
        "first_drafts_adding_content": sum(j.adds_content for j, _ in judged_first),
        "applied_by_default": len(applied),
        "applied_adding_content": sum(j.adds_content for j, _ in judged_applied),
        "applied_additions": [j.added for j, _ in judged_applied if j.adds_content],
        "flagged_at_review": len(flagged),
        "success": len(review["items"]) > 0 and not flagged,
        **run_metrics(trace, seconds),
        "judge_cost_usd": round(cost(judge_runs), 6),
    }


@contextmanager
def in_memory_evidence_search():
    """Replace the Postgres-backed search tool with the same chunks ranked in memory."""
    cache: dict[str, tuple[list, list]] = {}

    def fake_invoke(name, arguments, context=None):
        if name != "search_resume_evidence":
            return real_invoke(name, arguments, context)
        text = arguments["resume_text"]
        if text not in cache:
            chunks = chunk_resume(text)
            cache[text] = (chunks, embed([chunk.text for chunk in chunks]))
        chunks, vectors = cache[text]
        query = embed([arguments["query"]])[0]

        def cosine(vector):
            dot = sum(a * b for a, b in zip(vector, query))
            return dot / (math.sqrt(sum(a * a for a in vector)) * math.sqrt(sum(b * b for b in query)))

        ranked = sorted(zip(chunks, map(cosine, vectors)), key=lambda pair: pair[1], reverse=True)[: arguments.get("k", 5)]
        output = SearchResumeEvidenceOutput(
            chunks=[EvidenceChunk(id=c.index, text=c.text, start=c.start, end=c.end, similarity=round(s, 4)) for c, s in ranked],
            indexed_chunks=len(chunks),
        )
        return ToolResult(tool=name, output=output, runs=[], latency_ms=0)

    original = cover_module.invoke
    cover_module.invoke = fake_invoke
    try:
        yield
    finally:
        cover_module.invoke = original


def eval_cover_letter_case(case: dict) -> dict:
    graph = build_graph(AgentConfig(parallelism=3), checkpointer=InMemorySaver())
    config = run_config(f"eval-cover-{case['id']}")
    started = time.perf_counter()
    try:
        result = graph.invoke(
            {"resume_id": case["id"], "resume_text": case["resume"], "job_description": case["job"], "instructions": "",
             "trace": [], "steps": 0},
            config,
        )
    except Exception as error:
        return {"id": case["id"], "error": f"{type(error).__name__}: {error}"[:300]}
    seconds = time.perf_counter() - started

    review = result["__interrupt__"][0].value
    trace = run_steps(graph, config)
    first = state_after(graph, config, "draft") or {"drafts": {}}
    final = graph.get_state(config).values

    def cited_ids(drafts: dict) -> tuple[int, int]:
        total = sum(len(claim_ids) for draft in drafts.values() for claim_ids in [draft.get("unknown_evidence_ids", [])])
        cited = sum(len(claim["evidence"]) for draft in drafts.values() for claim in draft["claims"]) + total
        return cited - total, cited

    first_paragraphs = [draft["text"] for draft in first["drafts"].values()]
    final_paragraphs = [paragraph["text"] for paragraph in review["paragraphs"]]
    judged_first = pmap(lambda text: judge_paragraph(case["resume"], text), first_paragraphs, workers=3)
    judged_final = pmap(lambda text: judge_paragraph(case["resume"], text), final_paragraphs, workers=3)
    judge_runs = [m.model_dump() for _, m in judged_first + judged_final]
    valid_ids, all_ids = cited_ids(final["drafts"])

    return {
        "id": case["id"],
        "first_paragraphs_with_unsupported": sum(bool(j.unsupported_claims) for j, _ in judged_first),
        "first_unsupported_claims": sum(len(j.unsupported_claims) for j, _ in judged_first),
        "final_paragraphs_with_unsupported": sum(bool(j.unsupported_claims) for j, _ in judged_final),
        "final_unsupported_claims": sum(len(j.unsupported_claims) for j, _ in judged_final),
        "final_unsupported_examples": [claim for j, _ in judged_final for claim in j.unsupported_claims],
        "paragraphs": len(final_paragraphs),
        "unresolved_at_review": len(review["unresolved"]),
        "evidence_ids_valid": rate(valid_ids, all_ids),
        "success": not review["unresolved"],
        **run_metrics(trace, seconds),
        "judge_cost_usd": round(cost(judge_runs), 6),
    }


def summarize(rows: list[dict], keys: list[str]) -> dict:
    ok = [row for row in rows if "error" not in row]
    summary = {"cases": len(rows), "failed_runs": len(rows) - len(ok), "success_rate": rate(sum(row["success"] for row in ok), len(ok))}
    for key in keys:
        summary[f"total_{key}"] = sum(row[key] for row in ok)
    for key in ("steps", "llm_calls", "retries", "cost_usd", "latency_s", "revise_steps"):
        values = [row[key] for row in ok]
        summary[f"mean_{key}"] = round(statistics.mean(values), 4) if values else None
    summary["max_latency_s"] = max((row["latency_s"] for row in ok), default=None)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-agents", action="store_true")
    args = parser.parse_args()

    labeled = json.loads((DATA / "rewrite_faithfulness_cases.json").read_text())
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "agent_model": llm_config.get_model(), "judge_model": JUDGE_MODEL}

    report["rewrite_checker"] = evaluate_checker(labeled)
    judge_report, judge_runs = evaluate_judge(labeled)
    report["judge_validation"] = {**judge_report, "cost_usd": round(cost(judge_runs), 6)}

    if not args.skip_agents:
        agent_cases = json.loads((DATA / "agent_eval_cases.json").read_text())
        tailoring = [eval_tailoring_case(case) for case in agent_cases]
        with in_memory_evidence_search():
            cover = [eval_cover_letter_case(case) for case in agent_cases]

        t_ok = [row for row in tailoring if "error" not in row]
        report["tailoring"] = {
            "summary": {
                **summarize(tailoring, ["lines_selected", "first_drafts", "first_drafts_adding_content", "applied_by_default",
                                        "applied_adding_content", "flagged_at_review"]),
                "without_verification_adding_content_rate": rate(sum(r["first_drafts_adding_content"] for r in t_ok), sum(r["first_drafts"] for r in t_ok)),
                "with_verification_applied_adding_content_rate": rate(sum(r["applied_adding_content"] for r in t_ok), sum(r["applied_by_default"] for r in t_ok)),
                "planner_valid_selection_rate": rate(sum(r["planner_valid"] or 0 for r in t_ok), len(t_ok)),
            },
            "cases": tailoring,
        }
        c_ok = [row for row in cover if "error" not in row]
        report["cover_letter"] = {
            "summary": {
                **summarize(cover, ["paragraphs", "first_paragraphs_with_unsupported", "final_paragraphs_with_unsupported",
                                    "first_unsupported_claims", "final_unsupported_claims", "unresolved_at_review"]),
                "without_verification_paragraph_unsupported_rate": rate(sum(r["first_paragraphs_with_unsupported"] for r in c_ok), sum(r["paragraphs"] for r in c_ok)),
                "with_verification_paragraph_unsupported_rate": rate(sum(r["final_paragraphs_with_unsupported"] for r in c_ok), sum(r["paragraphs"] for r in c_ok)),
                "mean_evidence_ids_valid": rate(sum(r["evidence_ids_valid"] or 0 for r in c_ok), len(c_ok)),
            },
            "cases": cover,
        }

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"agent_eval_{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%SZ')}.json"
    out.write_text(json.dumps(report, indent=2))

    checker, judge = report["rewrite_checker"], report["judge_validation"]
    print(f"agent model={report['agent_model']} judge model={JUDGE_MODEL}")
    print(f"\n[rewrite checker, 40 labeled] precision={checker['precision']} recall={checker['recall']} f1={checker['f1']} accuracy={checker['accuracy']}")
    print(f"  by kind: {checker['by_kind']}")
    for error in checker["errors"]:
        print(f"  {error['error']}: {error['id']} {error['problems']}")
    print(f"\n[judge vs human labels] accuracy={judge['accuracy']} kappa={judge['kappa']} precision={judge['precision']} recall={judge['recall']} cost=${judge['cost_usd']}")
    for error in judge["errors"]:
        print(f"  disagrees on {error['id']} (label={error['label']}, judge={error['judge']}): {error['reason']}")
    for name in ("tailoring", "cover_letter"):
        if name in report:
            print(f"\n[{name}] " + json.dumps(report[name]["summary"]))
            for row in report[name]["cases"]:
                if "error" in row:
                    print(f"  FAILED {row['id']}: {row['error']}")
    print(f"\nReport: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
