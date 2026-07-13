import re
import time
from fastapi import APIRouter
from openai import OpenAI
from pydantic import BaseModel
from prompt_loader import load_prompt

router = APIRouter()
client = OpenAI()

def clean_cover_letter(content: str) -> str:
    lines = content.strip().splitlines()
    cleaned_lines = []

    blocked_lines = {
        "sincerely",
        "sincerely,",
        "best regards",
        "best regards,",
        "regards",
        "regards,",
    }

    for line in lines:
        stripped = line.strip()
        normalized = stripped.lower()

        if not stripped:
            cleaned_lines.append("")
            continue

        if normalized in blocked_lines:
            continue

        if "[" in stripped and "]" in stripped:
            continue

        cleaned_lines.append(stripped)

    replacements = {
        "Myfamiliarity": "My familiarity",
        "workingwith": "working with",
        "reliabilityand": "reliability and",
        "inareas": "in areas",
        "tooptimizing": "to optimizing",
        "tothe": "to the",
    }

    cleaned_content = "\n".join(cleaned_lines).strip()

    for wrong, fixed in replacements.items():
        cleaned_content = cleaned_content.replace(wrong, fixed)

    cleaned_content = re.sub(r"([.!?])([A-Z])", r"\1 \2", cleaned_content)
    
    return cleaned_content

class CoverLetterRequest(BaseModel):
    resume_text: str
    job_description: str


class CoverLetterResponse(BaseModel):
    content: str
    metadata: dict


@router.post("/cover-letter", response_model=CoverLetterResponse)
def create_cover_letter(request: CoverLetterRequest):
    start_time = time.time()

    prompt_template = load_prompt("cover_letter_v1")

    prompt = prompt_template.format(
        resume_text=request.resume_text,
        job_description=request.job_description,
    )

    response = client.responses.create(
    model="gpt-4o-mini",
    input=prompt,
    temperature=0.2,
)

    content = clean_cover_letter(response.output_text)

    latency_ms = int((time.time() - start_time) * 1000)

    return {
        "content": content,
        "metadata": {
            "endpoint": "/cover-letter",
            "model": "gpt-4o-mini",
            "prompt_version": "cover_letter_v1",
            "latency_ms": latency_ms,
            "status": "SUCCESS",
        },
    }