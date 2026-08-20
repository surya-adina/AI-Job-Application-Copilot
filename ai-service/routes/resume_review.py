import json
import os
import re
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
    context = {
        "resume_text": payload.resume_text,
        "job_description": payload.job_description,
        "analysis": payload.analysis,
        "evidence": payload.evidence,
    }

    return (
        "Return valid JSON only.\n"
        "Do not copy the input context.\n"
        "Do not include resume_text, job_description, analysis, evidence, task, context, or output_schema as top-level keys.\n"
        "The top-level JSON keys must be exactly: summary, suggestions, growth_areas, warnings.\n\n"
        "Required JSON shape:\n"
        "{\n"
        '  "summary": "short overview of the review",\n'
        '  "suggestions": [\n'
        "    {\n"
        '      "priority": "HIGH | MEDIUM | LOW",\n'
        '      "title": "specific recommendation title",\n'
        '      "target_section": "Summary, Experience, Projects, Skills, or Education",\n'
        '      "why": "why this recommendation matters",\n'
        '      "evidence": ["supporting evidence"],\n'
        '      "action": "truthful action the candidate can take"\n'
        "    }\n"
        "  ],\n"
        '  "growth_areas": ["optional growth areas"],\n'
        '  "warnings": ["truthfulness warnings only if needed"]\n'
        "}\n\n"
        "Context JSON:\n"
        + json.dumps(context)
    )

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
                    "content": build_resume_review_user_prompt(payload),
                },
            ],
            temperature=0.2,
            max_output_tokens=850,
            text={"format": {"type": "json_object"}},
        )

        latency_ms = int((time.perf_counter() - started_at) * 1000)

        parsed = json.loads(response.output_text)
        review = ResumeReviewPayload(**parsed)
        review = clean_resume_review(review)

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