import json
import re
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from llm import LLMCallError, RunMetadata, call_structured
from prompt_loader import load_prompt
from routes.errors import http_error_from_llm
from skills.claim_verifier import skills_missing_from_resume

router = APIRouter()

ENDPOINT = "/resume-review"


class ResumeReviewRequest(BaseModel):
    resume_text: str = Field(..., min_length=50)
    job_description: str = Field(..., min_length=50)
    analysis: dict
    evidence: dict
    prompt_version: str = "resume_review_v1"


class ResumeSuggestionDraft(BaseModel):
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    title: str
    target_section: str
    why: str
    evidence: list[str]
    action: str


class ResumeReviewDraft(BaseModel):
    """Shape the model returns."""

    summary: str
    suggestions: list[ResumeSuggestionDraft]
    growth_areas: list[str]
    warnings: list[str]


class ResumeSuggestion(ResumeSuggestionDraft):
    # Skills the suggestion names that the resume does not show (claim verifier).
    unsupported_skills: list[str] = Field(default_factory=list)


class ResumeReviewPayload(BaseModel):
    summary: str
    suggestions: list[ResumeSuggestion]
    growth_areas: list[str]
    warnings: list[str]


class ResumeReviewResponse(BaseModel):
    review: ResumeReviewPayload
    metadata: RunMetadata


def ground_suggestion(suggestion: ResumeSuggestionDraft, resume_text: str) -> ResumeSuggestion:
    """A suggestion may point at a skill the resume does not show (a gap to
    close). Flag those skills and make sure the action never reads as advice to
    claim them."""
    unsupported = skills_missing_from_resume(f"{suggestion.title} {suggestion.action}", resume_text)
    action = suggestion.action.strip()

    if unsupported:
        names = ", ".join(unsupported)
        it = "them" if len(unsupported) > 1 else "it"
        action = f"{action} Only add {names} to the resume once you have real experience with {it}; the resume does not show {it} yet."

    return ResumeSuggestion(**suggestion.model_dump(exclude={"action"}), action=action, unsupported_skills=unsupported)


def clean_resume_review(review: ResumeReviewDraft, resume_text: str) -> ResumeReviewPayload:
    cleaned_suggestions = []
    seen = set()

    for suggestion in review.suggestions:
        key = re.sub(r"[^a-z0-9]+", " ", f"{suggestion.title} {suggestion.action}".lower()).strip()
        if key in seen:
            continue

        seen.add(key)
        cleaned_suggestions.append(ground_suggestion(suggestion, resume_text))

    return ResumeReviewPayload(
        summary=review.summary.strip(),
        suggestions=cleaned_suggestions[:5],
        growth_areas=[item.strip() for item in review.growth_areas],
        warnings=[item.strip() for item in review.warnings],
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
        schema=ResumeReviewDraft,
        temperature=0.2,
        max_output_tokens=1200,
        **llm_kwargs,
    )

    return ResumeReviewResponse(
        review=clean_resume_review(result.parsed, payload.resume_text),
        metadata=result.metadata,
    )


@router.post("/resume-review", response_model=ResumeReviewResponse)
def review_resume(payload: ResumeReviewRequest):
    try:
        return run_resume_review(payload)
    except LLMCallError as error:
        raise http_error_from_llm(error, "Resume review failed") from error
