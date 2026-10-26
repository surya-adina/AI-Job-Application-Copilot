"""Cover-letter agent built on LangGraph.

    plan -> gather_evidence -> draft -> verify --(all claims supported)--> human_review -> END
                                          ^          |
                                          |    (some claim rejected and
                                          +-- revise  revision budget left)

* plan: match_skills, then an LLM planner picks a goal and an evidence query
  for each of the three paragraphs.
* gather_evidence: search_resume_evidence for each query (pgvector).
* draft / revise: draft_section from the retrieved resume chunks. A revision
  gets the verifier's reasons as feedback.
* verify: verify_claims. A paragraph passes only when every claim is backed by
  its cited resume chunks.
* human_review: interrupt() pauses the run until a person approves, edits or
  rejects. Paragraphs still failing verification after MAX_REVISIONS are shown
  to the reviewer as unresolved instead of being silently accepted.

Every node appends one entry to `trace` with its latency and the metadata of
each LLM call it made; the backend stores these as AgentStep and AiRun rows.
State holds plain JSON-compatible values so the Postgres checkpointer can
persist it between the pause and the resume.
"""

from __future__ import annotations

import json
import operator
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict

import psycopg
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, interrupt
from pydantic import BaseModel

from llm import call_structured
from prompt_loader import load_prompt
from skills.claim_verifier import supported_by, unsupported_facts
from skills.extractor import extract_known_skills
from skills.resume_chunks import chunk_resume
from tools import ToolContext, invoke

PLAN_PROMPT_VERSION = "agent_plan_v1"
SECTION_KEYS = ["p1", "p2", "p3"]
MAX_REVISIONS = 2
# Upper bound on node executions: plan, gather, draft, verify, MAX_REVISIONS x
# (revise, verify), human_review. The graph also gets a recursion_limit.
MAX_STEPS = 5 + 2 * MAX_REVISIONS + 1
EVIDENCE_PER_SECTION = 5
GREETING = "Dear Hiring Manager,"
CLOSING = "Thank you for considering my application. I would welcome the chance to discuss how my experience fits this role."


class PlannedSection(BaseModel):
    goal: str
    evidence_query: str


class AgentPlan(BaseModel):
    sections: list[PlannedSection]


class AgentState(TypedDict, total=False):
    task: str
    resume_id: str
    resume_text: str
    job_description: str
    instructions: str
    skills: dict
    plan: list[dict]
    evidence: dict
    drafts: dict
    verification: dict
    revisions: dict
    status: str
    decision: dict
    final_text: str | None
    trace: Annotated[list[dict], operator.add]
    steps: Annotated[int, operator.add]


@dataclass
class AgentConfig:
    tool_context: ToolContext = field(default_factory=ToolContext)
    parallelism: int = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _step(node: str, started: float, runs: list | None = None, detail: Any = None) -> dict:
    return {
        "node": node,
        "status": "ok",
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "runs": [run.model_dump() for run in runs or []],
        "detail": detail,
        "finished_at": _now(),
    }


def assemble_letter(state: AgentState) -> str:
    paragraphs = [state["drafts"][key]["text"].strip() for key in SECTION_KEYS if key in state.get("drafts", {})]
    return "\n\n".join([GREETING, *paragraphs, CLOSING])


ISSUE_PATTERN = re.compile(
    r"(?:skill|number)_not_in_evidence: [^;\"]+|adds_wording: [^;\"]+|empty_rewrite|quote_not_in_resume|quote_is_hedged"
    r"|no_evidence|unknown evidence id \d+"
)
MISSING_SKILL_PATTERN = re.compile(r"skill_not_in_evidence: ([^;\"]+)")
EVIDENCE_PER_MISSING_SKILL = 2


def issue_keys(problems: list[str]) -> set[str]:
    """The kinds of problem a paragraph has, ignoring how its claims are worded,
    so two drafts with the same unsupported skill compare equal."""
    return {issue.strip() for issue in ISSUE_PATTERN.findall(" ".join(problems))}


def resume_lines_for_skills(resume_text: str, skills: list[str], known_ids: set[int]) -> dict[str, list[dict]]:
    """For each skill, resume chunks that state it (outside hedged phrases).
    Chunk ids match search_resume_evidence, which indexes the same chunks."""
    chunks = chunk_resume(resume_text)
    found = {}
    for skill in skills:
        matches = [
            {"id": chunk.index, "text": chunk.text}
            for chunk in chunks
            if chunk.index not in known_ids and supported_by(skill, set(extract_known_skills(chunk.text)))
        ]
        found[skill] = matches[:EVIDENCE_PER_MISSING_SKILL]
    return found


def failing_sections(state: AgentState) -> list[str]:
    return [key for key, result in state.get("verification", {}).items() if not result["passed"]]


def build_graph(config: AgentConfig | None = None, checkpointer=None):
    config = config or AgentConfig()
    context = config.tool_context

    def call_tool(name: str, arguments: dict) -> tuple[dict, list]:
        result = invoke(name, arguments, context)
        return result.output.model_dump(), result.runs

    # ---------- nodes ----------

    def plan(state: AgentState) -> dict:
        started = time.perf_counter()
        skills, runs = call_tool(
            "match_skills", {"resume_text": state["resume_text"], "job_description": state["job_description"]}
        )
        matched = [s["skill"] for s in skills["skills"] if s["present"]]
        missing = [s["skill"] for s in skills["skills"] if not s["present"]]

        result = call_structured(
            endpoint="agent:plan",
            prompt_version=PLAN_PROMPT_VERSION,
            system=load_prompt(PLAN_PROMPT_VERSION),
            user=json.dumps(
                {
                    "job_description": state["job_description"],
                    "matched_skills": matched,
                    "missing_skills": missing,
                    "instructions": state.get("instructions", ""),
                }
            ),
            schema=AgentPlan,
            temperature=0.2,
            max_output_tokens=600,
            **context.llm_kwargs,
        )
        sections = result.parsed.sections[: len(SECTION_KEYS)]
        if not sections:
            raise ValueError("Planner returned no sections")

        planned = [{"key": key, **section.model_dump()} for key, section in zip(SECTION_KEYS, sections)]
        return {
            "skills": {"matched": matched, "missing": missing},
            "plan": planned,
            "revisions": {item["key"]: 0 for item in planned},
            "trace": [_step("plan", started, [*runs, result.metadata], {"plan": planned, "matched": matched, "missing": missing})],
            "steps": 1,
        }

    def gather_evidence(state: AgentState) -> dict:
        started = time.perf_counter()
        evidence = {}
        for item in state["plan"]:
            output, _ = call_tool(
                "search_resume_evidence",
                {
                    "resume_id": state["resume_id"],
                    "resume_text": state["resume_text"],
                    "query": item["evidence_query"],
                    "k": EVIDENCE_PER_SECTION,
                },
            )
            evidence[item["key"]] = [{"id": chunk["id"], "text": chunk["text"]} for chunk in output["chunks"]]

        detail = {key: [chunk["id"] for chunk in chunks] for key, chunks in evidence.items()}
        return {"evidence": evidence, "trace": [_step("gather_evidence", started, detail=detail)], "steps": 1}

    def _draft(state: AgentState, key: str, feedback: list[str] | None) -> tuple[str, dict, list]:
        item = next(section for section in state["plan"] if section["key"] == key)
        instructions = item["goal"]
        if state.get("instructions"):
            instructions += f"\nCandidate instructions: {state['instructions']}"
        if feedback:
            previous = state["drafts"][key]["text"]
            instructions += (
                "\nYour previous draft was rejected by the fact checker:\n"
                + previous
                + "\nProblems:\n- "
                + "\n- ".join(feedback)
                + "\nRewrite the paragraph so every claim is supported by the evidence exactly as written "
                "(copy numbers and tool names as they appear), or drop the unsupported claim."
            )

        output, runs = call_tool(
            "draft_section",
            {
                "section": "cover_letter_paragraph",
                "instructions": instructions,
                "job_description": state["job_description"],
                "evidence": state["evidence"][key],
            },
        )
        return key, output, runs

    def _draft_many(state: AgentState, jobs: list[tuple[str, list[str] | None]]) -> tuple[dict, list]:
        drafts = dict(state.get("drafts", {}))
        runs = []
        with ThreadPoolExecutor(max_workers=max(1, config.parallelism)) as pool:
            for key, output, call_runs in pool.map(lambda job: _draft(state, *job), jobs):
                drafts[key] = output
                runs += call_runs
        return drafts, runs

    def draft(state: AgentState) -> dict:
        started = time.perf_counter()
        drafts, runs = _draft_many(state, [(item["key"], None) for item in state["plan"]])
        return {"drafts": drafts, "trace": [_step("draft", started, runs, {"sections": list(drafts)})], "steps": 1}

    def verify(state: AgentState) -> dict:
        started = time.perf_counter()
        verification = {}
        for key, result in state["drafts"].items():
            problems = [f"cites unknown evidence id {i}" for i in result.get("unknown_evidence_ids", [])]
            # Check the paragraph text too: the model's claim list may leave statements out.
            section_evidence = [chunk["text"] for chunk in state["evidence"][key]]
            problems += [f"paragraph text: {problem}" for problem in unsupported_facts(result["text"], section_evidence)]
            verdicts = []
            if result["claims"]:
                output, _ = call_tool("verify_claims", {"resume_text": state["resume_text"], "claims": result["claims"]})
                verdicts = output["verdicts"]
                problems += [
                    f'"{verdict["text"]}": {"; ".join(verdict["reasons"])}' for verdict in verdicts if not verdict["supported"]
                ]
            verification[key] = {"passed": not problems, "problems": problems, "verdicts": verdicts}

        # A revision that leaves the same issues will not be fixed by another
        # one: stop revising that paragraph and let the reviewer decide.
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

        detail = {key: {"passed": value["passed"], "problems": value["problems"]} for key, value in verification.items()}
        if stalled:
            detail["stopped_no_progress"] = stalled
        return {
            "verification": verification,
            "revisions": revisions,
            "trace": [_step("verify", started, detail=detail)],
            "steps": 1,
        }

    def revise(state: AgentState) -> dict:
        started = time.perf_counter()
        keys = [key for key in failing_sections(state) if state["revisions"][key] < MAX_REVISIONS]

        # Before redrafting, look up each unsupported skill in the whole resume:
        # the section's search may simply have missed the line that states it.
        evidence = {key: list(chunks) for key, chunks in state["evidence"].items()}
        jobs, added = [], {}
        for key in keys:
            problems = state["verification"][key]["problems"]
            skills = sorted(set(MISSING_SKILL_PATTERN.findall(" ".join(problems))))
            known_ids = {chunk["id"] for chunk in evidence[key]}
            feedback = list(problems)

            for skill, lines in resume_lines_for_skills(state["resume_text"], skills, known_ids).items():
                if lines:
                    evidence[key] += lines
                    added.setdefault(key, []).extend(line["id"] for line in lines)
                    ids = ", ".join(str(line["id"]) for line in lines)
                    feedback.append(f"The resume does state {skill}: evidence id {ids} was added. Cite it for that claim.")
                else:
                    feedback.append(f"The resume never mentions {skill}. Remove it from the paragraph.")
            jobs.append((key, feedback))

        drafts, runs = _draft_many({**state, "evidence": evidence}, jobs)
        revisions = {**state["revisions"], **{key: state["revisions"][key] + 1 for key in keys}}
        return {
            "drafts": drafts,
            "evidence": evidence,
            "revisions": revisions,
            "trace": [_step("revise", started, runs, {"sections": keys, "revisions": revisions, "evidence_added": added})],
            "steps": 1,
        }

    def human_review(state: AgentState) -> dict:
        # Everything before interrupt() runs again when the graph resumes, so
        # this part must stay free of side effects.
        unresolved = {key: state["verification"][key]["problems"] for key in failing_sections(state)}
        decision = interrupt(
            {
                "letter": assemble_letter(state),
                "paragraphs": [
                    {
                        "key": key,
                        "text": state["drafts"][key]["text"],
                        "claims": state["verification"][key]["verdicts"],
                        "passed": state["verification"][key]["passed"],
                    }
                    for key in SECTION_KEYS
                    if key in state["drafts"]
                ],
                "unresolved": unresolved,
                "revisions": state["revisions"],
            }
        )

        started = time.perf_counter()
        action = decision["action"]
        if action == "approve":
            final_text, status = assemble_letter(state), "completed"
        elif action == "edit":
            final_text, status = decision["text"].strip(), "completed"
        else:
            final_text, status = None, "rejected"

        return {
            "decision": decision,
            "final_text": final_text,
            "status": status,
            "trace": [_step("human_review", started, detail={"action": action, "unresolved_sections": list(unresolved)})],
            "steps": 1,
        }

    # ---------- routing ----------

    def after_verify(state: AgentState) -> str:
        failing = failing_sections(state)
        if not failing:
            return "human_review"
        if state.get("steps", 0) + 2 > MAX_STEPS:  # revise + verify must still fit before review
            return "human_review"
        if any(state["revisions"][key] < MAX_REVISIONS for key in failing):
            return "revise"
        return "human_review"

    # Transient infrastructure errors are retried per node. LLM calls already
    # retry inside the client, so LLMCallError is not retried again here.
    retry = RetryPolicy(max_attempts=3, initial_interval=0.5, retry_on=(ConnectionError, TimeoutError, psycopg.OperationalError))

    graph = StateGraph(AgentState)
    graph.add_node("plan", plan, retry_policy=retry)
    graph.add_node("gather_evidence", gather_evidence, retry_policy=retry)
    graph.add_node("draft", draft, retry_policy=retry)
    graph.add_node("verify", verify)
    graph.add_node("revise", revise, retry_policy=retry)
    graph.add_node("human_review", human_review)

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "gather_evidence")
    graph.add_edge("gather_evidence", "draft")
    graph.add_edge("draft", "verify")
    graph.add_conditional_edges("verify", after_verify, ["revise", "human_review"])
    graph.add_edge("revise", "verify")
    graph.add_edge("human_review", END)

    return graph.compile(checkpointer=checkpointer)


def run_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": MAX_STEPS + 5}
