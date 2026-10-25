import os
import sys
from pathlib import Path

import anyio
from mcp.client.client import Client
from mcp.client.stdio import StdioServerParameters

from mcp_server import build_server
from tools import REGISTRY

SERVICE_DIR = Path(__file__).resolve().parents[1]
RESUME = "Built FastAPI microservices handling 2M requests/day for shipment tracking. No experience with Kubernetes."
CLAIMS = {
    "resume_text": RESUME,
    "claims": [
        {"text": "Built FastAPI services handling 2 million requests a day.", "evidence": ["Built FastAPI microservices handling 2M requests/day"]},
        {"text": "Ran Kubernetes clusters.", "evidence": ["Kubernetes"]},
    ],
}


def run(scenario):
    async def main():
        async with Client(build_server()) as client:
            return await scenario(client)

    return anyio.run(main)


def test_lists_every_registry_tool_with_its_schemas():
    tools = run(lambda client: client.list_tools()).tools

    assert [tool.name for tool in tools] == list(REGISTRY)
    for tool in tools:
        registry_tool = REGISTRY[tool.name]
        assert tool.description == registry_tool.description
        assert tool.input_schema == registry_tool.input_model.model_json_schema()
        assert tool.output_schema == registry_tool.output_model.model_json_schema()


def test_call_returns_structured_output_and_usage():
    result = run(lambda client: client.call_tool("verify_claims", CLAIMS))

    assert not result.is_error
    assert [verdict["supported"] for verdict in result.structured_content["verdicts"]] == [True, False]
    assert result.meta["usage"]["llm_calls"] == 0


def test_errors_are_reported_as_tool_errors():
    async def scenario(client):
        return (
            await client.call_tool("fetch_job_posting", {"url": "http://127.0.0.1/"}),
            await client.call_tool("verify_claims", {"claims": []}),
            await client.call_tool("does_not_exist", {}),
        )

    blocked, invalid, unknown = run(scenario)

    assert blocked.is_error and blocked.content[0].text.startswith("blocked_address")
    assert invalid.is_error and "resume_text: Field required" in invalid.content[0].text
    assert unknown.is_error and unknown.content[0].text == "Unknown tool: does_not_exist"


def test_works_over_stdio_subprocess():
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVICE_DIR / "mcp_server.py")],
        cwd=str(SERVICE_DIR),
        env={**os.environ, "OPENAI_API_KEY": ""},
    )

    async def main():
        async with Client(params) as client:
            tools = await client.list_tools()
            result = await client.call_tool("verify_claims", CLAIMS)
            return client.server_info.name, len(tools.tools), result

    name, tool_count, result = anyio.run(main)

    assert (name, tool_count) == ("job-application-copilot", len(REGISTRY))
    assert result.structured_content["supported_count"] == 1
