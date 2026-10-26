import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import main
from agent.graph import AgentConfig, run_config
from agent.tailoring import build_tailoring_graph
from routes import agent as agent_routes
from skills.resume_units import apply_rewrites, resume_units
from tests.conftest import TEST_SERVICE_TOKEN
from tests.fakes import FakeClient, ok
from tools import ToolContext

FASTAPI = "Built FastAPI microservices handling 2M requests/day for shipment tracking teams."
CHATBOT = "Designed a RAG-based chatbot using Mistral LLM and FAISS for course questions."
RESUME = f"""Jordan Lee
Experience
• {FASTAPI}
• {CHATBOT}
Skills
Python, FastAPI, PostgreSQL, Docker
"""
JOB = "AI Engineer. Build LLM applications and high-volume Python APIs. Kafka is a plus."
LLM_KWARGS = dict(model="gpt-4o-mini", max_retries=0, sleep=lambda _s: None)

SKILLS = ok(
    {
        "skills": [
            {"skill": "LLM", "priority": "required", "in_resume": True, "resume_evidence": "Mistral LLM"},
            {"skill": "Kafka", "priority": "preferred", "in_resume": False, "resume_evidence": None},
        ]
    }
)
PLAN = ok({"selections": [{"unit_id": 0, "goal": "Show API scale."}, {"unit_id": 1, "goal": "Frame as an LLM application."}, {"unit_id": 99, "goal": "Invalid id."}]})
GOOD_0 = ok({"text": "Scaled FastAPI microservices to 2M requests/day for shipment tracking teams."})
GOOD_1 = ok({"text": "Built an LLM application: a RAG chatbot with Mistral LLM and FAISS for course questions."})
BAD_1 = ok({"text": "Built an LLM application with Mistral LLM, FAISS and Kafka for course questions."})


# ---------- resume units ----------


def test_wrapped_bullets_are_joined_and_headings_kept_apart():
    text = (
        "• Engineered a pattern mining pipeline on 9,787 real Amazon weblog sessions (Rack ID,\n"
        "DataNode ID, Block ID); converted access sequences into weighted directed graphs, pruned nodes\n"
        "and edges, extracting 129,830 access patterns.\n"
        "• Tech: Python, Mistral LLM, FAISS, Streamlit, RAG, LangChain, Docker, GitHub Actions\n"
        "Stock Market Sentiment Analyzer | GitHub\n"
        "• Engineered a real-time stock intelligence system tracking 10 major tech stocks with FinBERT.\n"
    )
    units = resume_units(text)

    assert [unit.text.split()[0] for unit in units] == ["Engineered", "Tech:", "Stock", "Engineered"]
    assert units[0].text.endswith("extracting 129,830 access patterns.")
    assert all(" ".join(text[unit.start : unit.end].split()) == unit.text for unit in units)


def test_apply_rewrites_keeps_markers_and_other_lines():
    units = resume_units(RESUME)
    result = apply_rewrites(RESUME, units, {0: "Scaled FastAPI services to 2M requests/day."})

    assert "• Scaled FastAPI services to 2M requests/day.\n" in result
    assert f"• {CHATBOT}" in result
    assert result.startswith("Jordan Lee\nExperience\n")


# ---------- agent ----------


def make_graph(*script):
    context = ToolContext(llm_kwargs=dict(client=FakeClient(*script), **LLM_KWARGS))
    return build_tailoring_graph(AgentConfig(tool_context=context, parallelism=1), checkpointer=InMemorySaver())


def start(graph, thread_id="tailor-0001"):
    initial = {"resume_id": "r1", "resume_text": RESUME, "job_description": JOB, "instructions": "", "trace": [], "steps": 0}
    return graph.invoke(initial, run_config(thread_id))


def nodes(graph, thread_id="tailor-0001"):
    return [step["node"] for step in graph.get_state(run_config(thread_id)).values["trace"]]


def test_review_shows_original_and_rewrite_for_valid_units_only():
    graph = make_graph(SKILLS, PLAN, GOOD_0, GOOD_1)
    review = start(graph)["__interrupt__"][0].value

    assert [item["unit_id"] for item in review["items"]] == [0, 1]  # id 99 was dropped
    assert review["items"][0]["original"] == FASTAPI
    assert review["items"][0]["rewritten"].startswith("Scaled FastAPI")
    assert all(item["passed"] for item in review["items"])
    assert review["missing_skills"] == ["Kafka"]
    assert nodes(graph) == ["plan", "rewrite", "verify"]


def test_save_applies_accepted_and_edited_units_only():
    graph = make_graph(SKILLS, PLAN, GOOD_0, GOOD_1)
    start(graph)
    decision = {
        "action": "save",
        "title": "Tailored",
        "items": [{"unit_id": 0, "choice": "accept", "text": None}, {"unit_id": 1, "choice": "edit", "text": "My own chatbot line."}],
    }
    graph.invoke(Command(resume=decision), run_config("tailor-0001"))
    state = graph.get_state(run_config("tailor-0001")).values

    assert state["status"] == "completed"
    assert "• Scaled FastAPI microservices to 2M requests/day" in state["final_text"]
    assert "• My own chatbot line.\n" in state["final_text"]
    assert state["trace"][-1]["detail"] == {"action": "save", "accepted": 1, "edited": 1, "kept_original": 0}


def test_keep_original_and_discard():
    graph = make_graph(SKILLS, PLAN, GOOD_0, GOOD_1)
    start(graph)
    graph.invoke(Command(resume={"action": "save", "title": "T", "items": [{"unit_id": 0, "choice": "keep", "text": None}]}), run_config("tailor-0001"))
    assert graph.get_state(run_config("tailor-0001")).values["final_text"] == RESUME

    graph = make_graph(SKILLS, PLAN, GOOD_0, GOOD_1)
    start(graph, "tailor-0002")
    graph.invoke(Command(resume={"action": "discard", "items": []}), run_config("tailor-0002"))
    state = graph.get_state(run_config("tailor-0002")).values
    assert (state["status"], state["final_text"]) == ("rejected", None)


def test_rewrite_that_adds_a_skill_is_revised():
    graph = make_graph(SKILLS, PLAN, GOOD_0, BAD_1, GOOD_1)
    review = start(graph)["__interrupt__"][0].value

    assert nodes(graph) == ["plan", "rewrite", "verify", "revise", "verify"]
    trace = graph.get_state(run_config("tailor-0001")).values["trace"]
    assert trace[2]["detail"]["1"]["problems"] == ["skill_not_in_evidence: Kafka"]
    assert all(item["passed"] for item in review["items"])


def test_nothing_to_tailor_goes_straight_to_review():
    graph = make_graph(SKILLS, ok({"selections": []}))
    review = start(graph)["__interrupt__"][0].value

    assert review["items"] == []
    assert nodes(graph) == ["plan"]


# ---------- routes ----------


@pytest.fixture
def http(monkeypatch):
    holder = {}
    monkeypatch.setattr(agent_routes, "get_graph", lambda task="cover_letter": holder["graph"])
    client = TestClient(main.app, headers={"X-Service-Token": TEST_SERVICE_TOKEN})
    return client, holder


def test_routes_validate_tailoring_decisions(http):
    client, holder = http
    holder["graph"] = make_graph(SKILLS, PLAN, GOOD_0, GOOD_1)
    body = {"thread_id": "tailor-route-1", "task": "resume_tailoring", "resume_id": "r1", "resume_text": RESUME, "job_description": JOB}

    started = client.post("/agent/runs", json=body).json()
    assert started["status"] == "awaiting_review"
    assert len(started["review"]["items"]) == 2

    url = "/agent/runs/tailor-route-1/resume"
    assert client.post(url, json={"task": "resume_tailoring", "action": "approve"}).status_code == 422
    assert client.post(url, json={"task": "resume_tailoring", "action": "save", "items": []}).status_code == 422

    saved = client.post(url, json={"task": "resume_tailoring", "action": "save", "title": "Mine", "items": [{"unit_id": 0, "choice": "accept"}]}).json()
    assert saved["status"] == "completed"
    assert "Scaled FastAPI" in saved["final_text"]


def test_added_wording_is_flagged_but_rephrasing_is_not():
    from skills.claim_verifier import rewrite_problems

    original = "Implemented FastAPI endpoints to ingest 100+ financial headlines into PostgreSQL."
    assert rewrite_problems("Built FastAPI endpoints ingesting 100+ financial headlines into PostgreSQL.", original) == []
    assert rewrite_problems(
        "Built FastAPI endpoints ingesting 100+ financial headlines into PostgreSQL to support internal investor dashboards.",
        original,
    ) == ["adds_wording: support, internal, investor, dashboards"]


def test_rewrite_with_invented_purpose_is_revised():
    padded = ok({"text": "Scaled FastAPI microservices to 2M requests/day for shipment tracking teams, enabling investor analytics dashboards."})
    graph = make_graph(SKILLS, PLAN, padded, GOOD_1, GOOD_0)
    review = start(graph)["__interrupt__"][0].value

    trace = graph.get_state(run_config("tailor-0001")).values["trace"]
    assert trace[2]["detail"]["0"]["problems"] == ["adds_wording: investor, analytics, dashboards"]
    assert nodes(graph) == ["plan", "rewrite", "verify", "revise", "verify"]
    assert all(item["passed"] for item in review["items"])
