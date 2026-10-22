"""Test doubles for the OpenAI Responses client."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeUsage:
    input_tokens: int = 100
    output_tokens: int = 50
    total_tokens: int = 150


@dataclass
class FakeContent:
    type: str
    refusal: str | None = None


@dataclass
class FakeOutputItem:
    content: list[FakeContent]


@dataclass
class FakeResponse:
    output_text: str = ""
    usage: FakeUsage = field(default_factory=FakeUsage)
    status: str = "completed"
    incomplete_details: Any = None
    output: list[FakeOutputItem] = field(default_factory=list)


class FakeAPIError(Exception):
    def __init__(self, status_code: int, message: str = "fake api error"):
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(Exception):
    """Same class name as openai.RateLimitError, which is how the wrapper classifies it."""


def ok(payload: dict | str) -> FakeResponse:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return FakeResponse(output_text=text)


def refusal(message: str = "I can't help with that.") -> FakeResponse:
    return FakeResponse(output=[FakeOutputItem(content=[FakeContent(type="refusal", refusal=message)])])


def truncated() -> FakeResponse:
    class Details:
        reason = "max_output_tokens"

    return FakeResponse(output_text='{"score": 8', status="incomplete", incomplete_details=Details())


class FakeResponses:
    def __init__(self, script: list[FakeResponse | Exception]):
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        if not self.script:
            raise AssertionError("FakeClient received more calls than scripted")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    """Plays back a scripted sequence of responses or exceptions."""

    def __init__(self, *script: FakeResponse | Exception):
        self.responses = FakeResponses(list(script))

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.responses.calls
