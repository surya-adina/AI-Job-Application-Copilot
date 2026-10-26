"""Resume-tailoring agent built on LangGraph.

    plan -> rewrite -> verify --(every rewrite only rephrases its original)--> human_review -> END
                         ^          |
                         +- revise -+  (rewrite added a skill or number; budget and progress left)

* plan: match_skills, split the resume into units (bullets and summary
  sentences, wrapped PDF lines rejoined), then an LLM planner picks up to six
  units worth tailoring and what each should emphasize.
* rewrite / revise: rewrite_bullet for each chosen unit. A revision gets the
  checker's problems as plain feedback.
* verify: each rewrite may only state skills and numbers its own original line
  states. This is stricter than the cover-letter check, which allows any
  retrieved resume line as evidence.
* human_review: interrupt() until the user accepts, edits or keeps the
  original for each unit and names the new copy. The accepted text is spliced
  into the original resume at each unit's offsets; the original resume is
  never modified (the backend saves the result as a new resume).
"""

from __future__ import annotations

import json
import operator
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, interrupt
from pydantic import BaseModel

import psycopg
from agent.graph import MAX_REVISIONS, AgentConfig, _step, issue_keys
from llm import call_structured
from prompt_loader import load_prompt
from skills.claim_verifier import rewrite_problems
from skills.resume_units import apply_rewrites, resume_units
from tools import invoke

PLAN_PROMPT_VERSION = "tailor_plan_v1"
MAX_UNITS = 6
MIN_CANDIDATE_WORDS = 8


class TailorSelection(BaseModel):
    unit_id: int
    goal: str


class TailorPlan(BaseModel):
    selections: list[TailorSelection]


class TailoringState(TypedDict, total=False):
    task: str
    resume_id: str
    resume_text: str
    job_description: str
    instructions: str
    skills: dict
    plan: list[dict]
    drafts: dict
    verification: dict
    revisions: dict
    status: str
    decision: dict
    final_text: str | None
    trace: Annotated[list[dict], operator.add]
    steps: Annotated[int, operator.add]


SKILL_PROBLEM = re.compile(r"skill_not_in_evidence: (.+)")
NUMBER_PROBLEM = re.compile(r"number_not_in_evidence: (.+)")
WORDING_PROBLEM = re.compile(r"adds_wording: (.+)")


def readable_feedback(problems: list[str]) -> list[str]:
    feedback = []
    for problem in problems:
        if match := SKILL_PROBLEM.fullmatch(problem):
            feedback.append(f"Remove {match.group(1)}: the original line does not mention it.")
        elif match := NUMBER_PROBLEM.fullmatch(problem):
            feedback.append(f'Use the original line\'s numbers exactly; "{match.group(1)}" is not in it.')
        elif match := WORDING_PROBLEM.fullmatch(problem):
            feedback.append(
                f"Remove wording the original line does not support ({match.group(1)}). Do not add purpose, impact "
                "or fit-for-the-job clauses."
            )
        else:
            feedback.append("The rewrite was empty; rewrite the original line.")
    return feedback


def apply_decision(state: TailoringState, decision: dict) -> str:
    """The original resume with the user's accepted and edited rewrites spliced in."""
    units = resume_units(state["resume_text"])
    planned = {item["unit_id"] for item in state["plan"]}
    rewrites = {}
    for item in decision.get("items", []):
        unit_id = item["unit_id"]
        if unit_id not in planned:
            continue
        if item["choice"] == "accept":
            rewrites[unit_id] = state["drafts"][str(unit_id)]["text"]
        elif item["choice"] == "edit" and (item.get("text") or "").strip():
            rewrites[unit_id] = item["text"]
    return apply_rewrites(state["resume_text"], units, rewrites)


def build_tailoring_graph(config: AgentConfig | None = None, checkpointer=None):
    config = config or AgentConfig()
    context = config.tool_context

    def call_tool(name: str, arguments: dict) -> tuple[dict, list]:
        result = invoke(name, arguments, context)
        return result.output.model_dump(), result.runs

    def plan(state: TailoringState) -> dict:
        started = time.perf_counter()
        skills, runs = call_tool(
            "match_skills", {"resume_text": state["resume_text"], "job_description": state["job_description"]}
        )
        matched = [s["skill"] for s in skills["skills"] if s["present"]]
        missing_required = skills["missing_required_skills"]
        missing_preferred = skills["missing_preferred_skills"]

        candidates = [unit for unit in resume_units(state["resume_text"]) if len(unit.text.split()) >= MIN_CANDIDATE_WORDS]
        selections = []
        if candidates:
            result = call_structured(
                endpoint="agent:tailor_plan",
                prompt_version=PLAN_PROMPT_VERSION,
                system=load_prompt(PLAN_PROMPT_VERSION),
                user=json.dumps(
                    {
                        "job_description": state["job_description"],
                        "matched_skills": matched,
                        "missing_skills": missing_required + missing_preferred,
                        "instructions": state.get("instructions", ""),
                        "resume_units": [{"id": unit.id, "text": unit.text} for unit in candidates],
                    }
                ),
                schema=TailorPlan,
                temperature=0.2,
                max_output_tokens=800,
                **context.llm_kwargs,
            )
            runs.append(result.metadata)
            by_id = {unit.id: unit for unit in candidates}
            seen = set()
            for selection in result.parsed.selections:
                if selection.unit_id in by_id and selection.unit_id not in seen:
                    seen.add(selection.unit_id)
                    unit = by_id[selection.unit_id]
                    selections.append({"unit_id": unit.id, "original": unit.text, "goal": selection.goal})
            selections = selections[:MAX_UNITS]

        return {
            "skills": {"matched": matched, "missing_required": missing_required, "missing_preferred": missing_preferred},
            "plan": selections,
            "drafts": {},
            "verification": {},
            "revisions": {str(item["unit_id"]): 0 for item in selections},
            "trace": [_step("plan", started, runs, {"units": [item["unit_id"] for item in selections], "candidates": len(candidates)})],
            "steps": 1,
        }

    def _rewrite(state: TailoringState, item: dict, feedback: list[str]) -> tuple[str, dict, list]:
        goal = item["goal"]
        if state.get("instructions"):
            goal += f" Candidate instructions: {state['instructions']}"
        output, runs = call_tool(
            "rewrite_bullet",
            {"original": item["original"], "goal": goal, "job_description": state["job_description"], "feedback": feedback},
        )
        return str(item["unit_id"]), output, runs

    def _rewrite_many(state: TailoringState, jobs: list[tuple[dict, list[str]]]) -> tuple[dict, list]:
        drafts = dict(state.get("drafts", {}))
        runs = []
        with ThreadPoolExecutor(max_workers=max(1, config.parallelism)) as pool:
            for key, output, call_runs in pool.map(lambda job: _rewrite(state, *job), jobs):
                drafts[key] = output
                runs += call_runs
        return drafts, runs

    def rewrite(state: TailoringState) -> dict:
        started = time.perf_counter()
        drafts, runs = _rewrite_many(state, [(item, []) for item in state["plan"]])
        return {"drafts": drafts, "trace": [_step("rewrite", started, runs, {"units": list(drafts)})], "steps": 1}

    def verify(state: TailoringState) -> dict:
        started = time.perf_counter()
        verification = {}
        for item in state["plan"]:
            key = str(item["unit_id"])
            text = state["drafts"][key]["text"]
            problems = rewrite_problems(text, item["original"])
            verification[key] = {"passed": not problems, "problems": problems}

        revisions = dict(state.get("revisions", {}))
        previous = state.get("verification", {})
        stalled = [
            key
            for key, result in verification.items()
            if not result["passed"]
            and revisions.get(key, 0) > 0
            and key in previous
            and issue_keys(result["problems"]) == issue_keys(previous[key]["problems"])
        ]
        for key in stalled:
            revisions[key] = MAX_REVISIONS

        detail = {key: value for key, value in verification.items()}
        if stalled:
            detail["stopped_no_progress"] = stalled
        return {
            "verification": verification,
            "revisions": revisions,
            "trace": [_step("verify", started, detail=detail)],
            "steps": 1,
        }

    def failing(state: TailoringState) -> list[str]:
        return [key for key, result in state.get("verification", {}).items() if not result["passed"]]

    def revise(state: TailoringState) -> dict:
        started = time.perf_counter()
        keys = [key for key in failing(state) if state["revisions"][key] < MAX_REVISIONS]
        by_key = {str(item["unit_id"]): item for item in state["plan"]}
        jobs = [(by_key[key], readable_feedback(state["verification"][key]["problems"])) for key in keys]
        drafts, runs = _rewrite_many(state, jobs)
        revisions = {**state["revisions"], **{key: state["revisions"][key] + 1 for key in keys}}
        return {
            "drafts": drafts,
            "revisions": revisions,
            "trace": [_step("revise", started, runs, {"units": keys, "revisions": revisions})],
            "steps": 1,
        }

    def human_review(state: TailoringState) -> dict:
        # Runs again from the top on resume; keep everything before interrupt() side-effect free.
        decision = interrupt(
            {
                "items": [
                    {
                        "unit_id": item["unit_id"],
                        "goal": item["goal"],
                        "original": item["original"],
                        "rewritten": state["drafts"][str(item["unit_id"])]["text"],
                        "unchanged": state["drafts"][str(item["unit_id"])]["unchanged"],
                        "passed": state["verification"][str(item["unit_id"])]["passed"],
                        "problems": state["verification"][str(item["unit_id"])]["problems"],
                    }
                    for item in state["plan"]
                ],
                "matched_skills": state["skills"]["matched"],
                "missing_skills": state["skills"]["missing_required"] + state["skills"]["missing_preferred"],
            }
        )

        started = time.perf_counter()
        if decision["action"] == "save":
            final_text, status = apply_decision(state, decision), "completed"
        else:
            final_text, status = None, "rejected"

        choices = [item["choice"] for item in decision.get("items", [])]
        summary = {
            "action": decision["action"],
            "accepted": choices.count("accept"),
            "edited": choices.count("edit"),
            "kept_original": len(state["plan"]) - choices.count("accept") - choices.count("edit"),
        }
        return {
            "decision": decision,
            "final_text": final_text,
            "status": status,
            "trace": [_step("human_review", started, detail=summary)],
            "steps": 1,
        }

    def after_plan(state: TailoringState) -> str:
        return "rewrite" if state["plan"] else "human_review"

    def after_verify(state: TailoringState) -> str:
        keys = failing(state)
        if not keys:
            return "human_review"
        if any(state["revisions"][key] < MAX_REVISIONS for key in keys):
            return "revise"
        return "human_review"

    retry = RetryPolicy(max_attempts=3, initial_interval=0.5, retry_on=(ConnectionError, TimeoutError, psycopg.OperationalError))

    graph = StateGraph(TailoringState)
    graph.add_node("plan", plan, retry_policy=retry)
    graph.add_node("rewrite", rewrite, retry_policy=retry)
    graph.add_node("verify", verify)
    graph.add_node("revise", revise, retry_policy=retry)
    graph.add_node("human_review", human_review)

    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", after_plan, ["rewrite", "human_review"])
    graph.add_edge("rewrite", "verify")
    graph.add_conditional_edges("verify", after_verify, ["revise", "human_review"])
    graph.add_edge("revise", "verify")
    graph.add_edge("human_review", END)

    return graph.compile(checkpointer=checkpointer)
