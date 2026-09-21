import json
import os

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from prompt_loader import load_prompt

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class JobRequirementsPayload(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)


def clean_skill_name(skill: str) -> str:
    replacements = {
        "Go Lang": "Go",
        "Go lang": "Go",
        "go lang": "Go",
        "Claude Code/Codex/Cursor": "Agentic Coding Tools",
        "Claude Code, Codex, or Cursor": "Agentic Coding Tools",
        "Claude Code, Codex, Cursor": "Agentic Coding Tools",
    }

    cleaned = skill.strip()

    for wrong, fixed in replacements.items():
        cleaned = cleaned.replace(wrong, fixed)

    return cleaned


def dedupe_skills(skills: list[str]) -> list[str]:
    seen = set()
    cleaned_skills = []

    for skill in skills:
        cleaned = clean_skill_name(skill)

        if not cleaned:
            continue

        normalized = cleaned.lower()

        if normalized in seen:
            continue

        seen.add(normalized)
        cleaned_skills.append(cleaned)

    return cleaned_skills


def extract_job_requirements_llm(job_description: str) -> dict[str, list[str]]:
    prompt = load_prompt("job_requirements_v1")

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "job_description": job_description,
                    }
                ),
            },
        ],
        temperature=0.1,
        max_output_tokens=500,
        text={
            "format": {
                "type": "json_object",
            }
        },
    )

    parsed = json.loads(response.output_text)
    payload = JobRequirementsPayload(**parsed)

    required_skills = dedupe_skills(payload.required_skills)
    preferred_skills = dedupe_skills(payload.preferred_skills)

    required_set = set(required_skills)

    return {
        "required_skills": required_skills,
        "preferred_skills": [
            skill for skill in preferred_skills if skill not in required_set
        ],
    }