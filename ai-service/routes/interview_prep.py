import json
import time

from fastapi import APIRouter, HTTPException
from openai import OpenAI
from pydantic import BaseModel

from prompt_loader import load_prompt

router = APIRouter()
client = OpenAI()


class InterviewPrepRequest(BaseModel):
    resume_text: str
    job_description: str


class InterviewQuestion(BaseModel):
    question: str
    why_it_matters: str
    suggested_focus: str


class InterviewPrepResponse(BaseModel):
    technical_questions: list[InterviewQuestion]
    behavioral_questions: list[InterviewQuestion]
    project_questions: list[InterviewQuestion]
    preparation_tips: list[str]
    metadata: dict


def parse_json_output(output: str) -> dict:
    cleaned = output.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned.replace("```json", "", 1).strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```", "", 1).strip()

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    return json.loads(cleaned)


@router.post("/interview-prep", response_model=InterviewPrepResponse)
def create_interview_prep(request: InterviewPrepRequest):
    try:
        start_time = time.time()

        prompt_template = load_prompt("interview_prep_v1")

        prompt = (
            prompt_template
            .replace("{resume_text}", request.resume_text)
            .replace("{job_description}", request.job_description)
        )

        response = client.responses.create(
            model="gpt-4o-mini",
            input=prompt,
            temperature=0.2,
            max_output_tokens=900,
            text={
                "format": {
                    "type": "json_object",
                }
            },
        )

        usage = response.usage
        tokens_in = usage.input_tokens if usage else None
        tokens_out = usage.output_tokens if usage else None
        total_tokens = usage.total_tokens if usage else None

        parsed = parse_json_output(response.output_text)
        latency_ms = int((time.time() - start_time) * 1000)

        return {
            **parsed,
            "metadata": {
                "endpoint": "/interview-prep",
                "model": "gpt-4o-mini",
                "prompt_version": "interview_prep_v1",
                "latency_ms": latency_ms,
                "status": "SUCCESS",
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "total_tokens": total_tokens,
            },
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"{type(error).__name__}: {error}",
        )