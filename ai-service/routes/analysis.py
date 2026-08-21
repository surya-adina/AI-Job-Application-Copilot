import time
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from skills.extractor import extract_known_skills
from skills.job_requirements import extract_job_requirements

router = APIRouter()
PROMPT_VERSION = "deterministic-analysis-v1"


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
    resume_skills: list[str]
    required_skills: list[str]
    preferred_skills: list[str]
    missing_required_skills: list[str]
    missing_preferred_skills: list[str]
    semantic_matches: list[dict]


class AnalyzeResponse(BaseModel):
    analysis: AnalysisPayload
    metadata: AiRunMetadata
    evidence: SkillEvidence


def calculate_score(
    required_skills: list[str],
    preferred_skills: list[str],
    missing_required_skills: list[str],
    missing_preferred_skills: list[str],
) -> int:
    required_total = len(required_skills)
    preferred_total = len(preferred_skills)

    if required_total == 0 and preferred_total == 0:
        return 50

    required_matched = required_total - len(missing_required_skills)
    preferred_matched = preferred_total - len(missing_preferred_skills)

    if required_total > 0 and preferred_total > 0:
        required_score = required_matched / required_total
        preferred_score = preferred_matched / preferred_total
        score = (required_score * 0.75) + (preferred_score * 0.25)
    elif required_total > 0:
        score = required_matched / required_total
    else:
        score = preferred_matched / preferred_total

    return max(0, min(100, round(score * 100)))


def build_recommendations(
    missing_required_skills: list[str],
    missing_preferred_skills: list[str],
) -> list[str]:
    recommendations = []

    for skill in missing_required_skills[:3]:
        recommendations.append(
            f"If you genuinely have experience with {skill}, add a concrete example in your Skills, Projects, or Experience section. If not, treat it as a required gap."
        )

    remaining_slots = 3 - len(recommendations)

    if remaining_slots > 0:
        for skill in missing_preferred_skills[:remaining_slots]:
            recommendations.append(
                f"If applicable, mention {skill} with a specific project or work example. If you have not used it, do not add it."
            )

    return recommendations


def build_strengths(
    resume_skills: list[str],
    required_skills: list[str],
    preferred_skills: list[str],
) -> list[str]:
    resume_skill_set = set(resume_skills)
    matched_required = sorted(resume_skill_set.intersection(required_skills))
    matched_preferred = sorted(resume_skill_set.intersection(preferred_skills))

    strengths = []

    if matched_required:
        strengths.append(
            f"Resume shows required skill alignment in {', '.join(matched_required[:5])}."
        )

    if matched_preferred:
        strengths.append(
            f"Resume also supports preferred skills such as {', '.join(matched_preferred[:5])}."
        )

    if not strengths:
        strengths.append(
            "Resume has limited direct skill overlap with the extracted job requirements."
        )

    return strengths[:3]


def build_weaknesses(
    missing_required_skills: list[str],
    missing_preferred_skills: list[str],
) -> list[str]:
    weaknesses = []

    if missing_required_skills:
        weaknesses.append(
            f"Missing required skill evidence for {', '.join(missing_required_skills[:5])}."
        )

    if missing_preferred_skills:
        weaknesses.append(
            f"Missing preferred skill evidence for {', '.join(missing_preferred_skills[:5])}."
        )

    if not weaknesses:
        weaknesses.append(
            "No major skill gaps were detected by the saved skill analysis."
        )

    return weaknesses[:3]


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
    started_at = time.perf_counter()

    try:
        resume_skills = extract_known_skills(payload.resume_text)

        job_requirements = extract_job_requirements(payload.job_description)
        required_skills = job_requirements["required_skills"]
        preferred_skills = job_requirements["preferred_skills"]
        job_skills = sorted(set(required_skills + preferred_skills))

        resume_skill_set = set(resume_skills)

        missing_required_skills = sorted(
            skill for skill in required_skills if skill not in resume_skill_set
        )

        missing_preferred_skills = sorted(
            skill for skill in preferred_skills if skill not in resume_skill_set
        )

        matched_skills = sorted(resume_skill_set.intersection(job_skills))

        analysis = AnalysisPayload(
            score=calculate_score(
                required_skills=required_skills,
                preferred_skills=preferred_skills,
                missing_required_skills=missing_required_skills,
                missing_preferred_skills=missing_preferred_skills,
            ),
            matched_skills=matched_skills[:8],
            missing_skills=sorted(
                set(missing_required_skills + missing_preferred_skills)
            )[:8],
            strengths=build_strengths(
                resume_skills=resume_skills,
                required_skills=required_skills,
                preferred_skills=preferred_skills,
            ),
            weaknesses=build_weaknesses(
                missing_required_skills=missing_required_skills,
                missing_preferred_skills=missing_preferred_skills,
            ),
            recommendations=build_recommendations(
                missing_required_skills=missing_required_skills,
                missing_preferred_skills=missing_preferred_skills,
            ),
        )

        evidence = SkillEvidence(
            resume_skills=resume_skills,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            missing_required_skills=missing_required_skills,
            missing_preferred_skills=missing_preferred_skills,
            semantic_matches=[],
        )

        latency_ms = int((time.perf_counter() - started_at) * 1000)

        metadata = AiRunMetadata(
            endpoint="/analyze",
            model="deterministic-skill-matcher",
            prompt_version=PROMPT_VERSION,
            latency_ms=latency_ms,
            tokens_in=0,
            tokens_out=0,
            total_tokens=0,
            status="SUCCESS",
            estimated_cost_usd=0,
        )

        return AnalyzeResponse(
            analysis=analysis,
            metadata=metadata,
            evidence=evidence,
        )

    except Exception as error:
        latency_ms = int((time.perf_counter() - started_at) * 1000)

        metadata = AiRunMetadata(
            endpoint="/analyze",
            model="deterministic-skill-matcher",
            prompt_version=PROMPT_VERSION,
            latency_ms=latency_ms,
            tokens_in=0,
            tokens_out=0,
            total_tokens=0,
            status="FAILED",
            error_type=type(error).__name__,
            estimated_cost_usd=0,
        )

        raise HTTPException(
            status_code=500,
            detail={
                "message": "Deterministic analysis failed",
                "error": str(error),
                "metadata": metadata.model_dump(),
            },
        )
