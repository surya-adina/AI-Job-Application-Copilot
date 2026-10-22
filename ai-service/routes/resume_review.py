import json
import re
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from llm import LLMCallError, RunMetadata, call_structured
from prompt_loader import load_prompt
from routes.errors import http_error_from_llm

router = APIRouter()

ENDPOINT = "/resume-review"


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

class ResumeReviewResponse(BaseModel):
    review: ResumeReviewPayload
    metadata: RunMetadata

def normalize_review_text(text: str) -> str:
    replacements = {
        "Go Lang": "Go",
        "Go lang": "Go",
        "go lang": "Go",
    }

    cleaned = text.strip()

    for wrong, right in replacements.items():
        cleaned = cleaned.replace(wrong, right)

    return cleaned


def mentions_go(text: str) -> bool:
    return bool(re.search(r"\b(go|golang|go lang)\b", text.lower()))


def mentions_open_source(text: str) -> bool:
    lowered = text.lower()
    return "open-source" in lowered or "open source" in lowered or "sdk" in lowered


def clean_suggestion(suggestion: ResumeSuggestion) -> ResumeSuggestion:
    combined_text = " ".join(
        [
            suggestion.title,
            suggestion.why,
            suggestion.action,
            " ".join(suggestion.evidence),
        ]
    )

    evidence = [normalize_review_text(point) for point in suggestion.evidence]

    if mentions_go(combined_text):
        return ResumeSuggestion(
            priority="LOW",
            title="Treat Go as a preferred growth area",
            target_section="Skills or Projects",
            why="The job mentions Go as a plus or preferred skill, but this should not be treated as a major resume gap unless the candidate has real Go experience.",
            evidence=evidence,
            action="Do not add Go unless you have genuinely used it. If applicable, mention real Go experience with a specific project or work example; otherwise emphasize adjacent typed-language experience already present in the resume.",
        )

    if mentions_open_source(combined_text):
        return ResumeSuggestion(
            priority="MEDIUM",
            title="Clarify open-source or SDK-related work if applicable",
            target_section=suggestion.target_section or "Projects",
            why="The job values open-source or SDK-related work, but this should only be added if the candidate has real experience to support it.",
            evidence=evidence,
            action="If you have contributed to open-source projects or built developer-facing tools, mention the specific project and contribution. If not, do not claim open-source experience; emphasize relevant GitHub projects or full-stack project work instead.",
        )

    return ResumeSuggestion(
        priority=suggestion.priority,
        title=normalize_review_text(suggestion.title),
        target_section=normalize_review_text(suggestion.target_section),
        why=normalize_review_text(suggestion.why),
        evidence=evidence,
        action=normalize_review_text(suggestion.action),
    )


def clean_resume_review(review: ResumeReviewPayload) -> ResumeReviewPayload:
    cleaned_suggestions = []
    seen = set()

    for suggestion in review.suggestions:
        cleaned = clean_suggestion(suggestion)

        key = re.sub(
            r"[^a-z0-9]+",
            " ",
            f"{cleaned.title} {cleaned.action}".lower(),
        ).strip()

        if key in seen:
            continue

        seen.add(key)
        cleaned_suggestions.append(cleaned)

    return ResumeReviewPayload(
        summary=normalize_review_text(review.summary),
        suggestions=cleaned_suggestions[:5],
        growth_areas=[normalize_review_text(item) for item in review.growth_areas],
        warnings=[normalize_review_text(item) for item in review.warnings],
    )

def build_resume_review_user_prompt(payload: ResumeReviewRequest) -> str:
    return json.dumps(
        {
            "resume_text": payload.resume_text,
            "job_description": payload.job_description,
            "analysis": payload.analysis,
            "evidence": payload.evidence,
        }
    )


def run_resume_review(payload: ResumeReviewRequest, **llm_kwargs) -> ResumeReviewResponse:
    result = call_structured(
        endpoint=ENDPOINT,
        prompt_version=payload.prompt_version,
        system=load_prompt(payload.prompt_version),
        user=build_resume_review_user_prompt(payload),
        schema=ResumeReviewPayload,
        temperature=0.2,
        max_output_tokens=1200,
        **llm_kwargs,
    )

    return ResumeReviewResponse(
        review=clean_resume_review(result.parsed),
        metadata=result.metadata,
    )


@router.post("/resume-review", response_model=ResumeReviewResponse)
def review_resume(payload: ResumeReviewRequest):
    try:
        return run_resume_review(payload)
    except LLMCallError as error:
        raise http_error_from_llm(error, "Resume review failed") from error
