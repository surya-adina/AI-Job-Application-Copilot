import logging
import re
from typing import Literal

from fastapi import APIRouter, HTTPException
from langgraph.types import Command
from pydantic import BaseModel, Field, model_validator

from agent.checkpointer import CheckpointerUnavailable, get_checkpointer
from agent.graph import build_graph, run_config
from llm import LLMCallError
from tools import ToolError

router = APIRouter(prefix="/agent")
logger = logging.getLogger(__name__)

THREAD_ID_PATTERN = r"^[A-Za-z0-9-]{8,64}$"


class StartRunRequest(BaseModel):
    thread_id: str = Field(..., pattern=THREAD_ID_PATTERN, description="Caller-chosen id, e.g. the AgentRun id.")
    task: Literal["cover_letter"] = "cover_letter"
    resume_id: str = Field(..., min_length=1, max_length=64)
    resume_text: str = Field(..., min_length=50)
    job_description: str = Field(..., min_length=50)
    instructions: str = Field(default="", max_length=1000)


class Decision(BaseModel):
    action: Literal["approve", "edit", "reject"]
    text: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def edit_needs_text(self):
        if self.action == "edit" and not (self.text or "").strip():
            raise ValueError("Edited text is required for an edit decision")
        return self


class RunResponse(BaseModel):
    thread_id: str
    status: Literal["awaiting_review", "completed", "rejected", "failed"]
    steps: list[dict]
    review: dict | None = None
    final_text: str | None = None
    error: dict | None = None


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        try:
            _graph = build_graph(checkpointer=get_checkpointer())
        except CheckpointerUnavailable as error:
            raise HTTPException(status_code=503, detail={"message": str(error)}) from error
    return _graph


def describe(graph, thread_id: str, result: dict | None = None, error: Exception | None = None) -> RunResponse:
    snapshot = graph.get_state(run_config(thread_id))
    values = snapshot.values or {}
    steps = list(values.get("trace", []))

    if error is not None:
        failed_step = {
            "node": snapshot.next[0] if snapshot.next else "unknown",
            "status": "failed",
            "latency_ms": 0,
            "runs": [error.metadata.model_dump()] if isinstance(error, LLMCallError) else [],
            "detail": None,
            "error": {"type": getattr(error, "error_type", None) or getattr(error, "code", None) or type(error).__name__, "message": str(error)[:500]},
        }
        return RunResponse(thread_id=thread_id, status="failed", steps=[*steps, failed_step], error=failed_step["error"])

    interrupts = (result or {}).get("__interrupt__") or [task_interrupt for task in snapshot.tasks for task_interrupt in task.interrupts]
    if interrupts:
        return RunResponse(thread_id=thread_id, status="awaiting_review", steps=steps, review=interrupts[0].value)

    return RunResponse(
        thread_id=thread_id, status=values.get("status", "failed"), steps=steps, final_text=values.get("final_text")
    )


def run_graph(graph, thread_id: str, graph_input) -> RunResponse:
    try:
        result = graph.invoke(graph_input, run_config(thread_id))
    except (LLMCallError, ToolError) as error:
        logger.warning("Agent run %s failed: %s", thread_id, error)
        return describe(graph, thread_id, error=error)
    except Exception as error:
        logger.exception("Agent run %s failed", thread_id)
        return describe(graph, thread_id, error=error)
    return describe(graph, thread_id, result=result)


@router.post("/runs", response_model=RunResponse)
def start_run(request: StartRunRequest):
    graph = get_graph()
    if graph.get_state(run_config(request.thread_id)).values:
        raise HTTPException(status_code=409, detail={"message": f"Run {request.thread_id} already exists"})

    initial = request.model_dump(exclude={"thread_id"}) | {"trace": [], "steps": 0}
    return run_graph(graph, request.thread_id, initial)


@router.post("/runs/{thread_id}/resume", response_model=RunResponse)
def resume_run(thread_id: str, decision: Decision):
    if not re.fullmatch(THREAD_ID_PATTERN, thread_id):
        raise HTTPException(status_code=422, detail={"message": "Invalid thread id"})

    graph = get_graph()
    snapshot = graph.get_state(run_config(thread_id))
    if not any(task.interrupts for task in snapshot.tasks):
        raise HTTPException(status_code=409, detail={"message": f"Run {thread_id} is not waiting for review"})

    return run_graph(graph, thread_id, Command(resume=decision.model_dump()))


@router.get("/runs/{thread_id}", response_model=RunResponse)
def get_run(thread_id: str):
    if not re.fullmatch(THREAD_ID_PATTERN, thread_id):
        raise HTTPException(status_code=422, detail={"message": "Invalid thread id"})

    graph = get_graph()
    if not graph.get_state(run_config(thread_id)).values:
        raise HTTPException(status_code=404, detail={"message": f"Run {thread_id} not found"})
    return describe(graph, thread_id)
