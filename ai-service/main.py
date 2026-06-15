from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="AI Job Application Copilot - AI Service")


class AnalyzeRequest(BaseModel):
    resume_text: str = Field(..., min_length=50)
    job_description: str = Field(..., min_length=50)


class AnalyzeResponse(BaseModel):
    score: int
    matched_skills: list[str]
    missing_skills: list[str]
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]


@app.get("/health")
def health():
    return {"ok": True}

@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
    return AnalyzeResponse(
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