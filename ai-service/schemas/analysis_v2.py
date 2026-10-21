from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ResumeSectionType(str, Enum):
    SUMMARY = "summary"
    EDUCATION = "education"
    EXPERIENCE = "experience"
    PROJECTS = "projects"
    SKILLS = "skills"
    CERTIFICATIONS = "certifications"
    PUBLICATIONS = "publications"
    AWARDS = "awards"
    OTHER = "other"


class RequirementType(str, Enum):
    SKILL = "skill"
    TOOL = "tool"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    DOMAIN = "domain"
    WORKFLOW = "workflow"
    ELIGIBILITY = "eligibility"
    RESPONSIBILITY = "responsibility"
    SOFT_SKILL = "soft_skill"
    OTHER = "other"


class RequirementPriority(str, Enum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    NICE_TO_HAVE = "nice_to_have"


class RequirementStatus(str, Enum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    MISSING = "missing"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class EligibilityStatus(str, Enum):
    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class ViabilityStatus(str, Enum):
    VIABLE = "viable"
    CONDITIONAL = "conditional"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class ScoreConfidence(str, Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class ResumeSection(BaseModel):
    id: str
    section_type: ResumeSectionType
    title: str | None = None

    text: str
    normalized_text: str

    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    order_index: int = Field(ge=0)


class ResumeEvidence(BaseModel):
    id: str
    requirement_id: str

    resume_section_id: str | None = None
    section_type: ResumeSectionType | None = None
    source_label: str | None = None

    quote: str
    normalized_quote: str

    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)

    confidence: float = Field(ge=0.0, le=1.0)


class JobRequirement(BaseModel):
    id: str

    name: str
    normalized_name: str
    description: str | None = None

    type: RequirementType
    priority: RequirementPriority

    weight: float = Field(ge=1.0, le=5.0)

    hard_filter: bool = False

    source_sentence: str
    jd_section: str | None = None

    jd_start_offset: int | None = Field(default=None, ge=0)
    jd_end_offset: int | None = Field(default=None, ge=0)

    order_index: int = Field(ge=0)


class RequirementMatch(BaseModel):
    id: str
    requirement_id: str

    status: RequirementStatus
    confidence: float = Field(ge=0.0, le=1.0)

    evidence: list[ResumeEvidence] = Field(default_factory=list)

    explanation: str


class EligibilityFlag(BaseModel):
    id: str
    requirement_id: str | None = None

    name: str
    status: EligibilityStatus

    hard_filter: bool

    source_sentence: str
    jd_section: str | None = None

    explanation: str


class ScoreBreakdown(BaseModel):
    technical_match_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )

    required_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )

    preferred_match_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )

    nice_to_have_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )

    requirement_coverage_score: float = Field(
        ge=0,
        le=100,
    )

    score_confidence: ScoreConfidence

    known_scorable_weight: float = Field(ge=0)
    unknown_scorable_weight: float = Field(ge=0)
    not_applicable_weight: float = Field(ge=0)

    supported_weight: float = Field(ge=0)
    partial_weight: float = Field(ge=0)
    missing_weight: float = Field(ge=0)

    total_scorable_weight: float = Field(ge=0)

    scoring_version: str


class ApplicationViability(BaseModel):
    status: ViabilityStatus

    blocking_flags: list[EligibilityFlag] = Field(default_factory=list)
    unknown_flags: list[EligibilityFlag] = Field(default_factory=list)
    non_blocking_flags: list[EligibilityFlag] = Field(default_factory=list)

    explanation: str


class AnalysisMetadata(BaseModel):
    analysis_version: str
    requirement_extractor_prompt_version: str
    requirement_matcher_prompt_version: str
    scoring_version: str

    model: str

    status: Literal[
        "success",
        "failed",
        "partially_failed",
    ]

    latency_ms: int = Field(ge=0)

    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    estimated_cost_usd: float | None = Field(default=None, ge=0)

    created_at: datetime


class AnalysisResult(BaseModel):
    resume_sections: list[ResumeSection]

    requirements: list[JobRequirement]
    matches: list[RequirementMatch]

    eligibility_flags: list[EligibilityFlag]

    score_breakdown: ScoreBreakdown | None
    application_viability: ApplicationViability

    matched_requirements: list[str] = Field(default_factory=list)
    partial_match_gaps: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)

    top_strengths: list[str] = Field(default_factory=list)
    top_weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    narrative_summary: str | None = None

    metadata: AnalysisMetadata