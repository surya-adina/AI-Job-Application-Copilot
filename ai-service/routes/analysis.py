import json
import os
import time
from typing import Literal

from fastapi import APIRouter, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from prompt_loader import load_prompt

router = APIRouter()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
PROMPT_VERSION = "analysis_v1"


class AnalyzeRequest(BaseModel):
    resume_text: str = Field(..., min_length=50)
    job_description: str = Field(..., min_length=50)
    prompt_version: str = "analysis_v1"


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
    estimated_cost_usd: float | None = None


class SkillEvidence(BaseModel):
    resume_skills: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    missing_preferred_skills: list[str] = Field(default_factory=list)
    semantic_matches: list[dict] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    analysis: AnalysisPayload
    metadata: AiRunMetadata
    evidence: SkillEvidence


def dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []

    for item in items:
        value = item.strip()

        if not value:
            continue

        key = value.lower()

        if key in seen:
            continue

        seen.add(key)
        result.append(value)

    return result


def clean_analysis(analysis: AnalysisPayload) -> AnalysisPayload:
    return AnalysisPayload(
        score=max(0, min(100, analysis.score)),
        matched_skills=dedupe(analysis.matched_skills)[:10],
        missing_skills=dedupe(analysis.missing_skills)[:8],
        strengths=dedupe(analysis.strengths)[:3],
        weaknesses=dedupe(analysis.weaknesses)[:3],
        recommendations=dedupe(analysis.recommendations)[:3],
    )


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
    started_at = time.perf_counter()
    estimated_cost_usd = None

    try:
        system_prompt = load_prompt(payload.prompt_version)

        response = client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": system_prompt,
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
            temperature=0.2,
            max_output_tokens=850,
            text={
                "format": {
                    "type": "json_object",
                }
            },
        )

        latency_ms = int((time.perf_counter() - started_at) * 1000)

        parsed = json.loads(response.output_text)
        analysis = clean_analysis(AnalysisPayload(**parsed))

        usage = response.usage
        tokens_in = usage.input_tokens if usage else 0
        tokens_out = usage.output_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else tokens_in + tokens_out

        estimated_cost_usd = (
            tokens_in * 0.150 / 1_000_000
            + tokens_out * 0.600 / 1_000_000
        )

        metadata = AiRunMetadata(
            endpoint="/analyze",
            model=OPENAI_MODEL,
            prompt_version=payload.prompt_version,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            total_tokens=total_tokens,
            status="SUCCESS",
            estimated_cost_usd=estimated_cost_usd,
        )

        return AnalyzeResponse(
            analysis=analysis,
            metadata=metadata,
            evidence=SkillEvidence(),
        )

    except (json.JSONDecodeError, ValidationError) as error:
        latency_ms = int((time.perf_counter() - started_at) * 1000)

        raise HTTPException(
            status_code=502,
            detail={
                "message": "Model returned invalid structured output",
                "error": str(error),
                "metadata": {
                    "endpoint": "/analyze",
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
                "message": "AI analysis failed",
                "error": str(error),
                "metadata": {
                    "endpoint": "/analyze",
                    "model": OPENAI_MODEL,
                    "prompt_version": payload.prompt_version,
                    "latency_ms": latency_ms,
                    "status": "FAILED",
                    "error_type": type(error).__name__,
                },
            },
        )