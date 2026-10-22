import pytest
from pydantic import BaseModel

from llm import LLMCallError, call_structured
from llm.config import estimate_cost_usd
from llm.strict_schema import strict_json_schema
from tests.fakes import FakeAPIError, FakeClient, RateLimitError, ok, refusal, truncated


class Inner(BaseModel):
    name: str
    note: str | None = None


class Outer(BaseModel):
    score: int
    items: list[Inner]
    tags: list[str] = []


def call(client, **overrides):
    kwargs = dict(
        endpoint="/test",
        prompt_version="test_v1",
        system="system",
        user="user",
        schema=Outer,
        client=client,
        model="gpt-4o-mini",
        max_retries=2,
        sleep=lambda _seconds: None,
    )
    kwargs.update(overrides)
    return call_structured(**kwargs)


VALID = {"score": 80, "items": [{"name": "Python", "note": None}], "tags": []}


def _objects(node):
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node:
            yield node
        for value in node.values():
            yield from _objects(value)
    elif isinstance(node, list):
        for value in node:
            yield from _objects(value)


def test_strict_schema_requires_every_property_and_forbids_extras():
    schema = strict_json_schema(Outer)
    objects = list(_objects(schema))

    assert len(objects) == 2  # Outer and Inner (in $defs)
    for obj in objects:
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])
    assert "default" not in str(schema)


def test_strict_schema_keeps_a_field_named_default():
    class Settings(BaseModel):
        default: str
        mode: str = "fast"

    schema = strict_json_schema(Settings)

    assert set(schema["properties"]) == {"default", "mode"}
    assert "default" not in schema["properties"]["mode"]
    assert set(schema["required"]) == {"default", "mode"}


def test_request_uses_strict_json_schema_format():
    client = FakeClient(ok(VALID))
    call(client)

    text_format = client.calls[0]["text"]["format"]
    assert text_format["type"] == "json_schema"
    assert text_format["strict"] is True
    assert text_format["name"] == "Outer"


def test_success_reports_tokens_cost_and_zero_retries():
    result = call(FakeClient(ok(VALID)))

    assert result.parsed.items[0].name == "Python"
    assert result.metadata.status == "SUCCESS"
    assert result.metadata.retries == 0
    assert result.metadata.tokens_in == 100
    assert result.metadata.tokens_out == 50
    assert result.metadata.estimated_cost_usd == pytest.approx(100 * 0.15e-6 + 50 * 0.60e-6)


def test_retries_transient_errors_and_counts_them():
    client = FakeClient(RateLimitError("slow down"), FakeAPIError(503), ok(VALID))
    result = call(client)

    assert result.metadata.retries == 2
    assert result.metadata.status == "SUCCESS"
    assert len(client.calls) == 3


def test_gives_up_after_max_retries_with_failed_metadata():
    client = FakeClient(FakeAPIError(503), FakeAPIError(503), FakeAPIError(503))

    with pytest.raises(LLMCallError) as caught:
        call(client)

    assert caught.value.metadata.status == "FAILED"
    assert caught.value.metadata.retries == 2
    assert caught.value.metadata.error_type == "FakeAPIError"


def test_client_errors_are_not_retried():
    client = FakeClient(FakeAPIError(400, "bad request"))

    with pytest.raises(LLMCallError) as caught:
        call(client)

    assert len(client.calls) == 1
    assert caught.value.metadata.retries == 0


def test_client_setup_failure_returns_failed_metadata(monkeypatch):
    def missing_key():
        raise RuntimeError("Missing credentials")

    monkeypatch.setattr("llm.client.get_default_client", missing_key)

    with pytest.raises(LLMCallError) as caught:
        call(None)

    assert caught.value.error_type == "CLIENT_SETUP_ERROR"
    assert caught.value.metadata.status == "FAILED"
    assert caught.value.metadata.retries == 0


def test_invalid_output_is_retried_once_then_fails():
    client = FakeClient(ok({"score": "high"}), ok({"wrong": True}))

    with pytest.raises(LLMCallError) as caught:
        call(client)

    assert caught.value.error_type == "STRUCTURED_OUTPUT_ERROR"
    assert caught.value.metadata.retries == 1
    # Both attempts were billed, so both count toward tokens.
    assert caught.value.metadata.tokens_in == 200


def test_invalid_output_then_valid_succeeds():
    result = call(FakeClient(ok("not json"), ok(VALID)))
    assert result.metadata.retries == 1
    assert result.metadata.status == "SUCCESS"


def test_refusal_is_reported_and_not_retried():
    client = FakeClient(refusal())

    with pytest.raises(LLMCallError) as caught:
        call(client)

    assert caught.value.error_type == "MODEL_REFUSAL"
    assert len(client.calls) == 1


def test_truncated_output_is_reported_and_not_retried():
    client = FakeClient(truncated())

    with pytest.raises(LLMCallError) as caught:
        call(client)

    assert caught.value.error_type == "OUTPUT_TRUNCATED"
    assert len(client.calls) == 1


def test_cost_unknown_model_is_none_and_snapshots_match_base():
    assert estimate_cost_usd("some-new-model", 1000, 1000) is None
    assert estimate_cost_usd("gpt-4o-mini-2024-07-18", 1_000_000, 0) == pytest.approx(0.15)
    # "gpt-4.1-mini" must not be priced as "gpt-4.1".
    assert estimate_cost_usd("gpt-4.1-mini", 1_000_000, 0) == pytest.approx(0.40)
