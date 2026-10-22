"""Typed tool registry shared by the HTTP routes, the agent and the MCP server.

Each tool declares Pydantic input and output models; `invoke` validates the
arguments, runs the handler and returns the output together with metadata for
every LLM call the tool made, so callers can log them as AiRun rows.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel

from llm import RunMetadata


class ToolError(Exception):
    """An expected failure the caller can act on (bad URL, unknown evidence id, ...)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class ToolContext:
    """Dependencies a tool may need; tests replace them with fakes."""

    llm_kwargs: dict[str, Any] = field(default_factory=dict)
    connection_factory: Callable[[], Any] | None = None
    fetcher: Callable[[str], Any] | None = None


@dataclass
class ToolResult:
    tool: str
    output: BaseModel
    runs: list[RunMetadata]
    latency_ms: int

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "output": self.output.model_dump(),
            "runs": [run.model_dump() for run in self.runs],
            "latency_ms": self.latency_ms,
        }


Handler = Callable[[BaseModel, ToolContext], tuple[BaseModel, list[RunMetadata]]]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Handler

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
            "output_schema": self.output_model.model_json_schema(),
        }


REGISTRY: dict[str, Tool] = {}


def register(tool: Tool) -> Tool:
    if tool.name in REGISTRY:
        raise ValueError(f"Tool {tool.name} is already registered")
    REGISTRY[tool.name] = tool
    return tool


def get_tool(name: str) -> Tool:
    if name not in REGISTRY:
        raise KeyError(name)
    return REGISTRY[name]


def invoke(name: str, arguments: dict, context: ToolContext | None = None) -> ToolResult:
    """Validate arguments, run the tool and time it. Raises KeyError for an
    unknown tool, pydantic.ValidationError for bad arguments, ToolError for
    expected failures and llm.LLMCallError when a model call fails."""
    tool = get_tool(name)
    parsed = tool.input_model.model_validate(arguments)
    started = time.perf_counter()
    output, runs = tool.handler(parsed, context or ToolContext())
    return ToolResult(
        tool=name,
        output=tool.output_model.model_validate(output.model_dump()),
        runs=runs,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
