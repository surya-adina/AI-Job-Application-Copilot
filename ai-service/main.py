import json
import os
import time
from typing import Literal
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError
from prompt_loader import load_prompt
from skills.extractor import extract_known_skills
from skills.semantic_matcher import find_semantic_matches
from skills.embedding_client import embed_texts


load_dotenv()

app = FastAPI(title="AI Job Application Copilot - AI Service")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
PROMPT_NAME = "analysis_v1"
PROMPT_VERSION = "analysis-v1"


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
    job_skills: list[str]
    obvious_missing_skills: list[str]
    semantic_matches: list[dict]

class AnalyzeResponse(BaseModel):
    analysis: AnalysisPayload
    metadata: AiRunMetadata
    evidence: SkillEvidence


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
    started_at = time.perf_counter()

    try:
        system_prompt = load_prompt(payload.prompt_version)
        resume_skills = extract_known_skills(payload.resume_text)
        job_skills = extract_known_skills(payload.job_description)

        obvious_missing_skills = sorted(
            skill for skill in job_skills if skill not in resume_skills
        )
        semantic_matches = find_semantic_matches(
            resume_skills=resume_skills,
            job_skills=job_skills,
        )
        
        evidence = SkillEvidence(
            resume_skills=resume_skills,
            job_skills=job_skills,
            obvious_missing_skills=obvious_missing_skills,
            semantic_matches=semantic_matches,
        )

        response = client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "resume_text": payload.resume_text,
                            "job_description": payload.job_description,
                            "resume_skills": resume_skills,
                            "job_skills": job_skills,
                            "obvious_missing_skills": obvious_missing_skills,
                            "semantic_matches": semantic_matches,
                            "output_schema": {
                                "score": "integer from 0 to 100",
                                "matched_skills": "array of strings",
                                "missing_skills": "array of strings",
                                "strengths": "array of strings",
                                "weaknesses": "array of strings",
                                "recommendations": "array of strings",
                            },
                        }
                    ),
                },
            ],
            text={
                "format": {
                    "type": "json_object",
                }
            },
        )

        latency_ms = int((time.perf_counter() - started_at) * 1000)

        raw_text = response.output_text
        parsed = json.loads(raw_text)
        analysis = AnalysisPayload(**parsed)

        usage = response.usage
        tokens_in = usage.input_tokens if usage else 0
        tokens_out = usage.output_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else tokens_in + tokens_out
        estimated_cost_usd = (tokens_in * 0.150 / 1_000_000) + (tokens_out * 0.600 / 1_000_000)

        metadata = AiRunMetadata(
            endpoint="/analyze",
            model=OPENAI_MODEL,
            prompt_version=payload.prompt_version,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            total_tokens=total_tokens,
            status="SUCCESS",
            estimated_cost_usd=estimated_cost_usd,
        )

        return AnalyzeResponse(
            analysis=analysis,
            metadata=metadata,
            evidence=evidence,
        )

    except (json.JSONDecodeError, ValidationError) as error:
        latency_ms = int((time.perf_counter() - started_at) * 1000)

        metadata = AiRunMetadata(
            endpoint="/analyze",
            model=OPENAI_MODEL,
            prompt_version=PROMPT_VERSION,
            latency_ms=latency_ms,
            tokens_in=0,
            tokens_out=0,
            total_tokens=0,
            status="FAILED",
            error_type="STRUCTURED_OUTPUT_ERROR",
            estimated_cost_usd=estimated_cost_usd,
        )

        raise HTTPException(
            status_code=502,
            detail={
                "message": "Model returned invalid structured output",
                "error": str(error),
                "metadata": metadata.model_dump(),
            },
        )

    except Exception as error:
        latency_ms = int((time.perf_counter() - started_at) * 1000)

        metadata = AiRunMetadata(
            endpoint="/analyze",
            model=OPENAI_MODEL,
            prompt_version=PROMPT_VERSION,
            latency_ms=latency_ms,
            tokens_in=0,
            tokens_out=0,
            total_tokens=0,
            status="FAILED",
            error_type=type(error).__name__,
        )

        raise HTTPException(
            status_code=500,
            detail={
                "message": "AI analysis failed",
                "error": str(error),
                "metadata": metadata.model_dump(),
            },
        )