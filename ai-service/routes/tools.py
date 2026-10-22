from fastapi import APIRouter, Body, HTTPException
from pydantic import ValidationError

from llm import LLMCallError
from routes.errors import http_error_from_llm
from tools import REGISTRY, ToolError, invoke

router = APIRouter(prefix="/tools")


@router.get("")
def list_tools():
    return [tool.schema() for tool in REGISTRY.values()]


@router.post("/{name}")
def call_tool(name: str, arguments: dict = Body(...)):
    if name not in REGISTRY:
        raise HTTPException(status_code=404, detail={"message": f"Unknown tool: {name}"})

    try:
        return invoke(name, arguments).to_dict()
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors(include_url=False, include_input=False)) from error
    except ToolError as error:
        raise HTTPException(status_code=400, detail={"code": error.code, "message": str(error)}) from error
    except LLMCallError as error:
        raise http_error_from_llm(error, f"Tool {name} failed") from error
