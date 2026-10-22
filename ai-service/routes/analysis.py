import json

from fastapi import APIRouter
from pydantic import BaseModel, Field

from llm import LLMCallError, RunMetadata, call_structured
from prompt_loader import load_prompt
from routes.errors import http_error_from_llm

router = APIRouter()

ENDPOINT = "/analyze"


class AnalyzeRequest(BaseModel):
    resume_text: str = Field(..., min_length=50)
    job_description: str = Field(..., min_length=50)
    prompt_version: str = "analysis_v1"


class AnalysisLLMOutput(BaseModel):
    """Shape the model must return (strict Structured Outputs). No numeric
    constraints here: strict mode can't enforce them reliably, so we clamp below."""

    score: int
    matched_skills: list[str]
    missing_skills: list[str]
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]


class AnalysisPayload(BaseModel):
    score: int = Field(..., ge=0, le=100)
    matched_skills: list[str]
    missing_skills: list[str]
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]


class SkillEvidence(BaseModel):
    resume_skills: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    missing_preferred_skills: list[str] = Field(default_factory=list)
    semantic_matches: list[dict] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    analysis: AnalysisPayload
    metadata: RunMetadata
    evidence: SkillEvidence


def dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []

    for item in items:
        value = item.strip()
        key = value.lower()

        if not value or key in seen:
            continue

        seen.add(key)
        result.append(value)

    return result


def clean_analysis(analysis: AnalysisLLMOutput) -> AnalysisPayload:
    return AnalysisPayload(
        score=max(0, min(100, analysis.score)),
        matched_skills=dedupe(analysis.matched_skills)[:10],
        missing_skills=dedupe(analysis.missing_skills)[:8],
        strengths=dedupe(analysis.strengths)[:3],
        weaknesses=dedupe(analysis.weaknesses)[:3],
        recommendations=dedupe(analysis.recommendations)[:3],
    )


def run_analysis(payload: AnalyzeRequest, **llm_kwargs) -> AnalyzeResponse:
    result = call_structured(
        endpoint=ENDPOINT,
        prompt_version=payload.prompt_version,
        system=load_prompt(payload.prompt_version),
        user=json.dumps(
            {
                "resume_text": payload.resume_text,
                "job_description": payload.job_description,
            }
        ),
        schema=AnalysisLLMOutput,
        temperature=0.2,
        max_output_tokens=850,
        **llm_kwargs,
    )

    return AnalyzeResponse(
        analysis=clean_analysis(result.parsed),
        metadata=result.metadata,
        evidence=SkillEvidence(),
    )


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
    try:
        return run_analysis(payload)
    except LLMCallError as error:
        raise http_error_from_llm(error, "AI analysis failed") from error
