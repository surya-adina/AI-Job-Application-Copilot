"""Convert a Pydantic model into a JSON Schema that OpenAI Structured Outputs
accepts with `strict: true`.

Strict mode requires, for every object in the schema:
  * "additionalProperties": false
  * every property listed in "required"
and rejects keywords such as "default". Optional values are expressed as a
union with null, which Pydantic already does for `X | None` fields.

Keep LLM-facing models free of numeric/length constraints (ge, le, max_length);
validate or clamp those in code after parsing instead.
"""

from copy import deepcopy
from typing import Any

from pydantic import BaseModel

_UNSUPPORTED_KEYS = {"default"}


def _make_strict(node: Any, is_property_map: bool = False) -> Any:
    if isinstance(node, dict):
        if is_property_map:
            # Keys here are field names, not schema keywords: keep them all.
            return {key: _make_strict(value) for key, value in node.items()}

        node = {
            key: _make_strict(value, is_property_map=key in {"properties", "$defs"})
            for key, value in node.items()
            if key not in _UNSUPPORTED_KEYS
        }

        if node.get("type") == "object" and "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node["properties"].keys())

        return node

    if isinstance(node, list):
        return [_make_strict(item) for item in node]

    return node


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    return _make_strict(deepcopy(model.model_json_schema()))


def response_format(model: type[BaseModel]) -> dict[str, Any]:
    """The `text.format` payload for client.responses.create."""
    return {
        "type": "json_schema",
        "name": model.__name__,
        "schema": strict_json_schema(model),
        "strict": True,
    }
