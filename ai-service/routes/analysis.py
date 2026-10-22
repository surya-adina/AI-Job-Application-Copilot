import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from fastapi import APIRouter
from pydantic import BaseModel, Field

from llm import LLMCallError, RunMetadata, call_structured
from prompt_loader import load_prompt
from routes.errors import http_error_from_llm
from skills.skill_matcher import SkillEvidence, match_skills

router = APIRouter()
logger = logging.getLogger(__name__)

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


class AnalyzeResponse(BaseModel):
    analysis: AnalysisPayload
    metadata: RunMetadata
    evidence: SkillEvidence
    # Additional LLM calls made for this request (skill matching), logged as separate AiRun rows.
    runs: list[RunMetadata] = Field(default_factory=list)


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


def run_skill_matching(
    payload: AnalyzeRequest, skill_matcher: Callable = match_skills, **llm_kwargs
) -> tuple[SkillEvidence, list[RunMetadata]]:
    """Skill evidence is supplementary: a failure here must not fail the analysis."""
    try:
        evidence, metadata = skill_matcher(payload.resume_text, payload.job_description, **llm_kwargs)
        return evidence, [metadata]
    except LLMCallError as error:
        logger.warning("Skill matching failed: %s", error)
        return SkillEvidence(mode="failed"), [error.metadata]
    except Exception:
        logger.exception("Skill matching failed")
        return SkillEvidence(mode="failed"), []


def run_analysis(payload: AnalyzeRequest, skill_matcher: Callable = match_skills, **llm_kwargs) -> AnalyzeResponse:
    # Resolve the prompt first so an invalid prompt_version fails before any LLM call starts.
    system_prompt = load_prompt(payload.prompt_version)

    with ThreadPoolExecutor(max_workers=1) as pool:
        skill_future = pool.submit(run_skill_matching, payload, skill_matcher, **llm_kwargs)
        analysis, metadata = run_fit_analysis(payload, system_prompt, **llm_kwargs)
        evidence, runs = skill_future.result()

    return AnalyzeResponse(analysis=analysis, metadata=metadata, evidence=evidence, runs=runs)


def run_fit_analysis(payload: AnalyzeRequest, system_prompt: str, **llm_kwargs) -> tuple[AnalysisPayload, RunMetadata]:
    result = call_structured(
        endpoint=ENDPOINT,
        prompt_version=payload.prompt_version,
        system=system_prompt,
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

    return clean_analysis(result.parsed), result.metadata


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
    try:
        return run_analysis(payload)
    except LLMCallError as error:
        raise http_error_from_llm(error, "AI analysis failed") from error
