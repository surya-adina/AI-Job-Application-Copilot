import json
from typing import Literal

from pydantic import BaseModel, Field

from llm import call_structured
from prompt_loader import load_prompt
from skills.claim_verifier import Claim, ClaimVerdict, rewrite_problems, verify_claims
from skills.llm_job_requirements import extract_job_requirements_llm_with_metadata
from skills.safe_fetch import FetchError, fetch_page
from skills.skill_matcher import SkillEvidence, match_skills
from tools.base import Tool, ToolContext, ToolError, register

MIN_POSTING_CHARS = 200

# ---------- fetch_job_posting ----------


class FetchJobPostingInput(BaseModel):
    url: str = Field(..., max_length=2048, description="Public http(s) URL of a job posting.")


class FetchJobPostingOutput(BaseModel):
    url: str = Field(description="Final URL after redirects.")
    title: str | None
    text: str
    content_type: str
    bytes_read: int
    redirects: int


def fetch_job_posting(args: FetchJobPostingInput, context: ToolContext):
    try:
        page = (context.fetcher or fetch_page)(args.url)
    except FetchError as error:
        raise ToolError(error.code, str(error)) from error

    if len(page.text) < MIN_POSTING_CHARS:
        raise ToolError(
            "no_text",
            "The page has almost no text. It may be rendered by JavaScript; paste the job description instead.",
        )

    return FetchJobPostingOutput(**page.__dict__), []


register(
    Tool(
        name="fetch_job_posting",
        description=(
            "Download a public job posting page and return its readable text. Only public http(s) addresses on "
            "ports 80/443 are allowed; internal, private and metadata addresses are refused."
        ),
        input_model=FetchJobPostingInput,
        output_model=FetchJobPostingOutput,
        handler=fetch_job_posting,
    )
)

# ---------- extract_requirements ----------


class ExtractRequirementsInput(BaseModel):
    job_description: str = Field(..., min_length=50)


class ExtractRequirementsOutput(BaseModel):
    required_skills: list[str]
    preferred_skills: list[str]


def extract_requirements(args: ExtractRequirementsInput, context: ToolContext):
    requirements, metadata = extract_job_requirements_llm_with_metadata(args.job_description, **context.llm_kwargs)
    return ExtractRequirementsOutput(**requirements), [metadata]


register(
    Tool(
        name="extract_requirements",
        description="List the required and preferred skills in a job description.",
        input_model=ExtractRequirementsInput,
        output_model=ExtractRequirementsOutput,
        handler=extract_requirements,
    )
)

# ---------- match_skills ----------


class MatchSkillsInput(BaseModel):
    resume_text: str = Field(..., min_length=50)
    job_description: str = Field(..., min_length=50)
    mode: Literal["llm", "verified"] | None = Field(
        default=None, description="Matching mode; defaults to SKILL_MATCH_MODE."
    )


def match_skills_tool(args: MatchSkillsInput, context: ToolContext):
    kwargs = dict(context.llm_kwargs)
    if context.connection_factory is not None:
        from skills.semantic_matcher import PgVectorSimilarity

        kwargs["similarity_factory"] = lambda: PgVectorSimilarity(context.connection_factory())
    evidence, metadata = match_skills(args.resume_text, args.job_description, mode=args.mode, **kwargs)
    return evidence, [metadata]


register(
    Tool(
        name="match_skills",
        description=(
            "Compare a resume with a job description skill by skill: each job skill with its priority, whether "
            "the resume shows it, and the resume quote that supports it."
        ),
        input_model=MatchSkillsInput,
        output_model=SkillEvidence,
        handler=match_skills_tool,
    )
)

# ---------- search_resume_evidence ----------


class SearchResumeEvidenceInput(BaseModel):
    resume_id: str = Field(..., min_length=1, max_length=64)
    resume_text: str = Field(..., min_length=50, description="Current resume text; chunks are re-indexed when it changes.")
    query: str = Field(..., min_length=2, max_length=500)
    k: int = Field(default=5, ge=1, le=20)


class EvidenceChunk(BaseModel):
    id: int = Field(description="Chunk index; cite it as an evidence id.")
    text: str
    start: int
    end: int
    similarity: float


class SearchResumeEvidenceOutput(BaseModel):
    chunks: list[EvidenceChunk]
    indexed_chunks: int


def search_resume_evidence(args: SearchResumeEvidenceInput, context: ToolContext):
    from skills.embedding_store import get_connection
    from skills.resume_chunks import index_resume, search_resume

    connection = (context.connection_factory or get_connection)()
    try:
        indexed = index_resume(connection, args.resume_id, args.resume_text)
        matches = search_resume(connection, args.resume_id, args.query, args.k)
    except Exception as error:
        if type(error).__name__ == "ForeignKeyViolation":
            raise ToolError("unknown_resume", f"No resume with id {args.resume_id}") from error
        raise
    finally:
        connection.close()

    chunks = [
        EvidenceChunk(id=match.index, text=match.text, start=match.start, end=match.end, similarity=match.similarity)
        for match in matches
    ]
    return SearchResumeEvidenceOutput(chunks=chunks, indexed_chunks=indexed), []


register(
    Tool(
        name="search_resume_evidence",
        description=(
            "Find the parts of a resume most relevant to a query (semantic search over resume chunks). Returned "
            "chunks are verbatim resume text and can be cited as evidence."
        ),
        input_model=SearchResumeEvidenceInput,
        output_model=SearchResumeEvidenceOutput,
        handler=search_resume_evidence,
    )
)

# ---------- draft_section ----------

DRAFT_PROMPT_VERSION = "draft_section_v1"


class EvidenceItem(BaseModel):
    id: int
    text: str


class DraftSectionInput(BaseModel):
    section: Literal["cover_letter_paragraph", "resume_bullet", "professional_summary", "interview_answer"]
    instructions: str = Field(..., min_length=3, max_length=2000)
    job_description: str = Field(..., min_length=50)
    evidence: list[EvidenceItem] = Field(..., min_length=1, max_length=30)


class DraftClaim(BaseModel):
    text: str
    evidence_ids: list[int]


class DraftSectionLLMOutput(BaseModel):
    text: str
    claims: list[DraftClaim]


class DraftSectionOutput(BaseModel):
    text: str
    claims: list[Claim] = Field(description="Claims with the cited evidence text, ready for verify_claims.")
    unknown_evidence_ids: list[int]


def draft_section(args: DraftSectionInput, context: ToolContext):
    result = call_structured(
        endpoint="tool:draft_section",
        prompt_version=DRAFT_PROMPT_VERSION,
        system=load_prompt(DRAFT_PROMPT_VERSION),
        user=json.dumps(
            {
                "section": args.section,
                "instructions": args.instructions,
                "job_description": args.job_description,
                "evidence": [item.model_dump() for item in args.evidence],
            }
        ),
        schema=DraftSectionLLMOutput,
        temperature=0.3,
        max_output_tokens=900,
        **context.llm_kwargs,
    )

    evidence_by_id = {item.id: item.text for item in args.evidence}
    unknown = sorted({i for claim in result.parsed.claims for i in claim.evidence_ids if i not in evidence_by_id})
    claims = [
        Claim(text=claim.text, evidence=[evidence_by_id[i] for i in claim.evidence_ids if i in evidence_by_id])
        for claim in result.parsed.claims
    ]
    return DraftSectionOutput(text=result.parsed.text, claims=claims, unknown_evidence_ids=unknown), [result.metadata]


register(
    Tool(
        name="draft_section",
        description=(
            "Write one application section (cover letter paragraph, resume bullet, professional summary or "
            "interview answer) from numbered resume evidence. Returns the text and each factual claim with the "
            "evidence it cites."
        ),
        input_model=DraftSectionInput,
        output_model=DraftSectionOutput,
        handler=draft_section,
    )
)

# ---------- rewrite_bullet ----------

REWRITE_PROMPT_VERSION = "rewrite_bullet_v1"


class RewriteBulletInput(BaseModel):
    original: str = Field(..., min_length=10, max_length=1500, description="The resume line to tailor.")
    goal: str = Field(..., min_length=3, max_length=500, description="What the line should emphasize for this job.")
    job_description: str = Field(..., min_length=50)
    feedback: list[str] = Field(default_factory=list, max_length=20, description="Fact-check problems to fix.")


class RewriteBulletLLMOutput(BaseModel):
    text: str


class RewriteBulletOutput(BaseModel):
    text: str
    unchanged: bool
    problems: list[str] = Field(
        description="Skills, numbers or wording in the rewrite that the original line does not state."
    )


def rewrite_bullet(args: RewriteBulletInput, context: ToolContext):
    result = call_structured(
        endpoint="tool:rewrite_bullet",
        prompt_version=REWRITE_PROMPT_VERSION,
        system=load_prompt(REWRITE_PROMPT_VERSION),
        user=json.dumps(
            {
                "original": args.original,
                "goal": args.goal,
                "job_description": args.job_description,
                "fact_checker_feedback": args.feedback,
            }
        ),
        schema=RewriteBulletLLMOutput,
        temperature=0.3,
        max_output_tokens=400,
        **context.llm_kwargs,
    )
    text = result.parsed.text.strip().lstrip("•-*▪● ").strip()
    problems = rewrite_problems(text, args.original)
    output = RewriteBulletOutput(
        text=text, unchanged=" ".join(text.split()) == " ".join(args.original.split()), problems=problems
    )
    return output, [result.metadata]


register(
    Tool(
        name="rewrite_bullet",
        description=(
            "Rewrite one resume line in a job's terms without changing what it claims, and check the rewrite: any "
            "skill, number or new wording the original line does not state is reported in problems."
        ),
        input_model=RewriteBulletInput,
        output_model=RewriteBulletOutput,
        handler=rewrite_bullet,
    )
)

# ---------- verify_claims ----------


class VerifyClaimsInput(BaseModel):
    resume_text: str = Field(..., min_length=50)
    claims: list[Claim] = Field(..., min_length=1, max_length=50)
    require_evidence: bool = Field(default=True, description="Reject claims that cite no evidence.")


class VerifyClaimsOutput(BaseModel):
    verdicts: list[ClaimVerdict]
    supported_count: int
    unsupported_count: int
    all_supported: bool


def verify_claims_tool(args: VerifyClaimsInput, context: ToolContext):
    verdicts = verify_claims(args.claims, args.resume_text, args.require_evidence)
    supported = sum(verdict.supported for verdict in verdicts)
    return (
        VerifyClaimsOutput(
            verdicts=verdicts,
            supported_count=supported,
            unsupported_count=len(verdicts) - supported,
            all_supported=supported == len(verdicts),
        ),
        [],
    )


register(
    Tool(
        name="verify_claims",
        description=(
            "Check claims about the candidate against the resume. A claim passes only if its cited quotes are in "
            "the resume and not hedged, and every skill and number it states appears in those quotes."
        ),
        input_model=VerifyClaimsInput,
        output_model=VerifyClaimsOutput,
        handler=verify_claims_tool,
    )
)
