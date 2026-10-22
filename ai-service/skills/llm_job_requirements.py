import json

from pydantic import BaseModel

from llm import RunMetadata, call_structured
from prompt_loader import load_prompt

PROMPT_VERSION = "job_requirements_v1"


class JobRequirementsPayload(BaseModel):
    required_skills: list[str]
    preferred_skills: list[str]


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


def extract_job_requirements_llm_with_metadata(
    job_description: str, **llm_kwargs
) -> tuple[dict[str, list[str]], RunMetadata]:
    result = call_structured(
        endpoint="skill:extract_job_requirements",
        prompt_version=PROMPT_VERSION,
        system=load_prompt(PROMPT_VERSION),
        user=json.dumps({"job_description": job_description}),
        schema=JobRequirementsPayload,
        temperature=0.1,
        max_output_tokens=500,
        **llm_kwargs,
    )

    required_skills = dedupe_skills(result.parsed.required_skills)
    preferred_skills = dedupe_skills(result.parsed.preferred_skills)
    required_set = {skill.lower() for skill in required_skills}

    requirements = {
        "required_skills": required_skills,
        "preferred_skills": [skill for skill in preferred_skills if skill.lower() not in required_set],
    }
    return requirements, result.metadata


def extract_job_requirements_llm(job_description: str, **llm_kwargs) -> dict[str, list[str]]:
    requirements, _ = extract_job_requirements_llm_with_metadata(job_description, **llm_kwargs)
    return requirements
