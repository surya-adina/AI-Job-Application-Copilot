"""MCP server that exposes the AI service's typed tools over stdio.

    .venv/bin/python mcp_server.py
    npx @modelcontextprotocol/inspector .venv/bin/python mcp_server.py

Tool names, descriptions and input/output JSON schemas come from
tools.REGISTRY, the same registry behind the HTTP /tools routes and the
cover-letter agent, so all three expose identical contracts.

The server only speaks over stdin/stdout to the process that launched it and
opens no network port, so the HTTP service token does not apply. Tools that
need them read OPENAI_API_KEY and DATABASE_URL from ai-service/.env.
"""

import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

import anyio  # noqa: E402
from mcp import types  # noqa: E402
from mcp.server.lowlevel import Server  # noqa: E402
from mcp.server.stdio import stdio_server  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from llm import LLMCallError  # noqa: E402
from tools import REGISTRY, ToolError, invoke  # noqa: E402

SERVER_NAME = "job-application-copilot"
INSTRUCTIONS = (
    "Tools for comparing a resume with a job posting and writing application material that the resume "
    "supports. Typical flow: fetch_job_posting or paste a description, match_skills, search_resume_evidence, "
    "draft_section, then verify_claims on the drafted claims before using them."
)

logger = logging.getLogger(SERVER_NAME)


def tool_definitions() -> list[types.Tool]:
    return [
        types.Tool(
            name=tool.name,
            description=tool.description,
            input_schema=tool.input_model.model_json_schema(),
            output_schema=tool.output_model.model_json_schema(),
        )
        for tool in REGISTRY.values()
    ]


def error_result(message: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=message)], is_error=True)


async def on_list_tools(_context, _params) -> types.ListToolsResult:
    return types.ListToolsResult(tools=tool_definitions())


async def on_call_tool(_context, params: types.CallToolRequestParams) -> types.CallToolResult:
    if params.name not in REGISTRY:
        return error_result(f"Unknown tool: {params.name}")

    try:
        # Tools are synchronous (LLM, database and HTTP calls); run them off the event loop.
        result = await anyio.to_thread.run_sync(invoke, params.name, params.arguments or {})
    except ValidationError as error:
        details = "; ".join(f"{'.'.join(map(str, item['loc'])) or 'arguments'}: {item['msg']}" for item in error.errors())
        return error_result(f"Invalid arguments: {details}")
    except ToolError as error:
        return error_result(f"{error.code}: {error}")
    except LLMCallError as error:
        return error_result(f"Model call failed ({error.error_type})")
    except Exception:
        logger.exception("Tool %s failed", params.name)
        return error_result(f"Tool {params.name} failed unexpectedly")

    output = result.output.model_dump(mode="json")
    usage = {
        "llm_calls": len(result.runs),
        "estimated_cost_usd": round(sum(run.estimated_cost_usd or 0 for run in result.runs), 6),
        "latency_ms": result.latency_ms,
    }
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(output, indent=2))],
        structured_content=output,
        meta={"usage": usage},
    )


def build_server() -> Server:
    return Server(
        SERVER_NAME,
        version="1.0.0",
        instructions=INSTRUCTIONS,
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


async def main() -> None:
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    # stdout carries the protocol, so all logging goes to stderr.
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    anyio.run(main)
