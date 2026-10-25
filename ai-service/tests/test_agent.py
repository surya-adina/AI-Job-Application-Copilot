import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import main
from agent import graph as agent_graph
from agent.graph import CLOSING, GREETING, MAX_REVISIONS, AgentConfig, build_graph, run_config
from routes import agent as agent_routes
from tests.conftest import TEST_SERVICE_TOKEN
from tests.fakes import FakeAPIError, FakeClient, ok
from tools import ToolContext
from tools import invoke as real_invoke

FASTAPI = "Built FastAPI microservices handling 2M requests/day for shipment tracking."
POSTGRES = "Designed PostgreSQL schemas and cut p95 query latency by 40% with indexing."
RESUME = f"Jordan Lee\nBackend engineer.\n- {FASTAPI}\n- {POSTGRES}\n- Wrote Python services for logistics teams.\n"
JOB = "Backend Engineer. Build high-volume Python APIs with FastAPI and PostgreSQL. Kubernetes is a plus."

LLM_KWARGS = dict(model="gpt-4o-mini", max_retries=0, sleep=lambda _s: None)

SKILLS = ok(
    {
        "skills": [
            {"skill": "FastAPI", "priority": "required", "in_resume": True, "resume_evidence": "Built FastAPI microservices"},
            {"skill": "Kubernetes", "priority": "preferred", "in_resume": False, "resume_evidence": None},
        ]
    }
)
PLAN = ok(
    {
        "sections": [
            {"goal": "Strongest fit: FastAPI.", "evidence_query": "FastAPI services"},
            {"goal": "Experiences: PostgreSQL performance.", "evidence_query": "PostgreSQL latency"},
            {"goal": "Why this role.", "evidence_query": "Python services"},
        ]
    }
)


def draft(text, claim=None, ids=(0,)):
    claims = [{"text": claim, "evidence_ids": list(ids)}] if claim else []
    return ok({"text": text, "claims": claims})


GOOD = [
    draft("I built FastAPI services handling 2M requests/day.", "Built FastAPI services handling 2M requests/day.", [0]),
    draft("I cut PostgreSQL p95 latency by 40%.", "Cut PostgreSQL p95 latency by 40%.", [1]),
    draft("I am excited about this backend role."),
]
BAD_P2 = draft("I cut PostgreSQL latency by 60%.", "Cut PostgreSQL latency by 60%.", [1])


@pytest.fixture(autouse=True)
def fake_evidence_search(monkeypatch):
    def fake_invoke(name, arguments, context=None):
        if name == "search_resume_evidence":
            from tools.base import ToolResult
            from tools.definitions import EvidenceChunk, SearchResumeEvidenceOutput

            chunks = [EvidenceChunk(id=0, text=FASTAPI, start=0, end=1, similarity=0.9),
                      EvidenceChunk(id=1, text=POSTGRES, start=0, end=1, similarity=0.8)]
            return ToolResult(tool=name, output=SearchResumeEvidenceOutput(chunks=chunks, indexed_chunks=2), runs=[], latency_ms=1)
        return real_invoke(name, arguments, context)

    monkeypatch.setattr(agent_graph, "invoke", fake_invoke)


def make_graph(*script):
    context = ToolContext(llm_kwargs=dict(client=FakeClient(*script), **LLM_KWARGS))
    return build_graph(AgentConfig(tool_context=context, parallelism=1), checkpointer=InMemorySaver())


def start(graph, thread_id="thread-0001"):
    initial = {"resume_id": "r1", "resume_text": RESUME, "job_description": JOB, "instructions": "", "trace": [], "steps": 0}
    return graph.invoke(initial, run_config(thread_id))


def nodes(graph, thread_id="thread-0001"):
    return [step["node"] for step in graph.get_state(run_config(thread_id)).values["trace"]]


def test_happy_path_pauses_for_review_then_completes_on_approve():
    graph = make_graph(SKILLS, PLAN, *GOOD)
    result = start(graph)

    review = result["__interrupt__"][0].value
    assert review["unresolved"] == {}
    assert review["letter"].startswith(GREETING) and review["letter"].endswith(CLOSING)
    assert nodes(graph) == ["plan", "gather_evidence", "draft", "verify"]

    graph.invoke(Command(resume={"action": "approve", "text": None}), run_config("thread-0001"))
    state = graph.get_state(run_config("thread-0001")).values
    assert state["status"] == "completed"
    assert "2M requests/day" in state["final_text"]
    assert nodes(graph)[-1] == "human_review"

    trace = state["trace"]
    assert [run["endpoint"] for run in trace[0]["runs"]] == ["skill:match", "agent:plan"]
    assert len(trace[2]["runs"]) == 3  # one draft_section call per paragraph


def test_rejected_claim_is_revised_with_feedback():
    fixed = draft("I cut PostgreSQL p95 latency by 40%.", "Cut PostgreSQL p95 latency by 40%.", [1])
    client_script = [SKILLS, PLAN, GOOD[0], BAD_P2, GOOD[2], fixed]
    graph = make_graph(*client_script)
    result = start(graph)

    assert result["__interrupt__"][0].value["unresolved"] == {}
    assert nodes(graph) == ["plan", "gather_evidence", "draft", "verify", "revise", "verify"]

    state = graph.get_state(run_config("thread-0001")).values
    assert state["revisions"] == {"p1": 0, "p2": 1, "p3": 0}
    assert "number_not_in_evidence: 60%" in state["trace"][3]["detail"]["p2"]["problems"][0]


def test_revision_without_progress_stops_early():
    # The same unsupported number comes back after a revision: a second revision would be wasted.
    graph = make_graph(SKILLS, PLAN, GOOD[0], BAD_P2, GOOD[2], BAD_P2)
    review = start(graph)["__interrupt__"][0].value

    assert list(review["unresolved"]) == ["p2"]
    assert nodes(graph).count("revise") == 1
    trace = graph.get_state(run_config("thread-0001")).values["trace"]
    assert trace[-1]["detail"]["stopped_no_progress"] == ["p2"]


def test_revisions_continue_while_problems_change_up_to_the_limit():
    other_bad = draft("I cut PostgreSQL latency by 70%.", "Cut PostgreSQL latency by 70%.", [1])
    graph = make_graph(SKILLS, PLAN, GOOD[0], BAD_P2, GOOD[2], other_bad, BAD_P2)
    review = start(graph)["__interrupt__"][0].value

    assert list(review["unresolved"]) == ["p2"]
    assert review["revisions"]["p2"] == MAX_REVISIONS
    assert nodes(graph).count("revise") == MAX_REVISIONS


def test_revise_adds_resume_lines_for_skills_the_search_missed():
    # Python is in the resume, but the section's search results (FASTAPI, POSTGRES) do not mention it.
    python_claim = draft("I write Python services.", "Writes Python services.", [0])
    fixed = draft("I write Python services.", "Writes Python services.", [2])
    graph = make_graph(SKILLS, PLAN, python_claim, *GOOD[1:], fixed)
    review = start(graph)["__interrupt__"][0].value

    state = graph.get_state(run_config("thread-0001")).values
    revise_step = next(step for step in state["trace"] if step["node"] == "revise")
    assert revise_step["detail"]["evidence_added"] == {"p1": [2]}
    assert any("Python services" in chunk["text"] for chunk in state["evidence"]["p1"])
    assert review["unresolved"] == {}


@pytest.mark.parametrize(
    "decision, status, final_text",
    [
        ({"action": "edit", "text": "  My own letter.  "}, "completed", "My own letter."),
        ({"action": "reject", "text": None}, "rejected", None),
    ],
)
def test_edit_and_reject(decision, status, final_text):
    graph = make_graph(SKILLS, PLAN, *GOOD)
    start(graph)
    graph.invoke(Command(resume=decision), run_config("thread-0001"))

    state = graph.get_state(run_config("thread-0001")).values
    assert (state["status"], state["final_text"]) == (status, final_text)


# ---------- HTTP routes ----------


@pytest.fixture
def http(monkeypatch):
    holder = {}

    def use_graph(*script):
        holder["graph"] = make_graph(*script)

    monkeypatch.setattr(agent_routes, "get_graph", lambda: holder["graph"])
    client = TestClient(main.app, headers={"X-Service-Token": TEST_SERVICE_TOKEN})
    return client, use_graph


BODY = {"thread_id": "run-12345678", "resume_id": "r1", "resume_text": RESUME, "job_description": JOB}


def test_routes_start_review_and_resume(http):
    client, use_graph = http
    use_graph(SKILLS, PLAN, *GOOD)

    started = client.post("/agent/runs", json=BODY).json()
    assert started["status"] == "awaiting_review"
    assert len(started["steps"]) == 4

    assert client.post("/agent/runs", json=BODY).status_code == 409  # same thread id again
    assert client.post("/agent/runs/run-12345678/resume", json={"action": "edit"}).status_code == 422

    finished = client.post("/agent/runs/run-12345678/resume", json={"action": "approve"}).json()
    assert finished["status"] == "completed"
    assert finished["final_text"].startswith(GREETING)
    assert len(finished["steps"]) == 5

    assert client.post("/agent/runs/run-12345678/resume", json={"action": "approve"}).status_code == 409


def test_routes_report_failures_with_llm_metadata(http):
    client, use_graph = http
    use_graph(SKILLS, FakeAPIError(400, "bad request"))

    failed = client.post("/agent/runs", json=BODY).json()
    assert failed["status"] == "failed"
    assert failed["steps"][-1]["node"] == "plan"
    assert failed["steps"][-1]["runs"][0]["status"] == "FAILED"
    assert failed["error"]["type"] == "FakeAPIError"


def test_text_that_contradicts_its_claim_list_is_caught():
    # The claim list says 40%, but the paragraph text says 60%.
    sneaky = draft("I cut PostgreSQL p95 latency by 60%.", "Cut PostgreSQL p95 latency by 40%.", [1])
    fixed = draft("I cut PostgreSQL p95 latency by 40%.", "Cut PostgreSQL p95 latency by 40%.", [1])
    graph = make_graph(SKILLS, PLAN, GOOD[0], sneaky, GOOD[2], fixed)
    start(graph)

    trace = graph.get_state(run_config("thread-0001")).values["trace"]
    assert trace[3]["detail"]["p2"]["problems"] == ["paragraph text: number_not_in_evidence: 60%"]
    assert [step["node"] for step in trace][-2:] == ["revise", "verify"]
