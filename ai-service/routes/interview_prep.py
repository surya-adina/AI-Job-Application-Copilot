import json

from fastapi import APIRouter
from pydantic import BaseModel, Field

from llm import LLMCallError, RunMetadata, call_structured
from prompt_loader import load_prompt
from routes.errors import http_error_from_llm

router = APIRouter()

ENDPOINT = "/interview-prep"


class InterviewPrepRequest(BaseModel):
    resume_text: str = Field(..., min_length=50)
    job_description: str = Field(..., min_length=50)
    prompt_version: str = "interview_prep_v2"


class InterviewQuestion(BaseModel):
    question: str
    why_it_matters: str
    suggested_focus: str


class InterviewPrepPayload(BaseModel):
    technical_questions: list[InterviewQuestion]
    behavioral_questions: list[InterviewQuestion]
    project_questions: list[InterviewQuestion]
    preparation_tips: list[str]


class InterviewPrepResponse(InterviewPrepPayload):
    metadata: RunMetadata


def run_interview_prep(request: InterviewPrepRequest, **llm_kwargs) -> InterviewPrepResponse:
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
        schema=InterviewPrepPayload,
        temperature=0.2,
        max_output_tokens=1200,
        **llm_kwargs,
    )

    prep = result.parsed
    return InterviewPrepResponse(
        technical_questions=prep.technical_questions[:5],
        behavioral_questions=prep.behavioral_questions[:3],
        project_questions=prep.project_questions[:3],
        preparation_tips=prep.preparation_tips[:5],
        metadata=result.metadata,
    )


@router.post("/interview-prep", response_model=InterviewPrepResponse)
def create_interview_prep(request: InterviewPrepRequest):
    try:
        return run_interview_prep(request)
    except LLMCallError as error:
        raise http_error_from_llm(error, "Interview prep generation failed") from error
