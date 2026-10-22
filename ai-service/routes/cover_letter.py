import json

from fastapi import APIRouter
from pydantic import BaseModel, Field

from llm import LLMCallError, RunMetadata, call_structured
from prompt_loader import load_prompt
from routes.errors import http_error_from_llm
from skills.grounding import find_placeholders, find_unsupported_quotes

router = APIRouter()

ENDPOINT = "/cover-letter"
GREETING = "Dear Hiring Manager,"


class CoverLetterRequest(BaseModel):
    resume_text: str = Field(..., min_length=50)
    job_description: str = Field(..., min_length=50)
    prompt_version: str = "cover_letter_v2"


class CoverLetterParagraph(BaseModel):
    text: str
    supporting_resume_quotes: list[str]


class CoverLetterDraft(BaseModel):
    paragraphs: list[CoverLetterParagraph]
    closing_sentence: str


class CoverLetterGrounding(BaseModel):
    """Deterministic checks on the draft. unsupported_quotes are 'evidence'
    the model claimed to copy from the resume that is not actually there."""

    quotes_checked: int
    unsupported_quotes: list[str]
    placeholders: list[str]


class CoverLetterResponse(BaseModel):
    content: str
    paragraphs: list[CoverLetterParagraph]
    grounding: CoverLetterGrounding
    metadata: RunMetadata


def assemble_letter(draft: CoverLetterDraft) -> str:
    body = [paragraph.text.strip() for paragraph in draft.paragraphs if paragraph.text.strip()]
    return "\n\n".join([GREETING, *body, draft.closing_sentence.strip()])


def check_grounding(draft: CoverLetterDraft, resume_text: str, content: str) -> CoverLetterGrounding:
    quotes = [quote for paragraph in draft.paragraphs for quote in paragraph.supporting_resume_quotes]
    return CoverLetterGrounding(
        quotes_checked=len(quotes),
        unsupported_quotes=find_unsupported_quotes(quotes, resume_text),
        placeholders=find_placeholders(content),
    )


def run_cover_letter(request: CoverLetterRequest, **llm_kwargs) -> CoverLetterResponse:
    result = call_structured(
        endpoint=ENDPOINT,
        prompt_version=request.prompt_version,
        system=load_prompt(request.prompt_version),
        user=json.dumps(
            {
                "resume_text": request.resume_text,
                "job_description": request.job_description,
            }
        ),
        schema=CoverLetterDraft,
        temperature=0.3,
        max_output_tokens=900,
        **llm_kwargs,
    )

    draft = result.parsed
    content = assemble_letter(draft)

    return CoverLetterResponse(
        content=content,
        paragraphs=draft.paragraphs,
        grounding=check_grounding(draft, request.resume_text, content),
        metadata=result.metadata,
    )


@router.post("/cover-letter", response_model=CoverLetterResponse)
def create_cover_letter(request: CoverLetterRequest):
    try:
        return run_cover_letter(request)
    except LLMCallError as error:
        raise http_error_from_llm(error, "Cover letter generation failed") from error
