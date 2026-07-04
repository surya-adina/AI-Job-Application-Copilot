import json
import os
import time
from typing import Literal
from fastapi import APIRouter, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError
from prompt_loader import load_prompt

router = APIRouter()

_review_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class ResumeReviewRequest(BaseModel):
    resume_text: str = Field(..., min_length=50)
    job_description: str = Field(..., min_length=50)
    analysis: dict
    evidence: dict
    prompt_version: str = "resume_review_v1"


class ResumeSuggestion(BaseModel):
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    title: str
    target_section: str
    why: str
    evidence: list[str]
    action: str

class ResumeReviewPayload(BaseModel):
    summary: str
    suggestions: list[ResumeSuggestion]
    growth_areas: list[str]
    warnings: list[str]

class ReviewMetadata(BaseModel):
    endpoint: str
    model: str
    prompt_version: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    total_tokens: int
    status: Literal["SUCCESS", "FAILED"]
    error_type: str | None = None


class ResumeReviewResponse(BaseModel):
    review: ResumeReviewPayload
    metadata: ReviewMetadata


@router.post("/resume-review", response_model=ResumeReviewResponse)
def review_resume(payload: ResumeReviewRequest):
    started_at = time.perf_counter()

    try:
        system_prompt = load_prompt(payload.prompt_version)

        response = _review_client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "resume_text": payload.resume_text,
                            "job_description": payload.job_description,
                            "analysis": payload.analysis,
                            "evidence": payload.evidence,
                            "output_schema": {
                                "summary": "short string",
                                "suggestions": [
                                    {
                                        "priority": "HIGH | MEDIUM | LOW",
                                        "title": "string",
                                        "why": "string",
                                        "evidence": [
                                            "string"
                                        ],
                                        "action": "string"
                                    }
                                ],
                                "growth_areas": "array of strings",
                                "warnings": "array of strings"
                            },
                        }
                    ),
                },
            ],
            text={"format": {"type": "json_object"}},
        )

        latency_ms = int((time.perf_counter() - started_at) * 1000)

        parsed = json.loads(response.output_text)
        review = ResumeReviewPayload(**parsed)

        usage = response.usage
        tokens_in = usage.input_tokens if usage else 0
        tokens_out = usage.output_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else tokens_in + tokens_out

        metadata = ReviewMetadata(
            endpoint="/resume-review",
            model=OPENAI_MODEL,
            prompt_version=payload.prompt_version,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            total_tokens=total_tokens,
            status="SUCCESS",
        )

        return ResumeReviewResponse(review=review, metadata=metadata)

    except (json.JSONDecodeError, ValidationError) as error:
        latency_ms = int((time.perf_counter() - started_at) * 1000)

        raise HTTPException(
            status_code=502,
            detail={
                "message": "Model returned invalid resume review output",
                "error": str(error),
                "metadata": {
                    "endpoint": "/resume-review",
                    "model": OPENAI_MODEL,
                    "prompt_version": payload.prompt_version,
                    "latency_ms": latency_ms,
                    "status": "FAILED",
                    "error_type": "STRUCTURED_OUTPUT_ERROR",
                },
            },
        )

    except Exception as error:
        latency_ms = int((time.perf_counter() - started_at) * 1000)

        raise HTTPException(
            status_code=500,
            detail={
                "message": "Resume review failed",
                "error": str(error),
                "metadata": {
                    "endpoint": "/resume-review",
                    "model": OPENAI_MODEL,
                    "prompt_version": payload.prompt_version,
                    "latency_ms": latency_ms,
                    "status": "FAILED",
                    "error_type": type(error).__name__,
                },
            },
        )