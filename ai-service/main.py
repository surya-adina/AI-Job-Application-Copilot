import time

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="AI Job Application Copilot - AI Service")


class AnalyzeRequest(BaseModel):
    resume_text: str = Field(..., min_length=50)
    job_description: str = Field(..., min_length=50)


class AnalysisPayload(BaseModel):
    score: int
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
    status: str


class AnalyzeResponse(BaseModel):
    analysis: AnalysisPayload
    metadata: AiRunMetadata


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
    started_at = time.perf_counter()

    analysis = AnalysisPayload(
        score=78,
        matched_skills=["React", "Node.js", "PostgreSQL", "Prisma"],
        missing_skills=["AWS", "Docker", "OpenTelemetry"],
        strengths=[
            "Strong full-stack backend foundation.",
            "Good experience with TypeScript, PostgreSQL, and structured APIs.",
        ],
        weaknesses=[
            "Limited visible production deployment evidence.",
            "Cloud and observability experience need stronger proof.",
        ],
        recommendations=[
            "Add measurable AI observability metrics.",
            "Highlight eval harness and token-cost tracking.",
        ],
    )

    latency_ms = int((time.perf_counter() - started_at) * 1000)

    metadata = AiRunMetadata(
        endpoint="/analyze",
        model="fake-python-analyzer-v0",
        prompt_version="analysis-v0",
        latency_ms=latency_ms,
        tokens_in=0,
        tokens_out=0,
        total_tokens=0,
        status="SUCCESS",
    )

    return AnalyzeResponse(analysis=analysis, metadata=metadata)