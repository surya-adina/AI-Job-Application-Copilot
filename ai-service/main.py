from fastapi import FastAPI
from routes.analysis import router as analysis_router
from routes.resume_review import router as resume_review_router
from routes.cover_letter import router as cover_letter_router
from routes.interview_prep import router as interview_prep_router

app = FastAPI(title="AI Job Application Copilot - AI Service")

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(analysis_router)
app.include_router(resume_review_router)
app.include_router(cover_letter_router)
app.include_router(interview_prep_router)