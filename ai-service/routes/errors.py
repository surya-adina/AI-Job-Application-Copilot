from fastapi import HTTPException

from llm import LLMCallError


def http_error_from_llm(error: LLMCallError, message: str) -> HTTPException:
    """Keep the existing error contract: detail.metadata is what the backend logs to AiRun."""
    status_code = 502 if error.error_type in {"STRUCTURED_OUTPUT_ERROR", "OUTPUT_TRUNCATED", "MODEL_REFUSAL"} else 503
    return HTTPException(
        status_code=status_code,
        detail={
            "message": message,
            "error": str(error),
            "metadata": error.metadata.model_dump(),
        },
    )
