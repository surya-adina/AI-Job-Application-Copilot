import json
import os
import time
from typing import Literal
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

app = FastAPI(title="AI Job Application Copilot - AI Service")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
PROMPT_VERSION = "analysis-v1"


class AnalyzeRequest(BaseModel):
    resume_text: str = Field(..., min_length=50)
    job_description: str = Field(..., min_length=50)


class AnalysisPayload(BaseModel):
    score: int = Field(..., ge=0, le=100)
    matched_skills: list[str]
    missing_skills: list[str]
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]


class AiRunMetadata(BaseModel):
    endpoint: str
    model: str
    prompt_version: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    total_tokens: int
    status: Literal["SUCCESS", "FAILED"]
    error_type: str | None = None

class AnalyzeResponse(BaseModel):
    analysis: AnalysisPayload
    metadata: AiRunMetadata


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
    started_at = time.perf_counter()

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI job-fit analysis engine. "
                        "Analyze a resume against a job description. "
                        "Return ONLY valid JSON matching the requested schema. "
                        "Do not invent experience not present in the resume."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "resume_text": payload.resume_text,
                            "job_description": payload.job_description,
                            "output_schema": {
                                "score": "integer from 0 to 100",
                                "matched_skills": "array of strings",
                                "missing_skills": "array of strings",
                                "strengths": "array of strings",
                                "weaknesses": "array of strings",
                                "recommendations": "array of strings",
                            },
                        }
                    ),
                },
            ],
            text={
                "format": {
                    "type": "json_object",
                }
            },
        )

        latency_ms = int((time.perf_counter() - started_at) * 1000)

        raw_text = response.output_text
        parsed = json.loads(raw_text)
        analysis = AnalysisPayload(**parsed)

        usage = response.usage
        tokens_in = usage.input_tokens if usage else 0
        tokens_out = usage.output_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else tokens_in + tokens_out

        metadata = AiRunMetadata(
            endpoint="/analyze",
            model=OPENAI_MODEL,
            prompt_version=PROMPT_VERSION,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            total_tokens=total_tokens,
            status="SUCCESS",
        )

        return AnalyzeResponse(analysis=analysis, metadata=metadata)

    except (json.JSONDecodeError, ValidationError) as error:
        latency_ms = int((time.perf_counter() - started_at) * 1000)

        metadata = AiRunMetadata(
            endpoint="/analyze",
            model=OPENAI_MODEL,
            prompt_version=PROMPT_VERSION,
            latency_ms=latency_ms,
            tokens_in=0,
            tokens_out=0,
            total_tokens=0,
            status="FAILED",
            error_type="STRUCTURED_OUTPUT_ERROR",
        )

        raise HTTPException(
            status_code=502,
            detail={
                "message": "Model returned invalid structured output",
                "error": str(error),
                "metadata": metadata.model_dump(),
            },
        )

    except Exception as error:
        latency_ms = int((time.perf_counter() - started_at) * 1000)

        metadata = AiRunMetadata(
            endpoint="/analyze",
            model=OPENAI_MODEL,
            prompt_version=PROMPT_VERSION,
            latency_ms=latency_ms,
            tokens_in=0,
            tokens_out=0,
            total_tokens=0,
            status="FAILED",
            error_type=type(error).__name__,
        )

        raise HTTPException(
            status_code=500,
            detail={
                "message": "AI analysis failed",
                "error": str(error),
                "metadata": metadata.model_dump(),
            },
        )