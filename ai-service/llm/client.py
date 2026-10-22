"""One wrapper for every OpenAI call in the AI service.

What it guarantees:
  * Structured calls use strict json_schema Structured Outputs, then validate
    the result with the same Pydantic model.
  * Transient failures (rate limits, timeouts, connection errors, 5xx) are
    retried with exponential backoff and jitter. The OpenAI SDK's own silent
    retries are disabled so `retries` in the metadata is the real count.
  * A response that fails validation is retried once; refusals and truncated
    output are not retried because a second attempt would fail the same way.
  * Tokens and cost are summed across every attempt, since failed attempts
    are billed too.

The OpenAI SDK is only imported when the default client is first needed, so
tests can pass a fake client and run without the SDK installed.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Literal, TypeVar

from pydantic import BaseModel, ValidationError

from llm import config
from llm.strict_schema import response_format

T = TypeVar("T", bound=BaseModel)

RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
RETRYABLE_ERROR_NAMES = {
    "APIConnectionError",
    "APITimeoutError",
    "RateLimitError",
    "InternalServerError",
    "Timeout",
    "ConnectError",
    "ReadTimeout",
}
MAX_SCHEMA_RETRIES = 1


class RunMetadata(BaseModel):
    endpoint: str
    model: str
    prompt_version: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    total_tokens: int
    retries: int
    status: Literal["SUCCESS", "FAILED"]
    error_type: str | None = None
    estimated_cost_usd: float | None = None


class LLMCallError(Exception):
    def __init__(self, message: str, error_type: str, metadata: RunMetadata):
        super().__init__(message)
        self.error_type = error_type
        self.metadata = metadata


@dataclass
class StructuredResult(Generic[T]):
    parsed: T
    metadata: RunMetadata


@dataclass
class TextResult:
    text: str
    metadata: RunMetadata


@dataclass
class _Usage:
    tokens_in: int = 0
    tokens_out: int = 0
    total: int = 0

    def add(self, response: Any) -> None:
        usage = getattr(response, "usage", None)
        if not usage:
            return
        tokens_in = getattr(usage, "input_tokens", 0) or 0
        tokens_out = getattr(usage, "output_tokens", 0) or 0
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.total += getattr(usage, "total_tokens", None) or tokens_in + tokens_out


class _NonRetryable(Exception):
    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type


_default_client = None


def get_default_client():
    global _default_client
    if _default_client is None:
        from openai import OpenAI  # imported lazily on purpose

        _default_client = OpenAI(max_retries=0, timeout=config.get_timeout_seconds())
    return _default_client


def is_retryable(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    if status_code in RETRYABLE_STATUS_CODES:
        return True
    return type(error).__name__ in RETRYABLE_ERROR_NAMES


def error_type_for(error: Exception) -> str:
    if isinstance(error, _NonRetryable):
        return error.error_type
    if isinstance(error, (ValidationError, json.JSONDecodeError)):
        return "STRUCTURED_OUTPUT_ERROR"
    return type(error).__name__


def backoff_seconds(attempt: int, base: float = 0.5, cap: float = 8.0) -> float:
    return min(cap, base * (2**attempt)) * (0.5 + random.random() / 2)


def _find_refusal(response: Any) -> str | None:
    for item in getattr(response, "output", None) or []:
        for content in getattr(item, "content", None) or []:
            if getattr(content, "type", None) == "refusal":
                return getattr(content, "refusal", None) or "Model refused the request"
    return None


def _check_complete(response: Any) -> None:
    if getattr(response, "status", None) == "incomplete":
        details = getattr(response, "incomplete_details", None)
        reason = getattr(details, "reason", None) or "unknown"
        raise _NonRetryable("OUTPUT_TRUNCATED", f"Response incomplete: {reason}")

    refusal = _find_refusal(response)
    if refusal:
        raise _NonRetryable("MODEL_REFUSAL", refusal)


def _run(
    *,
    endpoint: str,
    prompt_version: str,
    request: dict[str, Any],
    parse: Callable[[Any], Any],
    client: Any = None,
    model: str | None = None,
    max_retries: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
):
    model = model or config.get_model()
    max_retries = config.get_max_retries() if max_retries is None else max_retries

    usage = _Usage()
    retries = 0
    schema_retries = 0
    started_at = time.perf_counter()

    def metadata(status: str, error_type: str | None = None) -> RunMetadata:
        return RunMetadata(
            endpoint=endpoint,
            model=model,
            prompt_version=prompt_version,
            latency_ms=int((time.perf_counter() - started_at) * 1000),
            tokens_in=usage.tokens_in,
            tokens_out=usage.tokens_out,
            total_tokens=usage.total,
            retries=retries,
            status=status,
            error_type=error_type,
            estimated_cost_usd=config.estimate_cost_usd(model, usage.tokens_in, usage.tokens_out),
        )

    # Setup failures (e.g. a missing API key) must still produce FAILED metadata
    # instead of escaping as an unhandled 500.
    try:
        client = client or get_default_client()
    except Exception as error:
        raise LLMCallError(str(error), "CLIENT_SETUP_ERROR", metadata("FAILED", "CLIENT_SETUP_ERROR")) from error

    while True:
        try:
            response = client.responses.create(model=model, **request)
            usage.add(response)
            _check_complete(response)
            return parse(response), metadata("SUCCESS")

        except (ValidationError, json.JSONDecodeError) as error:
            if schema_retries < MAX_SCHEMA_RETRIES and retries < max_retries:
                schema_retries += 1
                retries += 1
                continue
            raise LLMCallError(str(error), "STRUCTURED_OUTPUT_ERROR", metadata("FAILED", "STRUCTURED_OUTPUT_ERROR")) from error

        except _NonRetryable as error:
            raise LLMCallError(str(error), error.error_type, metadata("FAILED", error.error_type)) from error

        except Exception as error:  # SDK and network errors
            if is_retryable(error) and retries < max_retries:
                sleep(backoff_seconds(retries))
                retries += 1
                continue
            error_type = error_type_for(error)
            raise LLMCallError(str(error), error_type, metadata("FAILED", error_type)) from error


def call_structured(
    *,
    endpoint: str,
    prompt_version: str,
    system: str,
    user: str,
    schema: type[T],
    temperature: float = 0.2,
    max_output_tokens: int = 900,
    **kwargs: Any,
) -> StructuredResult[T]:
    request = {
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "text": {"format": response_format(schema)},
    }

    parsed, metadata = _run(
        endpoint=endpoint,
        prompt_version=prompt_version,
        request=request,
        parse=lambda response: schema.model_validate_json(response.output_text),
        **kwargs,
    )
    return StructuredResult(parsed=parsed, metadata=metadata)


def call_text(
    *,
    endpoint: str,
    prompt_version: str,
    system: str,
    user: str,
    temperature: float = 0.2,
    max_output_tokens: int = 900,
    **kwargs: Any,
) -> TextResult:
    request = {
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }

    text, metadata = _run(
        endpoint=endpoint,
        prompt_version=prompt_version,
        request=request,
        parse=lambda response: response.output_text,
        **kwargs,
    )
    return TextResult(text=text, metadata=metadata)
